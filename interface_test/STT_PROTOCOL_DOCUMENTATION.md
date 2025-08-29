# Documentation Protocole STT moshi-server

**Version:** 1.0  
**Date:** 2025-08-29  
**Status:** Vérifié et testé fonctionnel

## Vue d'ensemble

Cette documentation décrit le protocole WebSocket pour la reconnaissance vocale (STT) du serveur moshi-server Rust. Toutes les informations sont basées sur des tests réels et du code fonctionnel.

## Configuration serveur

### Conteneur Docker
- **Conteneur séparé** : `unmute-stt-1` (différent du TTS)
- **Port:** 8080
- **Endpoint:** `/api/asr-streaming`
- **Protocole:** WebSocket + MessagePack

### URL de connexion
```
ws://[IP_CONTENEUR]:8080/api/asr-streaming
```

### Authentification
```http
Headers: {"kyutai-api-key": "public_token"}
```

## Format audio

### Spécifications requises
- **Échantillonnage:** 24 000 Hz exactement
- **Format:** Float32 PCM mono
- **Valeurs:** -1.0 à +1.0
- **Taille chunk:** 1920 échantillons par message

### Conversion automatique
Le script gère automatiquement:
- Conversion stéréo → mono (moyenne des canaux)
- Rééchantillonnage vers 24kHz
- Conversion différents formats → float32 PCM

## Protocole de communication

### 1. Connexion
```python
async with websockets.connect(ws_url, additional_headers=headers) as websocket:
```

### 2. Message Ready
Le serveur envoie d'abord:
```python
{"type": "Ready"}
```

### 3. Envoi audio
Format des chunks audio:
```python
message = {
    "type": "Audio",
    "pcm": [float32_samples]  # 1920 échantillons
}
await websocket.send(msgpack.packb(message, use_bin_type=True, use_single_float=True))
```

### 4. Temporisation réaliste
```python
await asyncio.sleep(SAMPLES_PER_FRAME / SAMPLE_RATE)  # = 0.08 secondes
```

### 5. Signal de fin
```python
# Envoyer le marker
marker_message = {"type": "Marker", "id": 999}
await websocket.send(msgpack.packb(marker_message, use_bin_type=True))

# CRUCIAL: Envoyer des chunks de silence pour forcer le traitement (comme le backend)
silence_chunk = np.zeros(SAMPLES_PER_FRAME, dtype=np.float32)
for i in range(25):  # Exactement comme dans le backend
    silence_message = {
        "type": "Audio",
        "pcm": silence_chunk.tolist()
    }
    await websocket.send(msgpack.packb(silence_message, use_bin_type=True, use_single_float=True))
```

## Messages reçus

### Message Word
```python
{
    "type": "Word",
    "text": "bonjour",
    "start_time": 1.25
}
```

### Message EndWord
```python
{
    "type": "EndWord", 
    "stop_time": 1.87
}
```

### Message Step
```python
{
    "type": "Step",
    "step_idx": 150
}
```
*Note: Messages très fréquents pendant le traitement*

### Message Marker
```python
{
    "type": "Marker",
    "id": 999
}
```
*Confirme la réception du signal de fin*

### Message Error
```python
{
    "type": "Error",
    "message": "Description de l'erreur"
}
```

## Exemple d'utilisation

### Script complet testé
Voir [`simple_stt_test.py`](simple_stt_test.py) pour l'implémentation complète.

### Commande d'utilisation
```bash
python3 simple_stt_test.py fichier.wav
```

### Détection automatique IP
```python
from docker_utils import get_stt_container_ip
host = get_stt_container_ip()  # Conteneur STT spécifique
```

## Observations techniques

### Chronologie typique
1. Connexion WebSocket
2. Réception message `Ready`
3. Envoi chunks audio en temps réel
4. Réception messages `Step` (fréquents)
5. Réception messages `Word` avec timestamps
6. Réception messages `EndWord`
7. Envoi marker de fin
8. **Envoi 25 chunks de silence** (crucial pour forcer le traitement)
9. Réception confirmation `Marker` ou fermeture connexion

### Gestion des erreurs
- Vérifier `type: "Error"` dans chaque message
- Limite de sécurité: 10000 messages maximum
- Timeout de connexion WebSocket standard

### Performance
- **Temps réel:** Envoi synchronisé sur la durée audio
- **Chunking:** 1920 échantillons = 80ms d'audio
- **Latence:** Transcription en temps réel pendant l'envoi

## Différences avec TTS

| Aspect | STT | TTS |
|--------|-----|-----|
| Conteneur | `unmute-stt-1` | `unmute-tts-1` |
| Endpoint | `/api/asr-streaming` | `/api/tts_streaming` |
| Direction | Client → Serveur | Serveur → Client |
| Format | Audio PCM | Texte → Audio PCM |
| Messages | Audio chunks | Texte par mots |
| Réponse | Words + timestamps | Audio + texte |
| Fin protocole | Marker + 25 chunks silence | EOS + signal vide |

## Notes techniques vérifiées

- **MessagePack:** `use_bin_type=True, use_single_float=True`
- **Container:** Séparé du TTS (`unmute-stt-1` vs `unmute-tts-1`)
- **Audio:** Format float32 obligatoire
- **Streaming:** Bidirectionnel asynchrone
- **Authentification:** Token "public_token" suffisant
- **Fin propre:** Marker + 25 chunks de silence obligatoires
- **Détection IP:** Utiliser `get_stt_container_ip()` spécifiquement

---

*Documentation basée sur reverse-engineering et tests réels du protocole moshi-server*