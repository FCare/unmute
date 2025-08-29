#!/usr/bin/env python3
"""
Utilitaires pour détecter automatiquement les IPs des conteneurs Docker
"""

import subprocess
import json
import re
from typing import Optional

def get_container_ip(container_name: str) -> Optional[str]:
    """Récupère l'IP d'un conteneur Docker par son nom"""
    try:
        # Exécuter docker inspect
        result = subprocess.run(
            ["docker", "inspect", container_name],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parser le JSON
        data = json.loads(result.stdout)
        if not data:
            return None
            
        container_info = data[0]
        
        # Récupérer l'IP depuis les réseaux
        networks = container_info.get("NetworkSettings", {}).get("Networks", {})
        for network_name, network_info in networks.items():
            ip = network_info.get("IPAddress")
            if ip:
                return ip
                
        return None
        
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError, IndexError):
        return None

def get_tts_container_ip() -> Optional[str]:
    """Récupère l'IP du conteneur TTS"""
    # Essayer différents noms possibles
    possible_names = [
        "unmute-tts-1",
        "unmute_tts_1", 
        "tts",
        "moshi-server-tts"
    ]
    
    for name in possible_names:
        ip = get_container_ip(name)
        if ip:
            return ip
    
    return None

def get_stt_container_ip() -> Optional[str]:
    """Récupère l'IP du conteneur STT"""
    # Essayer différents noms possibles
    possible_names = [
        "unmute-stt-1",
        "unmute_stt_1",
        "stt", 
        "moshi-server-stt"
    ]
    
    for name in possible_names:
        ip = get_container_ip(name)
        if ip:
            return ip
    
    return None

def discover_service_endpoints():
    """Découvre automatiquement les endpoints TTS et STT"""
    endpoints = {}
    
    # TTS
    tts_ip = get_tts_container_ip()
    if tts_ip:
        endpoints["tts"] = {
            "ip": tts_ip,
            "port": 8080,
            "url": f"ws://{tts_ip}:8080/api/tts_streaming"
        }
    
    # STT  
    stt_ip = get_stt_container_ip()
    if stt_ip:
        endpoints["stt"] = {
            "ip": stt_ip, 
            "port": 8080,
            "url": f"ws://{stt_ip}:8080/api/asr-streaming"
        }
    
    return endpoints

if __name__ == "__main__":
    print("🔍 Découverte des services Docker...")
    endpoints = discover_service_endpoints()
    
    if endpoints:
        for service, info in endpoints.items():
            print(f"  {service.upper()}: {info['url']}")
    else:
        print("  ❌ Aucun service trouvé")