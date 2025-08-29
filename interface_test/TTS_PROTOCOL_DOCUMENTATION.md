# Documentation du Protocole TTS - Communication avec Docker TTS

## Vue d'ensemble

Ce document décrit le protocole de communication avec le serveur TTS moshi-server Rust via WebSocket. Ce protocole permet de remplacer complètement le backend Python et de communiquer directement avec le serveur TTS Docker.

## Architecture

```
Client Python ← WebSocket + MessagePack → Docker TTS (moshi-server Rust)
```

## Connexion WebSocket

### URL de base
```
ws://172.18.0.2:8080/api/tts_streaming
```

### Paramètres de requête obligatoires

| Paramètre | Valeur | Description |
|-----------|--------|-------------|
| `format` | `"PcmMessagePack"` | **CRITIQUE** - Format de réponse PCM |
| `auth_id` | `"public_token"` | Token d'authentification |

### Paramètres optionnels

| Paramètre | Valeur par défaut | Description |
|-----------|-------------------|-------------|
| `voice` | `"unmute-prod-website/developpeuse-3.wav"` | Voix à utiliser |
| `cfg_alpha` | `1.5` | Coefficient Classifier-Free Guidance |
| `temperature` | `null` | Température de génération (sampling) |
| `top_k` | `null` | Top-K sampling |
| `seed` | `null` | Seed pour la génération |
| `max_seq_len` | `null` | Longueur max de séquence |

### Exemple d'URL complète
```
ws://172.18.0.2:8080/api/tts_streaming?format=PcmMessagePack&auth_id=public_token&voice=unmute-prod-website/developpeuse-3.wav&cfg_alpha=1.5
```

### Headers requis
```python
headers = {"kyutai-api-key": "public_token"}
```

## Voice Cloning

### Voix personnalisées
Le système supporte les voix personnalisées via voice cloning :

#### 1. Créer embedding de voix :
```python
# Enregistrer audio de référence
voice_audio = record_reference_voice()

# Générer embedding via serveur voice cloning 
response = requests.post(
    "http://localhost:8092/api/voice",
    data=voice_audio,
    headers={"Content-Type": "application/octet-stream"}
)
voice_embedding = response.content
```

#### 2. Utiliser voix personnalisée :
```python
# Connexion avec voix custom
voice_name = "custom:voice_id_123"
ws_url = f"ws://172.18.0.2:8080/api/tts_streaming?format=PcmMessagePack&auth_id=public_token"

# Après message Ready
await websocket.send(voice_embedding)  # Envoyer embedding binaire

# Puis envoi texte normal...
```

### Format de voix avec timing
```python
# Démarrer à un point spécifique de l'audio de référence
voice = "developpeuse-3.wav+2.5"  # Démarrer à 2.5 secondes
```

## Protocole de communication

### 1. Établissement de la connexion

#### Purge des messages résiduels (CRITIQUE)
Le serveur TTS garde parfois des données d'anciennes sessions. Il faut **absolument** purger ces messages au démarrage :

```python
# Purge jusqu'à 10 messages résiduels
for i in range(10):
    try:
        message_bytes = await asyncio.wait_for(websocket.recv(), timeout=0.5)
        data = msgpack.unpackb(message_bytes)
        if data.get('type') == 'Ready':
            break  # Session propre trouvée
    except asyncio.TimeoutError:
        break  # Plus de messages résiduels
```

#### Message Ready
Le serveur envoie un message `Ready` pour signaler qu'il est prêt :

```json
{
    "type": "Ready"
}
```

### 2. Envoi d'embedding de voix (optionnel)

#### Pour voix personnalisée :
```python
# Après Ready, avant envoi texte
if voice.startswith("custom:"):
    voice_embedding = voice_embeddings_cache.get(voice)
    if voice_embedding:
        await websocket.send(voice_embedding)  # Données binaires
```

### 3. Envoi de texte

#### Format des messages texte
```python
message = {
    "type": "Text",
    "text": "mot_ou_phrase"
}
await websocket.send(msgpack.packb(message))
```

#### Stratégie d'envoi recommandée
Envoyer **mot par mot** avec une pause de 100ms entre chaque mot (comme le backend officiel) :

```python
words = text.split()
for word in words:
    message = {"type": "Text", "text": word}
    await websocket.send(msgpack.packb(message))
    await asyncio.sleep(0.1)
```

