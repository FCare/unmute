import logging
import os
import re
import json
from copy import deepcopy
from functools import cache
from typing import Any, AsyncIterator, AsyncGenerator, Protocol, cast

import httpx
from mistralai import Mistral
from openai import AsyncOpenAI, OpenAI

from unmute.kyutai_constants import LLM_SERVER

from ..kyutai_constants import KYUTAI_LLM_MODEL, KYUTAI_LLM_API_KEY, KYUTAI_LLM_THINK

INTERRUPTION_CHAR = "—"  # em-dash
USER_SILENCE_MARKER = "..."


def clean_text_for_tts(text: str) -> str:
    """Supprime uniquement les emojis qui causent des artefacts TTS"""
    # Supprimer les emojis (caractères Unicode dans les plages d'emojis)
    emoji_pattern = re.compile(
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
    return emoji_pattern.sub('', text)


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


def get_openai_client(server_url: str = LLM_SERVER, api_key: str = KYUTAI_LLM_API_KEY or "EMPTY") -> AsyncOpenAI:
    return AsyncOpenAI(api_key=api_key, base_url=server_url + "/v1")


@cache
def autoselect_model() -> str:
    if KYUTAI_LLM_MODEL is not None:
        return KYUTAI_LLM_MODEL
    client_sync = OpenAI(api_key=get_openai_client().api_key, base_url=get_openai_client().base_url)
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
        # Paramètres extra pour Ollama
        extra_body = {}
        if not KYUTAI_LLM_THINK:
            extra_body["think"] = False
            
        # Reconstituer le payload JSON qui sera envoyé à Ollama
        # Via l'endpoint /v1/chat/completions (OpenAI compatible)
        json_payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": self.temperature,
        }
        # Les paramètres extra_body sont fusionnés au niveau racine par OpenAI client
        json_payload.update(extra_body)
        
        logging.info(f"JSON PAYLOAD TO OLLAMA /v1/chat/completions: {json_payload}")
            
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=cast(Any, messages),  # Cast and hope for the best
            stream=True,
            temperature=self.temperature,
            extra_body=extra_body,
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
                
                # Logging pour voir tout le texte qui passe
                logging.info(f"TEXT CHUNK: {repr(chunk_content)}")
                if chunk_content != cleaned_content:
                    logging.info(f"TEXT CLEANING - EMOJI SUPPRIMÉ: {repr(chunk_content)} → {repr(cleaned_content)}")


class OllamaStream:
    """Stream pour l'API native Ollama qui supporte le paramètre 'think'"""
    
    def __init__(
        self,
        server_url: str = LLM_SERVER,
        temperature: float = 1.0,
    ):
        self.server_url = server_url
        self.client = httpx.AsyncClient(base_url=server_url, timeout=60.0)
        self.model = autoselect_model_ollama()
        self.temperature = temperature

    async def chat_completion(
        self, messages: list[dict[str, str]]
    ) -> AsyncIterator[str]:
        # Format natif Ollama
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "keep_alive": -1,  # Garde le modèle en mémoire indéfiniment
            "options": {
                "temperature": self.temperature
            }
        }
        
        # Le paramètre think va directement à la racine (pas dans options)
        if not KYUTAI_LLM_THINK:
            payload["think"] = False
            
        logging.info(f"OLLAMA NATIVE API PAYLOAD: {payload}")
        
        async with self.client.stream(
            "POST",
            "/api/chat",  # API native au lieu de /v1/chat/completions
            json=payload,
            headers={"Content-Type": "application/json"}
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.strip():
                    try:
                        data = json.loads(line)
                        # Format de réponse Ollama différent
                        if "message" in data and "content" in data["message"]:
                            content = data["message"]["content"]
                            if content:
                                cleaned_content = clean_text_for_tts(content)
                                
                                # Logging pour voir tout le texte qui passe
                                logging.info(f"OLLAMA TEXT CHUNK: {repr(content)}")
                                if content != cleaned_content:
                                    logging.info(f"OLLAMA TEXT CLEANING - EMOJI SUPPRIMÉ: {repr(content)} → {repr(cleaned_content)}")
                                
                                if cleaned_content:
                                    yield cleaned_content
                    except json.JSONDecodeError:
                        continue

    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.client.aclose()


def is_ollama_server(server_url: str = LLM_SERVER) -> bool:
    """Détecte si le serveur est un serveur Ollama en testant l'endpoint /api/tags"""
    try:
        with httpx.Client(base_url=server_url, timeout=5.0) as client:
            response = client.get("/api/tags")
            response.raise_for_status()
            # Si l'endpoint /api/tags existe et retourne du JSON avec "models", c'est Ollama
            data = response.json()
            return "models" in data
    except Exception:
        return False


@cache
def autoselect_model_ollama() -> str:
    """Version spécifique pour Ollama utilisant l'API native"""
    if KYUTAI_LLM_MODEL is not None:
        return KYUTAI_LLM_MODEL
    
    # Utiliser l'API native Ollama pour lister les modèles
    try:
        with httpx.Client(base_url=LLM_SERVER, timeout=10.0) as client:
            response = client.get("/api/tags")
            response.raise_for_status()
            models = response.json()
            if not models.get("models"):
                raise ValueError("Aucun modèle disponible sur le serveur Ollama.")
            if len(models["models"]) != 1:
                raise ValueError("Il y a plusieurs modèles disponibles. Veuillez en spécifier un.")
            return models["models"][0]["name"]
    except Exception as e:
        logging.error(f"Erreur lors de la récupération des modèles Ollama: {e}")
        raise


def create_llm_stream(temperature: float = 1.0) -> LLMStream:
    """Factory function pour créer le bon type de stream selon le serveur"""
    if is_ollama_server():
        logging.info("Serveur Ollama détecté, utilisation de l'API native")
        return OllamaStream(server_url=LLM_SERVER, temperature=temperature)  # type: ignore
    else:
        logging.info("Serveur non-Ollama détecté, utilisation de l'API OpenAI compatible")
        client = get_openai_client()
        return VLLMStream(client=client, temperature=temperature)
