import httpx
from typing import Dict, Any
from .base import BaseTool

class WeatherTool(BaseTool):
    """Outil pour obtenir la météo via Open-Meteo API"""
    
    @property
    def name(self) -> str:
        return "get_weather"
    
    @property
    def description(self) -> str:
        return "Obtient les informations météorologiques actuelles pour une ville via Open-Meteo"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "Le nom de la ville (ex: Paris, Londres, New York)"
                }
            },
            "required": ["city"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        """Récupère la météo pour une ville via Open-Meteo API"""
        city = kwargs.get("city")
        if not city:
            return "Erreur: paramètre 'city' manquant"
        try:
            async with httpx.AsyncClient() as client:
                # 1. Géocodage pour obtenir les coordonnées
                geocoding_response = await client.get(
                    "https://geocoding-api.open-meteo.com/v1/search",
                    params={"name": city, "count": 1, "language": "fr", "format": "json"}
                )
                
                if geocoding_response.status_code != 200:
                    return f"Impossible de localiser {city}"
                    
                geocoding_data = geocoding_response.json()
                
                if not geocoding_data.get("results"):
                    return f"Ville '{city}' non trouvée"
                
                location = geocoding_data["results"][0]
                lat = location["latitude"]
                lon = location["longitude"]
                country = location.get("country", "")
                
                # 2. Récupération de la météo actuelle
                weather_response = await client.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": lat,
                        "longitude": lon,
                        "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                        "timezone": "Europe/Paris",
                        "forecast_days": 1
                    }
                )
                
                if weather_response.status_code != 200:
                    return f"Impossible d'obtenir la météo pour {city}"
                
                weather_data = weather_response.json()
                current = weather_data["current"]
                
                # Codes météo Open-Meteo vers descriptions
                weather_codes = {
                    0: "Ciel dégagé",
                    1: "Principalement dégagé", 2: "Partiellement nuageux", 3: "Couvert",
                    45: "Brouillard", 48: "Brouillard givrant",
                    51: "Bruine légère", 53: "Bruine modérée", 55: "Bruine forte",
                    61: "Pluie légère", 63: "Pluie modérée", 65: "Pluie forte",
                    71: "Neige légère", 73: "Neige modérée", 75: "Neige forte",
                    95: "Orage", 96: "Orage avec grêle légère", 99: "Orage avec grêle forte"
                }
                
                temp = current["temperature_2m"]
                humidity = current["relative_humidity_2m"]
                wind_speed = current["wind_speed_10m"]
                weather_desc = weather_codes.get(current["weather_code"], "Condition inconnue")
                
                return f"À {city} ({country}): {temp}°C, {weather_desc}. Humidité: {humidity}%, Vent: {wind_speed} km/h"
                
        except Exception as e:
            return f"Erreur lors de la récupération de la météo pour {city}: {e}"