import os
import re
from copy import deepcopy
from functools import cache
from typing import Any, AsyncIterator, Protocol, cast

from mistralai import Mistral
from openai import AsyncOpenAI, OpenAI

from unmute.kyutai_constants import LLM_SERVER

from ..kyutai_constants import KYUTAI_LLM_MODEL

INTERRUPTION_CHAR = "—"  # em-dash
USER_SILENCE_MARKER = "..."


class StreamingTextCleaner:
    """Nettoyeur de texte avec état pour streaming token-par-token.
    
    Gère les suppressions en temps réel :
    - Les emojis qui causent des artefacts TTS
    - Le contenu entre parenthèses () via état "in_parentheses"
    - Le contenu entre crochets [] via état "in_brackets"
    - Le contenu entre chevrons <> via état "in_chevrons"
    """
    
    def __init__(self):
        self.in_parentheses = 0  # Compteur pour parenthèses imbriquées
        self.in_brackets = 0     # Compteur pour crochets imbriqués
        self.in_chevrons = 0     # Compteur pour chevrons imbriqués
        
        # Pattern emoji (garde l'existant)
        self.emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U00002702-\U000027B0"  # dingbats
            "\U000024C2-\U0001F251"  # enclosed characters
            "]+",
            flags=re.UNICODE
        )
    
    def clean_token(self, token: str) -> str:
        """Nettoie un token en gardant l'état des ouvertures/fermetures"""
        
        # Supprimer les emojis en premier
        token = self.emoji_pattern.sub('', token)
        if not token:
            return ""
        
        result = ""
        i = 0
        
        while i < len(token):
            char = token[i]
            
            # Gestion des parenthèses
            if char == '(':
                self.in_parentheses += 1
                # Ne pas inclure le caractère d'ouverture
            elif char == ')':
                if self.in_parentheses > 0:
                    self.in_parentheses -= 1
                    # Ne pas inclure le caractère de fermeture
                else:
                    # Parenthèse fermante sans ouverture, la garder
                    result += char
            
            # Gestion des crochets
            elif char == '[':
                self.in_brackets += 1
                # Ne pas inclure le caractère d'ouverture
            elif char == ']':
                if self.in_brackets > 0:
                    self.in_brackets -= 1
                    # Ne pas inclure le caractère de fermeture
                else:
                    # Crochet fermant sans ouverture, le garder
                    result += char
            
            # Gestion des chevrons
            elif char == '<':
                self.in_chevrons += 1
                # Ne pas inclure le caractère d'ouverture
            elif char == '>':
                if self.in_chevrons > 0:
                    self.in_chevrons -= 1
                    # Ne pas inclure le caractère de fermeture
                else:
                    # Chevron fermant sans ouverture, le garder
                    result += char
            
            # Caractère normal
            else:
                # Inclure seulement si on n'est dans aucune structure à supprimer
                if (self.in_parentheses == 0 and
                    self.in_brackets == 0 and
                    self.in_chevrons == 0):
                    result += char
                # Sinon le caractère est supprimé (on est dans une structure)
            
            i += 1
        
        return result


# Instance globale réutilisée pour maintenir l'état entre tokens
_text_cleaner = StreamingTextCleaner()

def clean_text_for_tts(text: str) -> str:
    """Interface de compatibilité qui utilise le nettoyeur avec état"""
    return _text_cleaner.clean_token(text)


def preprocess_messages_for_llm(
    chat_history: list[dict[str, str]],
) -> list[dict[str, str]]:
    output = []

    for message in chat_history:
        message = deepcopy(message)

        # Sometimes, an interruption happens before the LLM can say anything at all.
        # In that case, we're left with a message with only INTERRUPTION_CHAR.
        # Simplify by removing.
        if message["content"].replace(INTERRUPTION_CHAR, "") == "":
            continue

        if output and message["role"] == output[-1]["role"]:
            output[-1]["content"] += " " + message["content"]
        else:
            output.append(message)

    def role_at(index: int) -> str | None:
        if index >= len(output):
            return None
        return output[index]["role"]

    if role_at(0) == "system" and role_at(1) in [None, "assistant"]:
        # Some LLMs, like Gemma, get confused if the assistant message goes before user
        # messages, so add a dummy user message.
        output = [output[0]] + [{"role": "user", "content": "Hello."}] + output[1:]

    for message in chat_history:
        if (
            message["role"] == "user"
            and message["content"].startswith(USER_SILENCE_MARKER)
            and message["content"] != USER_SILENCE_MARKER
        ):
            # This happens when the user is silent but then starts talking again after
            # the silence marker was inserted but before the LLM could respond.
            # There are special instructions in the system prompt about how to handle
            # the silence marker, so remove the marker from the message to not confuse
            # the LLM
            message["content"] = message["content"][len(USER_SILENCE_MARKER) :]

    return output


