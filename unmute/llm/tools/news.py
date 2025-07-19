"""
Tool pour rechercher des actualités avec NewsAPI.
Utilise l'API complète NewsAPI.org avec support français/anglais.
"""

import os
import logging
from typing import Dict, Any
import httpx

from .base import BaseTool

logger = logging.getLogger(__name__)

# Réutilise la même clé API que le système existant
NEWSAPI_API_KEY = os.environ.get("NEWSAPI_API_KEY")

class NewsTool(BaseTool):
    """Tool pour rechercher des actualités avec NewsAPI"""
    
    @property
    def name(self) -> str:
        return "search_news"
    
    @property
    def description(self) -> str:
        return """Recherche des actualités récentes avec NewsAPI.
        
        Peut rechercher par:
        - Mots-clés spécifiques (ex: "intelligence artificielle", "Tesla", "climat")
        - Catégorie (technologie, business, santé, science, sports, etc.)
        - Pays (France, USA, UK) 
        - Langue (français ou anglais)
        
        Exemples d'usage:
        - Actualités tech françaises
        - News récentes sur l'IA
        - Headlines business américaines
        - Actualités sportives
        """
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Mots-clés à rechercher dans les actualités"
                },
                "language": {
                    "type": "string",
                    "enum": ["fr", "en"],
                    "default": "fr",
                    "description": "Langue des actualités (fr=français, en=anglais)"
                },
                "category": {
                    "type": "string",
                    "enum": ["general", "business", "technology", "health", "science", "sports", "entertainment"],
                    "description": "Catégorie d'actualités (optionnel)"
                },
                "country": {
                    "type": "string", 
                    "enum": ["fr", "us", "gb"],
                    "description": "Pays pour les headlines (fr=France, us=USA, gb=UK)"
                },
                "max_articles": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 5,
                    "description": "Nombre maximum d'articles à retourner (1-10)"
                }
            },
            "required": ["query"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        """Recherche des actualités avec NewsAPI"""
        
        if not NEWSAPI_API_KEY:
            return "❌ Erreur: Clé API NewsAPI non configurée. Ajoutez NEWSAPI_API_KEY dans votre fichier .env"
        
        # Extraire les paramètres
        query = kwargs.get("query", "")
        language = kwargs.get("language", "fr")
        category = kwargs.get("category")
        country = kwargs.get("country")
        max_articles = kwargs.get("max_articles", 5)
        
        # Validation des paramètres
        max_articles = min(max(max_articles, 1), 10)  # Entre 1 et 10
        
        try:
            # Choisir l'endpoint selon les paramètres
            if country and not query:
                # Headlines par pays
                articles = await self._get_headlines_by_country(country, category, language, max_articles)
            elif category and not country:
                # News par catégorie
                articles = await self._search_by_category(query, category, language, max_articles)
            else:
                # Recherche générale
                articles = await self._search_everything(query, language, max_articles)
            
            if not articles:
                return f"Aucune actualité trouvée pour: {query}"
            
            # Formater la réponse
            result = f"📰 Actualités ({len(articles)} résultat{'s' if len(articles) > 1 else ''}):\n\n"
            
            for i, article in enumerate(articles, 1):
                title = article.get('title', 'Titre non disponible')
                description = article.get('description', '')
                source = article.get('source', {}).get('name', 'Source inconnue')
                published = article.get('publishedAt', '')[:10]  # Date seulement
                
                result += f"{i}. **{title}**\n"
                result += f"   📅 {published} - 📺 {source}\n"
                if description:
                    # Limiter la description à 150 caractères
                    desc_short = description[:150] + "..." if len(description) > 150 else description
                    result += f"   📝 {desc_short}\n"
                result += "\n"
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur NewsAPI: {e}")
            return f"❌ Erreur lors de la recherche d'actualités: {str(e)}"
    
    def _get_headers(self):
        """Headers pour l'API NewsAPI"""
        return {
            "Authorization": f"Bearer {NEWSAPI_API_KEY}",
            "User-Agent": "Unmute/1.0"
        }
    
    async def _search_everything(self, query: str, language: str, max_articles: int) -> list:
        """Recherche dans toutes les actualités"""
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "language": language,
            "sortBy": "publishedAt",  # Plus récentes en premier
            "pageSize": max_articles
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            data = response.json()
            
            return data.get('articles', [])
    
    async def _get_headlines_by_country(self, country: str, category: str | None, language: str, max_articles: int) -> list:
        """Récupère les headlines par pays"""
        url = "https://newsapi.org/v2/top-headlines"
        params = {
            "country": country,
            "pageSize": max_articles
        }
        
        if category:
            params["category"] = category
            
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            data = response.json()
            
            return data.get('articles', [])
    
    async def _search_by_category(self, query: str, category: str | None, language: str, max_articles: int) -> list:
        """Recherche par catégorie"""
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query if query else category,  # Si pas de query, utiliser la catégorie
            "language": language,
            "sortBy": "popularity",
            "pageSize": max_articles
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            data = response.json()
            
            return data.get('articles', [])

# Test rapide du tool
if __name__ == "__main__":
    import asyncio
    
    async def test_news_tool():
        tool = NewsTool()
        
        # Test avec des exemples
        test_cases = [
            {"query": "intelligence artificielle", "language": "fr"},
            {"query": "Tesla", "language": "en", "max_articles": 3},
            {"query": "climat", "category": "science", "language": "fr"}
        ]
        
        for test in test_cases:
            print(f"\n🧪 Test: {test}")
            print("=" * 50)
            result = await tool.execute(**test)
            print(result)
            print()
    
    asyncio.run(test_news_tool())