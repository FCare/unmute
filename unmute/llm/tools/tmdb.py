"""
Tool pour rechercher des films, séries et acteurs avec TMDB API.
API avec clé requise, support français natif.
"""

import os
import logging
from typing import Dict, Any
import httpx

from .base import BaseTool

logger = logging.getLogger(__name__)

# Clé API TMDB depuis .env
TMDB_API_KEY = os.environ.get("TMDB_API_KEY")
TMDB_BASE_URL = "https://api.themoviedb.org/3"

class TMDBTool(BaseTool):
    """Tool pour rechercher des films, séries et acteurs via TMDB API"""
    
    @property
    def name(self) -> str:
        return "search_movies_tv"
    
    @property
    def description(self) -> str:
        return """Recherche d'informations sur les films, séries TV et acteurs via TMDB.
        
        🎬 Types de recherche supportés :
        1. Films : Recherche par titre, infos détaillées (synopsis, cast, notes, année)
        2. Séries TV : Recherche par nom, infos complètes (épisodes, saisons, cast)
        3. Acteurs : Recherche personnalités, filmographie, biographie
        4. Découverte : Films/séries populaires, tendances du moment, mieux notés
        
        📊 Informations retournées :
        - Titre original et français (si disponible)
        - Synopsis complet en français
        - Note moyenne et nombre de votes
        - Date de sortie / première diffusion
        - Genres, pays d'origine, langue
        - Cast principal (acteurs, réalisateur)
        - Durée (films) ou nombre de saisons (séries)
        - Budget et box-office (si disponible)
        
        🌍 Support multilingue natif :
        L'API TMDB supporte le français directement, pas besoin de traduction.
        Les synopsis, titres et descriptions sont récupérés en français.
        
        💡 Exemples d'usage :
        - "Infos sur le film Inception"
        - "Nouvelle saison de Stranger Things" 
        - "Filmographie de Leonardo DiCaprio"
        - "Films populaires en ce moment"
        - "Quels sont les films tendance ?"
        """
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "search_type": {
                    "type": "string",
                    "enum": ["movie", "tv", "person", "popular_movies", "popular_tv", "trending"],
                    "description": "Type de recherche : movie (films), tv (séries), person (acteurs), popular_movies, popular_tv, trending (tendances)"
                },
                "query": {
                    "type": "string",
                    "description": "Terme de recherche (titre du film/série, nom de l'acteur). Laisser vide pour popular/trending."
                },
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "default": 3,
                    "description": "Nombre maximum de résultats à retourner"
                }
            },
            "required": ["search_type"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        """Recherche avec TMDB API"""
        
        if not TMDB_API_KEY:
            return "❌ Erreur: Clé API TMDB non configurée. Ajoutez TMDB_API_KEY dans votre fichier .env\n🔑 Obtenez votre clé sur: https://www.themoviedb.org/settings/api"
        
        search_type = kwargs.get("search_type", "movie")
        query = kwargs.get("query", "")
        max_results = kwargs.get("max_results", 3)
        
        # Validation
        max_results = min(max(max_results, 1), 5)
        
        try:
            # Choisir l'endpoint selon le type
            if search_type == "movie":
                if not query:
                    return "❌ Une recherche de film nécessite un titre"
                results = await self._search_movies(query, max_results)
            elif search_type == "tv":
                if not query:
                    return "❌ Une recherche de série nécessite un nom"
                results = await self._search_tv(query, max_results)
            elif search_type == "person":
                if not query:
                    return "❌ Une recherche d'acteur nécessite un nom"
                results = await self._search_person(query, max_results)
            elif search_type == "popular_movies":
                results = await self._get_popular_movies(max_results)
            elif search_type == "popular_tv":
                results = await self._get_popular_tv(max_results)
            elif search_type == "trending":
                results = await self._get_trending(max_results)
            else:
                return "❌ Type de recherche non supporté"
            
            if not results:
                return f"Aucun résultat trouvé pour: {query}" if query else "Aucun résultat trouvé"
            
            # Formater selon le type
            if search_type == "person":
                return await self._format_persons(results)
            else:
                return await self._format_movies_tv(results, search_type)
            
        except Exception as e:
            logger.error(f"Erreur TMDB API: {e}")
            return f"❌ Erreur lors de la recherche TMDB: {str(e)}"
    
    def _get_headers(self) -> dict:
        """Headers pour l'API TMDB"""
        return {
            "Authorization": f"Bearer {TMDB_API_KEY}",
            "Content-Type": "application/json"
        }
    
    async def _search_movies(self, query: str, max_results: int) -> list:
        """Recherche de films"""
        url = f"{TMDB_BASE_URL}/search/movie"
        params = {
            "query": query,
            "language": "fr-FR",
            "page": 1
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            data = response.json()
            
            results = data.get('results', [])
            return results[:max_results]
    
    async def _search_tv(self, query: str, max_results: int) -> list:
        """Recherche de séries TV"""
        url = f"{TMDB_BASE_URL}/search/tv"
        params = {
            "query": query,
            "language": "fr-FR",
            "page": 1
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            data = response.json()
            
            results = data.get('results', [])
            return results[:max_results]
    
    async def _search_person(self, query: str, max_results: int) -> list:
        """Recherche d'acteurs/personnalités"""
        url = f"{TMDB_BASE_URL}/search/person"
        params = {
            "query": query,
            "language": "fr-FR",
            "page": 1
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            data = response.json()
            
            results = data.get('results', [])
            return results[:max_results]
    
    async def _get_popular_movies(self, max_results: int) -> list:
        """Films populaires"""
        url = f"{TMDB_BASE_URL}/movie/popular"
        params = {
            "language": "fr-FR",
            "page": 1
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            data = response.json()
            
            results = data.get('results', [])
            return results[:max_results]
    
    async def _get_popular_tv(self, max_results: int) -> list:
        """Séries populaires"""
        url = f"{TMDB_BASE_URL}/tv/popular"
        params = {
            "language": "fr-FR",
            "page": 1
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            data = response.json()
            
            results = data.get('results', [])
            return results[:max_results]
    
    async def _get_trending(self, max_results: int) -> list:
        """Tendances du jour"""
        url = f"{TMDB_BASE_URL}/trending/all/day"
        params = {
            "language": "fr-FR"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            data = response.json()
            
            results = data.get('results', [])
            return results[:max_results]
    
    async def _format_movies_tv(self, results: list, search_type: str) -> str:
        """Formate les résultats films/séries"""
        if "movie" in search_type or search_type == "trending":
            title = "🎬 **Films trouvés**"
        else:
            title = "📺 **Séries trouvées**"
        
        result_text = f"{title} ({len(results)} résultat{'s' if len(results) > 1 else ''}):\n\n"
        
        for i, item in enumerate(results, 1):
            # Déterminer le type d'item (film ou série)
            is_movie = 'title' in item or item.get('media_type') == 'movie'
            
            if is_movie:
                title = item.get('title', 'Titre inconnu')
                date = item.get('release_date', '')
                duration_info = ""
            else:
                title = item.get('name', 'Titre inconnu')
                date = item.get('first_air_date', '')
                duration_info = ""
            
            overview = item.get('overview', 'Synopsis non disponible')
            vote_average = item.get('vote_average', 0)
            vote_count = item.get('vote_count', 0)
            genres = item.get('genre_ids', [])
            original_title = item.get('original_title') or item.get('original_name', '')
            
            result_text += f"🎭 **{i}. {title}**"
            
            if original_title and original_title != title:
                result_text += f" *(titre original: {original_title})*"
            
            result_text += "\n"
            
            # Date et note
            if date:
                year = date[:4] if date else ""
                result_text += f"📅 **Année :** {year}\n"
            
            if vote_average > 0:
                stars = "⭐" * min(int(vote_average / 2), 5)
                result_text += f"⭐ **Note :** {vote_average:.1f}/10 {stars} ({vote_count:,} votes)\n"
            
            # Synopsis
            if overview:
                # Limiter le synopsis pour éviter texte trop long pour TTS
                synopsis_short = overview[:300] + "..." if len(overview) > 300 else overview
                result_text += f"📖 **Synopsis :** {synopsis_short}\n"
            
            result_text += "\n" + "─" * 40 + "\n\n"
        
        return result_text
    
    async def _format_persons(self, results: list) -> str:
        """Formate les résultats acteurs"""
        result_text = f"🎭 **Acteurs/Personnalités trouvés** ({len(results)} résultat{'s' if len(results) > 1 else ''}):\n\n"
        
        for i, person in enumerate(results, 1):
            name = person.get('name', 'Nom inconnu')
            known_for_department = person.get('known_for_department', '')
            popularity = person.get('popularity', 0)
            known_for = person.get('known_for', [])
            
            result_text += f"🎭 **{i}. {name}**\n"
            
            if known_for_department:
                dept_fr = {
                    'Acting': 'Acteur/Actrice',
                    'Directing': 'Réalisateur/Réalisatrice', 
                    'Writing': 'Scénariste',
                    'Production': 'Producteur/Productrice'
                }.get(known_for_department, known_for_department)
                result_text += f"🎬 **Métier :** {dept_fr}\n"
            
            if popularity > 0:
                result_text += f"📊 **Popularité :** {popularity:.1f}\n"
            
            # Films/séries connues
            if known_for:
                titles = []
                for work in known_for[:3]:  # Top 3
                    title = work.get('title') or work.get('name', '')
                    if title:
                        year = ""
                        if work.get('release_date'):
                            year = f" ({work['release_date'][:4]})"
                        elif work.get('first_air_date'):
                            year = f" ({work['first_air_date'][:4]})"
                        titles.append(f"{title}{year}")
                
                if titles:
                    result_text += f"🌟 **Connu pour :** {', '.join(titles)}\n"
            
            result_text += "\n" + "─" * 40 + "\n\n"
        
        return result_text

# Test du tool
if __name__ == "__main__":
    import asyncio
    
    async def test_tmdb_tool():
        tool = TMDBTool()
        
        test_cases = [
            {"search_type": "movie", "query": "Inception", "max_results": 1},
            {"search_type": "tv", "query": "Breaking Bad", "max_results": 1},
            {"search_type": "person", "query": "Leonardo DiCaprio", "max_results": 1},
            {"search_type": "trending", "max_results": 2}
        ]
        
        for test in test_cases:
            print(f"\n🧪 Test: {test}")
            print("=" * 60)
            result = await tool.execute(**test)
            print(result)
            print()
    
    asyncio.run(test_tmdb_tool())