#!/usr/bin/env python3
"""
Script TTS parfait qui reproduit le protocole backend Python
mais communique DIRECTEMENT avec le docker TTS Rust
"""

import asyncio
import websockets
import msgpack
import argparse
import numpy as np
import wave
import ssl
from pathlib import Path
import urllib.parse
from docker_utils import get_tts_container_ip

def url_escape(value) -> str:
    return urllib.parse.quote(str(value), safe="")

def build_websocket_url(url=None, host=None, port=None):
    """Construit l'URL WebSocket selon le mode d'accès (public ou local)"""
    if url:
        # Mode domaine public via Traefik
        protocol = "wss"  # HTTPS par défaut pour domaines publics
        effective_port = 443 if port is None else port
        base_path = "/tts"  # Route Traefik
        if effective_port == 443:
            return f"{protocol}://{url}{base_path}"
        else:
            return f"{protocol}://{url}:{effective_port}{base_path}"
    else:
        # Mode local/docker direct
        protocol = "ws"
        effective_port = port or 8080
        effective_host = host or get_tts_container_ip()
        base_path = "/api/tts_streaming"  # Route directe TTS
        return f"{protocol}://{effective_host}:{effective_port}{base_path}"

# Messages du protocole backend (reproduits)
class TTSClientTextMessage:
    def __init__(self, text: str):
        self.type = "Text"
        self.text = text
    
    def model_dump(self):
        return {"type": self.type, "text": self.text}

class TTSClientEosMessage:
    def __init__(self):
        self.type = "Eos"
    
    def model_dump(self):
        return {"type": self.type}