async def rechunk_to_words(iterator: AsyncIterator[str]) -> AsyncIterator[str]:
    """Rechunk the stream of text to whole words.

    Otherwise the TTS doesn't know where word boundaries are and will mispronounce
    split words.

    The spaces will be included with the next word, so "foo bar baz" will be split into
    "foo", " bar", " baz".
    Multiple space-like characters will be merged to a single space.
    """
    buffer = ""
    space_re = re.compile(r"\s+")
    prefix = ""
    async for delta in iterator:
        buffer = buffer + delta
        while True:
            match = space_re.search(buffer)
            if match is None:
                break
            chunk = buffer[: match.start()]
            buffer = buffer[match.end() :]
            if chunk != "":
                yield prefix + chunk
            prefix = " "

    if buffer != "":
        yield prefix + buffer


class LLMStream(Protocol):
    async def chat_completion(
        self, messages: list[dict[str, str]]
    ) -> AsyncIterator[str]:
        """Get a chat completion from the LLM."""
        ...


class MistralStream:
    def __init__(self):
        self.current_message_index = 0
        self.mistral = Mistral(api_key=os.environ["MISTRAL_API_KEY"])

    async def chat_completion(
        self, messages: list[dict[str, str]]
    ) -> AsyncIterator[str]:
        event_stream = await self.mistral.chat.stream_async(
            model="mistral-large-latest",
            messages=cast(Any, messages),  # It's too annoying to type this properly
            temperature=1.0,
        )

        async for event in event_stream:
            delta = event.data.choices[0].delta.content
            assert isinstance(delta, str)  # make Pyright happy
            yield delta


def get_openai_client(server_url: str = LLM_SERVER) -> AsyncOpenAI:
    return AsyncOpenAI(api_key="EMPTY", base_url=server_url + "/v1")


@cache
def autoselect_model() -> str:
    if KYUTAI_LLM_MODEL is not None:
        return KYUTAI_LLM_MODEL
    client_sync = OpenAI(api_key="EMPTY", base_url=get_openai_client().base_url)
    models = client_sync.models.list()
    if len(models.data) != 1:
        raise ValueError("There are multiple models available. Please specify one.")
    return models.data[0].id


class VLLMStream:
    def __init__(
        self,
        client: AsyncOpenAI,
        temperature: float = 1.0,
    ):
        """
        If `model` is None, it will look at the available models, and if there is only
        one model, it will use that one. Otherwise, it will raise.
        """
        self.client = client
        self.model = autoselect_model()
        self.temperature = temperature

    async def chat_completion(
        self, messages: list[dict[str, str]]
    ) -> AsyncIterator[str]:
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=cast(Any, messages),  # Cast and hope for the best
            stream=True,
            temperature=self.temperature,
        )

        async with stream:
            async for chunk in stream:
                chunk_content = chunk.choices[0].delta.content

                if not chunk_content:
                    # This happens on the first message, see:
                    # https://platform.openai.com/docs/guides/streaming-responses#read-the-responses
                    # Also ignore `null` chunks, which is what llama.cpp does:
                    # https://github.com/ggml-org/llama.cpp/blob/6491d6e4f1caf0ad2221865b4249ae6938a6308c/tools/server/tests/unit/test_chat_completion.py#L338
                    continue

                # Nettoyer le texte avec la version douce qui préserve le rythme
                cleaned_content = clean_text_for_tts(chunk_content)
                
                if cleaned_content:  # Seulement si il reste du contenu après nettoyage
                    yield cleaned_content
