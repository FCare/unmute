#!/usr/bin/env python3
"""
Script STT simple - Envoi fichier WAV et réception transcription en streaming
"""

import asyncio
import websockets
import msgpack
import argparse
import wave
import numpy as np
from pathlib import Path
from docker_utils import get_stt_container_ip

# Configuration basée sur l'analyse du backend
STT_SERVER = "ws://172.18.0.2:8080"  # Docker STT (même conteneur que TTS)
STT_PATH = "/api/asr-streaming"
SAMPLE_RATE = 24000
SAMPLES_PER_FRAME = 1920  # Taille de chunk d'après le backend
HEADERS = {"kyutai-api-key": "public_token"}

def load_wav_file(wav_path: Path) -> np.ndarray:
    """Charge un fichier WAV et le convertit au format requis"""
    print(f"📁 Chargement du fichier: {wav_path}")
    
    with wave.open(str(wav_path), 'rb') as wav_file:
        # Vérifier le format
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        framerate = wav_file.getframerate()
        n_frames = wav_file.getnframes()
        
        print(f"  📊 Format original:")
        print(f"    - Canaux: {channels}")
        print(f"    - Largeur échantillon: {sample_width} bytes")
        print(f"    - Fréquence: {framerate} Hz")
        print(f"    - Durée: {n_frames / framerate:.2f} secondes")
        
        # Lire les données audio
        audio_data = wav_file.readframes(n_frames)
        
        # Convertir en numpy array
        if sample_width == 1:
            audio_np = np.frombuffer(audio_data, dtype=np.uint8)
            audio_np = (audio_np.astype(np.float32) - 128) / 128.0
        elif sample_width == 2:
            audio_np = np.frombuffer(audio_data, dtype=np.int16)
            audio_np = audio_np.astype(np.float32) / 32768.0
        elif sample_width == 4:
            audio_np = np.frombuffer(audio_data, dtype=np.int32)
            audio_np = audio_np.astype(np.float32) / 2147483648.0
        else:
            raise ValueError(f"Format non supporté: {sample_width} bytes par échantillon")
        
        # Convertir en mono si stéréo
        if channels == 2:
            audio_np = audio_np.reshape(-1, 2)
            audio_np = audio_np.mean(axis=1)  # Moyenne des deux canaux
            print(f"  🔄 Conversion stéréo → mono")
        elif channels > 2:
            raise ValueError(f"Trop de canaux: {channels} (max supporté: 2)")
        
        # Rééchantillonnage si nécessaire
        if framerate != SAMPLE_RATE:
            print(f"  🔄 Rééchantillonnage: {framerate} Hz → {SAMPLE_RATE} Hz")
            # Rééchantillonnage simple (à améliorer avec scipy si besoin)
            ratio = SAMPLE_RATE / framerate
            new_length = int(len(audio_np) * ratio)
            indices = np.linspace(0, len(audio_np) - 1, new_length)
            audio_np = np.interp(indices, np.arange(len(audio_np)), audio_np)
        
        print(f"  ✅ Format final: {len(audio_np)} échantillons, {len(audio_np)/SAMPLE_RATE:.2f}s")
        return audio_np.astype(np.float32)