async def test_perfect_tts(text: str, output_file: str = "perfect_tts_output.wav", url: str = None, host: str = None, port: int = None):
    """Test TTS en reproduisant exactement le protocole backend"""
    
    # Détection du mode d'accès
    if url:
        print(f"🌐 Utilisation du domaine public: {url}")
        if port is None:
            port = 443  # Port HTTPS par défaut
    elif host is None:
        print("🔍 Détection automatique du conteneur TTS...")
        host = get_tts_container_ip()
        if host is None:
            print("❌ Impossible de trouver le conteneur TTS")
            print("💡 Essayez avec --host IP_MANUELLE ou --url DOMAINE")
            return False
        print(f"✅ Conteneur TTS trouvé: {host}")
        if port is None:
            port = 8080  # Port par défaut pour accès local
    
    # Configuration EXACTE du backend Python
    query_params = {
        "format": "PcmMessagePack",  # ← SECRET !
        "auth_id": "public_token",
        "cfg_alpha": 1.5,  # Comme dans le backend
        "voice": "unmute-prod-website/developpeuse-3.wav"
    }
    
    # URL avec paramètres EXACTEMENT comme le backend
    params_str = "&".join(f"{key}={url_escape(value)}" for key, value in query_params.items())
    ws_url = f"{build_websocket_url(url, host, port)}?{params_str}"
    
    # Headers EXACTEMENT comme le backend
    headers = {"kyutai-api-key": "public_token"}
    
    print(f"🔊 Synthèse TTS Parfaite (Protocol Backend)")
    print(f"Texte: {text}")
    print(f"URL: {ws_url}")
    print(f"Sortie: {output_file}")
    
    try:
        # Configuration SSL pour WSS (domaines publics)
        ssl_context = None
        if ws_url.startswith("wss://"):
            ssl_context = ssl.create_default_context()
        
        async with websockets.connect(ws_url, additional_headers=headers, ssl=ssl_context) as websocket:
            print("✅ Connexion WebSocket établie")
            
            # Collecter les chunks audio PCM
            audio_pcm_chunks = []
            message_count = 0
            
            # Créer des tâches parallèles pour envoi et réception
            async def send_text():
                print(f"📤 Envoi du texte mot par mot (Protocol Backend)...")
                words = text.split()
                for i, word in enumerate(words, 1):
                    print(f"  📝 Mot {i}/{len(words)}: '{word}'")
                    message = TTSClientTextMessage(word)
                    await websocket.send(msgpack.packb(message.model_dump()))
                    await asyncio.sleep(0.1)  # Comme dans le backend
                
                # Signal de fin EOS (comme le backend)
                print(f"📤 Envoi du signal EOS...")
                eos_message = TTSClientEosMessage()
                await websocket.send(msgpack.packb(eos_message.model_dump()))
            
            async def receive_audio():
                nonlocal audio_pcm_chunks, message_count
                print("📥 Réception des messages TTS...")
                
                # Attendre Ready message (comme le backend)
                ready_received = False
                
                async for response in websocket:
                    message_count += 1
                    
                    try:
                        # Décoder MessagePack (comme le backend)
                        data = msgpack.unpackb(response)
                        msg_type = data.get('type', 'unknown')
                        print(f"  📨 Message {message_count}: {msg_type}")
                        
                        if msg_type == 'Ready':
                            print("  ✅ Serveur TTS prêt")
                            ready_received = True
                            
                        elif msg_type == 'Error':
                            print(f"  ❌ Erreur TTS: {data.get('message', 'Unknown error')}")
                            return False
                            
                        elif msg_type == 'Text':
                            text_content = data.get('text', '')
                            start_s = data.get('start_s', 0)
                            stop_s = data.get('stop_s', 0)
                            
                            # Signal de fin spécial détecté (comme le backend ligne 309-310)
                            if text_content == "" and start_s == 0 and stop_s == 0:
                                print("  ✅ Signal de fin détecté (empty text)")
                                break
                            else:
                                print(f"  📝 Texte: '{text_content}' ({start_s:.2f}s-{stop_s:.2f}s)")
                            
                        elif msg_type == 'Audio':
                            pcm_data = data.get('pcm', [])
                            if pcm_data:
                                audio_pcm_chunks.extend(pcm_data)
                                print(f"  🎵 Audio PCM: {len(pcm_data)} échantillons (total: {len(audio_pcm_chunks)})")
                        
                        else:
                            print(f"  ⚠️ Type de message inconnu: {msg_type}")
                        
                    except Exception as e:
                        print(f"  ❌ Erreur décodage: {e}")
                        print(f"  📄 Données brutes: {response[:100] if len(response) > 100 else response}")
                        
                    # Sécurité: limite pour éviter boucle infinie
                    if message_count > 500:
                        print("  ⚠️ Limite de messages atteinte")
                        break
                
                print("  ✅ Connexion fermée - génération terminée")
                return ready_received
            
            # Variables partagées pour synchronisation
            ready_received = asyncio.Event()
            start_sending = asyncio.Event()
            
            async def wait_ready_then_receive():
                nonlocal audio_pcm_chunks, message_count
                print("📥 Purge des messages résiduels (comme le backend)...")
                
                # EXACTEMENT comme le backend : purge d'abord les anciens messages !
                for i in range(10):
                    try:
                        # Utiliser recv(decode=False) comme le backend ligne 228
                        message_bytes = await asyncio.wait_for(websocket.recv(), timeout=0.5)
                        data = msgpack.unpackb(message_bytes)
                        msg_type = data.get('type', 'unknown')
                        print(f"  🗑️ Purge message {i+1}: {msg_type}")
                        
                        if msg_type == 'Ready':
                            print("  ✅ Serveur TTS prêt (après purge)")
                            ready_received.set()
                            start_sending.set()  # Signal pour commencer l'envoi
                            break
                        elif msg_type == 'Error':
                            print(f"  ❌ Erreur TTS: {data.get('message', 'Unknown error')}")
                            return False
                        else:
                            print(f"  🗑️ Message résiduel ignoré: {msg_type}")
                            
                    except asyncio.TimeoutError:
                        print(f"  ⏰ Purge terminée après {i} messages")
                        break
                    except Exception as e:
                        print(f"  ❌ Erreur purge: {e}")
                        break
                
                # Si pas de Ready trouvé pendant la purge, continuer normalement
                if not ready_received.is_set():
                    print("📥 Attente du message Ready...")
                    async for response in websocket:
                        try:
                            data = msgpack.unpackb(response)
                            msg_type = data.get('type', 'unknown')
                            print(f"  📨 Message initial: {msg_type}")
                            
                            if msg_type == 'Ready':
                                print("  ✅ Serveur TTS prêt")
                                ready_received.set()
                                start_sending.set()  # Signal pour commencer l'envoi
                                break
                            elif msg_type == 'Error':
                                print(f"  ❌ Erreur TTS: {data.get('message', 'Unknown error')}")
                                return False
                        except Exception as e:
                            print(f"  ❌ Erreur décodage initial: {e}")
                
                # Deuxième étape : recevoir l'audio en continu
                print("📥 Réception des messages TTS en temps réel...")
                async for response in websocket:
                    message_count += 1
                    
                    try:
                        data = msgpack.unpackb(response)
                        msg_type = data.get('type', 'unknown')
                        print(f"  📨 Message {message_count}: {msg_type}")
                        
                        if msg_type == 'Error':
                            print(f"  ❌ Erreur TTS: {data.get('message', 'Unknown error')}")
                            return False
                            
                        elif msg_type == 'Text':
                            text_content = data.get('text', '')
                            start_s = data.get('start_s', 0)
                            stop_s = data.get('stop_s', 0)
                            
                            # Signal de fin spécial détecté
                            if text_content == "" and start_s == 0 and stop_s == 0:
                                print("  ✅ Signal de fin détecté (empty text)")
                                break
                            else:
                                print(f"  📝 Texte: '{text_content}' ({start_s:.2f}s-{stop_s:.2f}s)")
                            
                        elif msg_type == 'Audio':
                            pcm_data = data.get('pcm', [])
                            if pcm_data:
                                audio_pcm_chunks.extend(pcm_data)
                                print(f"  🎵 Audio PCM: {len(pcm_data)} échantillons (total: {len(audio_pcm_chunks)})")
                        
                        else:
                            print(f"  ⚠️ Type de message inconnu: {msg_type}")
                        
                    except Exception as e:
                        print(f"  ❌ Erreur décodage: {e}")
                        
                    # Sécurité: limite pour éviter boucle infinie
                    if message_count > 500:
                        print("  ⚠️ Limite de messages atteinte")
                        break
                
                print("  ✅ Réception terminée")
                return True
            
            async def send_when_ready():
                # Attendre que le serveur soit prêt
                await start_sending.wait()
                
                print(f"📤 Envoi du texte mot par mot (temps réel)...")
                words = text.split()
                for i, word in enumerate(words, 1):
                    print(f"  📝 Mot {i}/{len(words)}: '{word}'")
                    message = TTSClientTextMessage(word)
                    await websocket.send(msgpack.packb(message.model_dump()))
                    await asyncio.sleep(0.1)  # Comme dans le backend
                
                # Signal de fin EOS
                print(f"📤 Envoi du signal EOS...")
                eos_message = TTSClientEosMessage()
                await websocket.send(msgpack.packb(eos_message.model_dump()))
            
            # Démarrer les deux tâches en parallèle dès la connexion
            receive_task = asyncio.create_task(wait_ready_then_receive())
            send_task = asyncio.create_task(send_when_ready())
            
            # Attendre que les deux tâches se terminent
            results = await asyncio.gather(send_task, receive_task, return_exceptions=True)
            
            # Convertir les données PCM en fichier audio (comme le backend)
            if audio_pcm_chunks:
                output_path = Path(output_file)
                
                # Convertir en numpy array
                audio_array = np.array(audio_pcm_chunks, dtype=np.float32)
                
                # Convertir float32 [-1,1] vers int16 pour WAV
                audio_int16 = (audio_array * 32767).astype(np.int16)
                
                # Sauvegarder en WAV (24kHz échantillonnage comme le backend)
                sample_rate = 24000
                with wave.open(str(output_path), 'wb') as wav_file:
                    wav_file.setnchannels(1)  # Mono
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(sample_rate)
                    wav_file.writeframes(audio_int16.tobytes())
                
                print(f"✅ Audio sauvegardé: {output_path} ({len(audio_pcm_chunks)} échantillons)")
                
                # Informations sur l'audio
                duration_s = len(audio_pcm_chunks) / sample_rate
                print(f"  🎵 Durée: {duration_s:.2f} secondes")
                print(f"  🎵 Échantillonnage: {sample_rate} Hz")
                print(f"  🎵 Protocol: Backend Python → Docker TTS Rust")
                
                return True
            else:
                print("❌ Aucune donnée audio reçue")
                return False
                
    except websockets.exceptions.ConnectionClosed as e:
        print(f"❌ Connexion fermée: {e}")
        return False
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Test TTS Perfect (Backend Protocol)")
    parser.add_argument("text", nargs="?", help="Texte à synthétiser")
    parser.add_argument("--output", "-o", default="perfect_tts_output.wav", help="Fichier de sortie")
    parser.add_argument("--url", help="URL publique (ex: caronboulme.freeboxos.fr)")
    parser.add_argument("--host", default=None, help="IP du docker TTS (auto-détecté si non spécifié)")
    parser.add_argument("--port", type=int, default=None, help="Port (443 pour URL publique, 8080 pour local)")
    
    args = parser.parse_args()
    
    if args.text:
        success = asyncio.run(test_perfect_tts(args.text, args.output, args.url, args.host, args.port))
        if success:
            print(f"\n🎉 Succès parfait! Écoutez le résultat: {args.output}")
        else:
            print(f"\n💥 Échec de la synthèse vocale")
    else:
        # Test par défaut
        default_text = "Je suis triste car mon chien est mort"
        success = asyncio.run(test_perfect_tts(default_text, args.output, args.url, args.host, args.port))
        if success:
            print(f"\n🎉 Succès parfait! Écoutez le résultat: {args.output}")

if __name__ == "__main__":
    main()