#### Signal de fin (EOS)
```python
eos_message = {"type": "Eos"}
await websocket.send(msgpack.packb(eos_message))
```

### 4. Réception des réponses

Tous les messages reçus sont encodés en **MessagePack**.

#### Types de messages reçus

##### Message Ready
```json
{
    "type": "Ready"
}
```

##### Message Audio (données PCM)
```json
{
    "type": "Audio",
    "pcm": [0.1, -0.2, 0.3, ...]  // float32 array
}
```

##### Message Text (métadonnées timing)
```json
{
    "type": "Text", 
    "text": "mot_prononcé",
    "start_s": 1.2,
    "stop_s": 1.8
}
```

##### Signal de fin
```json
{
    "type": "Text",
    "text": "",
    "start_s": 0,
    "stop_s": 0
}
```

##### Message d'erreur
```json
{
    "type": "Error",
    "message": "Description de l'erreur"
}
```

## Traitement de l'audio

### Format PCM reçu
- **Type** : `float32`
- **Range** : `[-1.0, 1.0]`
- **Échantillonnage** : `24000 Hz`
- **Canaux** : `1` (mono)

### Conversion vers WAV
```python
# Concaténer tous les chunks PCM
audio_array = np.array(all_pcm_chunks, dtype=np.float32)

# Convertir float32 vers int16
audio_int16 = (audio_array * 32767).astype(np.int16)

# Sauvegarder en WAV
with wave.open(output_file, 'wb') as wav_file:
    wav_file.setnchannels(1)      # Mono
    wav_file.setsampwidth(2)      # 16-bit
    wav_file.setframerate(24000)  # 24kHz
    wav_file.writeframes(audio_int16.tobytes())
```

## Timing et synchronisation

### Exécution parallèle obligatoire
L'audio est généré **en temps réel** pendant l'envoi des mots. Il faut **absolument** exécuter l'envoi et la réception en parallèle :

```python
async def send_text():
    # Envoi mot par mot + EOS
    
async def receive_audio():
    # Réception continue des messages

# Exécution parallèle
await asyncio.gather(send_text(), receive_audio())
```

### Ordre des opérations
1. **Connexion** WebSocket
2. **Purge** messages résiduels (crucial !)
3. **Attente** message Ready
4. **Envoi** voice embedding (si voix personnalisée)
5. **Démarrage parallèle** : envoi + réception
6. **Collection** données audio
7. **Détection** signal de fin
8. **Sauvegarde** audio final

## Gestion d'erreurs

### Erreurs communes

| Erreur | Cause | Solution |
|--------|-------|----------|
| Audio incomplet | Pas de purge résiduels | Ajouter purge au démarrage |
| Timeout connexion | Mauvaise auth | Vérifier `auth_id` et headers |
| Format incorrect | Mauvais paramètre | Utiliser `format=PcmMessagePack` |
| Session bloquée | Données résiduelles | Augmenter timeout purge |

### Limites de sécurité
- **Max messages** : 500 par session
- **Timeout purge** : 0.5s par message
- **Max purge** : 10 messages résiduels

## Exemple d'implémentation complète

Voir [`perfect_tts_test.py`](./perfect_tts_test.py) pour une implémentation complète et fonctionnelle.

## Configuration serveur

### Fichier de configuration TTS
Voir [`services/moshi-server/configs/tts.toml`](../services/moshi-server/configs/tts.toml) pour les paramètres serveur.

### Paramètres critiques
- `n_q = 16` : Niveaux de quantization (impact mémoire GPU)
- `cfg_coef = 2.0` : Coefficient base pour CFG
- `authorized_ids = ["public_token"]` : Tokens autorisés

## Performance

### Optimisations possibles
1. **Mémoire GPU** : Réduire `n_q` et `cfg_coef` dans config TTS
2. **Latence** : Ajuster pause entre mots (défaut 100ms)
3. **Qualité** : Ajuster `cfg_alpha`

### Métriques typiques
- **Latence première note** : ~200-500ms
- **Débit audio** : Temps réel (24kHz)
- **Mémoire nécessaire** : Selon config `n_q`

## Voix disponibles

### Voix par défaut
```
unmute-prod-website/developpeuse-3.wav
```

### Voix personnalisées
Format : `custom:nom_de_voix`
(Nécessite envoi d'embedding voice après connexion)

---

**Note** : Ce protocole reproduit exactement le comportement du backend Python officiel mais communique directement avec le serveur TTS Docker pour de meilleures performances.