async def stream_stt_transcription(wav_path: Path, host: str = None, port: int = 8080):
    """Envoie un fichier WAV et reçoit la transcription en streaming"""
    
    # Détection automatique de l'IP si pas fournie
    if host is None:
        print("🔍 Détection automatique du conteneur STT...")
        host = get_stt_container_ip()
        if host is None:
            print("❌ Impossible de trouver le conteneur STT")
            print("💡 Essayez avec --host IP_MANUELLE")
            return False
        print(f"✅ Conteneur STT trouvé: {host}")
    
    # URL WebSocket
    ws_url = f"ws://{host}:{port}{STT_PATH}"
    
    print(f"🎤 STT Streaming")
    print(f"Fichier: {wav_path}")
    print(f"URL: {ws_url}")
    print()
    
    # Charger le fichier audio
    try:
        audio_data = load_wav_file(wav_path)
    except Exception as e:
        print(f"❌ Erreur chargement audio: {e}")
        return False
    
    try:
        async with websockets.connect(ws_url, additional_headers=HEADERS) as websocket:
            print("✅ Connexion WebSocket établie")
            
            # Variables pour la transcription
            transcription_words = []
            message_count = 0
            sending_finished = asyncio.Event()
            
            async def send_audio():
                print("📤 Envoi de l'audio par chunks...")
                
                # Attendre Ready avant d'envoyer
                await asyncio.sleep(0.5)
                
                # Envoyer audio par chunks
                total_chunks = len(audio_data) // SAMPLES_PER_FRAME + 1
                for i in range(0, len(audio_data), SAMPLES_PER_FRAME):
                    chunk = audio_data[i:i + SAMPLES_PER_FRAME]
                    
                    # Compléter le dernier chunk si nécessaire
                    if len(chunk) < SAMPLES_PER_FRAME:
                        chunk = np.pad(chunk, (0, SAMPLES_PER_FRAME - len(chunk)))
                    
                    # Message audio
                    message = {
                        "type": "Audio",
                        "pcm": chunk.tolist()
                    }
                    
                    await websocket.send(msgpack.packb(message, use_bin_type=True, use_single_float=True))
                    
                    chunk_num = i // SAMPLES_PER_FRAME + 1
                    print(f"  🎵 Chunk {chunk_num}/{total_chunks}: {len(chunk)} échantillons")
                    
                    # Pause réaliste (simule temps réel)
                    await asyncio.sleep(SAMPLES_PER_FRAME / SAMPLE_RATE)
                
                print("📤 Envoi terminé")
                
                # Envoyer un marker pour signaler la fin
                marker_message = {"type": "Marker", "id": 999}
                await websocket.send(msgpack.packb(marker_message, use_bin_type=True))
                print("📤 Marker de fin envoyé")
                
                # EXACTEMENT comme le backend : envoyer chunks de silence pour forcer le traitement
                print("📤 Envoi de chunks de silence pour forcer le traitement...")
                silence_chunk = np.zeros(SAMPLES_PER_FRAME, dtype=np.float32)
                for i in range(25):  # Comme dans le backend
                    silence_message = {
                        "type": "Audio",
                        "pcm": silence_chunk.tolist()
                    }
                    await websocket.send(msgpack.packb(silence_message, use_bin_type=True, use_single_float=True))
                    await asyncio.sleep(0.01)  # Rapide pour pousser le traitement
                
                print("📤 Chunks de silence envoyés")
            
            async def receive_transcription():
                nonlocal transcription_words, message_count
                print("📥 Réception de la transcription...")
                
                async for response in websocket:
                    message_count += 1
                    
                    try:
                        data = msgpack.unpackb(response)
                        msg_type = data.get('type', 'unknown')
                        
                        if msg_type == 'Ready':
                            print("  ✅ Serveur STT prêt")
                            
                        elif msg_type == 'Word':
                            word = data.get('text', '')
                            start_time = data.get('start_time', 0)
                            transcription_words.append((word, start_time))
                            print(f"  📝 Mot: '{word}' (t={start_time:.2f}s)")
                            
                        elif msg_type == 'EndWord':
                            stop_time = data.get('stop_time', 0)
                            print(f"  ⏹️ Fin de mot (t={stop_time:.2f}s)")
                            
                        elif msg_type == 'Step':
                            step_idx = data.get('step_idx', 0)
                            # Pas besoin d'afficher tous les steps
                            if step_idx % 50 == 0:  # Afficher un step sur 50
                                print(f"  🔄 Step {step_idx}")
                                
                        elif msg_type == 'Marker':
                            marker_id = data.get('id', 0)
                            print(f"  🏁 Marker reçu: {marker_id}")
                            if marker_id == 999:  # Notre marker de fin
                                print("  ✅ Fin de transcription détectée")
                                break
                                
                        elif msg_type == 'Error':
                            error_msg = data.get('message', 'Unknown error')
                            print(f"  ❌ Erreur STT: {error_msg}")
                            return False
                            
                        else:
                            print(f"  ⚠️ Message inconnu: {msg_type}")
                        
                    except Exception as e:
                        print(f"  ❌ Erreur décodage: {e}")
                        
                    # Sécurité
                    if message_count > 10000:
                        print("  ⚠️ Limite de messages atteinte")
                        break
                
                print("  ✅ Réception terminée")
                return True
            
            # Démarrer envoi et réception en parallèle
            send_task = asyncio.create_task(send_audio())
            receive_task = asyncio.create_task(receive_transcription())
            
            # Attendre les deux tâches
            results = await asyncio.gather(send_task, receive_task, return_exceptions=True)
            
            # Afficher la transcription finale
            if transcription_words:
                print(f"\n📝 Transcription finale:")
                print("=" * 50)
                full_text = " ".join(word for word, _ in transcription_words)
                print(full_text)
                print("=" * 50)
                
                print(f"\n📊 Détails:")
                for i, (word, start_time) in enumerate(transcription_words, 1):
                    print(f"  {i:2d}. '{word}' (t={start_time:.2f}s)")
                
                return True
            else:
                print("❌ Aucun mot transcrit")
                return False
                
    except websockets.exceptions.ConnectionClosed as e:
        print(f"❌ Connexion fermée: {e}")
        return False
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Test STT Streaming avec fichier WAV")
    parser.add_argument("wav_file", type=Path, help="Fichier WAV à transcrire")
    parser.add_argument("--host", default=None, help="IP du serveur STT (auto-détecté si non spécifié)")
    parser.add_argument("--port", type=int, default=8080, help="Port du serveur STT")
    
    args = parser.parse_args()
    
    if not args.wav_file.exists():
        print(f"❌ Fichier non trouvé: {args.wav_file}")
        return
    
    if not args.wav_file.suffix.lower() == '.wav':
        print(f"❌ Format non supporté: {args.wav_file.suffix} (utilisez .wav)")
        return
    
    success = asyncio.run(stream_stt_transcription(args.wav_file, args.host, args.port))
    
    if success:
        print(f"\n🎉 Transcription réussie!")
    else:
        print(f"\n💥 Échec de la transcription")

if __name__ == "__main__":
    main()