"""
Tool TMDB complet avec API complète pour films, séries, acteurs et comptes utilisateur.
Inclut filmographie, détails complets, gestion des comptes et toutes les fonctionnalités TMDB.
"""

import os
import logging
from typing import Dict, Any, List
import httpx
from datetime import datetime

from .base import BaseTool

logger = logging.getLogger(__name__)

# Configuration API TMDB
TMDB_API_KEY = os.environ.get("TMDB_API_KEY")
TMDB_BASE_URL = "https://api.themoviedb.org/3"

class TMDBTool(BaseTool):
    """Tool complet pour l'API TMDB - Films, Séries, Acteurs, Comptes utilisateur"""
    
    @property
    def name(self) -> str:
        return "search_movies_tv_complete"
    
    @property
    def description(self) -> str:
        return """🎬 API TMDB complète pour films, séries TV, acteurs et comptes utilisateur.
        
        🔍 **Types de recherche disponibles :**
        
        **RECHERCHE GÉNÉRALE :**
        - `movie` : Recherche de films par titre
        - `tv` : Recherche de séries TV par nom  
        - `person` : Recherche d'acteurs/personnalités
        - `multi` : Recherche mixte (films + séries + personnes)
        
        **DÉCOUVERTE :**
        - `popular_movies` : Films populaires du moment
        - `popular_tv` : Séries populaires du moment
        - `trending` : Tendances du jour (tous types)
        - `top_rated_movies` : Films les mieux notés
        - `top_rated_tv` : Séries les mieux notées
        
        **DÉTAILS COMPLETS :**
        - `movie_details` : Détails complets d'un film (avec cast, équipe, budget, etc.)
        - `tv_details` : Détails complets d'une série (saisons, épisodes, cast, etc.)
        - `person_details` : Biographie complète d'une personne
        - `person_filmography` : Filmographie complète d'un acteur/réalisateur
        
        **GESTION DE COMPTE UTILISATEUR :**
        - `account_details` : Détails du compte utilisateur
        - `account_favorites_movies` : Films favoris du compte
        - `account_favorites_tv` : Séries favorites du compte
        - `account_watchlist_movies` : Films en watchlist
        - `account_watchlist_tv` : Séries en watchlist
        - `account_rated_movies` : Films notés par l'utilisateur
        - `account_rated_tv` : Séries notées par l'utilisateur
        - `account_lists` : Listes personnalisées du compte
        
        🌟 **Exemples d'usage :**
        - "Quel est le dernier film de Christopher Nolan ?" → person_filmography
        - "Détails complets du film Inception" → movie_details  
        - "Mes films favoris" → account_favorites_movies
        - "Films populaires en ce moment" → popular_movies
        - "Filmographie de Leonardo DiCaprio" → person_filmography
        
        🎯 **Fonctionnalités avancées :**
        - Support français natif (titres, synopsis, genres)
        - Cast et équipe technique complète
        - Budgets, box-office, durées
        - Notes et critiques utilisateurs
        - Gestion complète des comptes TMDB
        - Tri par date de sortie pour la filmographie
        """
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "search_type": {
                    "type": "string",
                    "enum": [
                        # Recherche générale
                        "movie", "tv", "person", "multi",
                        # Découverte
                        "popular_movies", "popular_tv", "trending", "top_rated_movies", "top_rated_tv",
                        # Détails complets
                        "movie_details", "tv_details", "person_details", "person_filmography",
                        # Comptes utilisateur
                        "account_details", "account_favorites_movies", "account_favorites_tv",
                        "account_watchlist_movies", "account_watchlist_tv", "account_rated_movies", 
                        "account_rated_tv", "account_lists"
                    ],
                    "description": "Type de recherche TMDB à effectuer"
                },
                "query": {
                    "type": "string", 
                    "description": "Terme de recherche (titre, nom d'acteur, etc.). Requis pour les recherches, optionnel pour découverte/tendances."
                },
                "tmdb_id": {
                    "type": "integer",
                    "description": "ID TMDB spécifique pour les détails complets (film_id, tv_id, person_id)"
                },
                "account_id": {
                    "type": "integer", 
                    "description": "ID du compte TMDB pour les fonctionnalités de compte"
                },
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 5,
                    "description": "Nombre maximum de résultats (1-10)"
                }
            },
            "required": ["search_type"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        """Exécute la recherche TMDB selon le type demandé"""
        
        if not TMDB_API_KEY:
            return "❌ **Erreur de configuration**\n\n🔑 Clé API TMDB manquante. Ajoutez `TMDB_API_KEY` dans votre fichier `.env`\n\n📖 **Obtenir une clé :** https://www.themoviedb.org/settings/api"
        
        search_type = kwargs.get("search_type")
        query = kwargs.get("query", "").strip()
        tmdb_id = kwargs.get("tmdb_id")
        account_id = kwargs.get("account_id")
        max_results = min(max(kwargs.get("max_results", 5), 1), 10)
        
        if not search_type:
            return "❌ Le paramètre 'search_type' est requis"
        
        try:
            # Router selon le type de recherche
            if search_type in ["movie", "tv", "person", "multi"]:
                if not query:
                    return f"❌ Une recherche de type '{search_type}' nécessite un terme de recherche"
                return await self._search_content(search_type, query, max_results)
            
            elif search_type in ["popular_movies", "popular_tv", "trending", "top_rated_movies", "top_rated_tv"]:
                return await self._get_discovery_content(search_type, max_results)
            
            elif search_type in ["movie_details", "tv_details", "person_details"]:
                if not tmdb_id:
                    return f"❌ Les détails complets nécessitent un tmdb_id"
                return await self._get_detailed_content(search_type, tmdb_id)
            
            elif search_type == "person_filmography":
                if tmdb_id:
                    return await self._get_person_filmography(tmdb_id, max_results)
                elif query:
                    # Rechercher la personne d'abord, puis sa filmographie
                    return await self._search_and_get_filmography(query, max_results)
                else:
                    return "❌ La filmographie nécessite soit un tmdb_id soit le nom de la personne"
            
            elif search_type.startswith("account_"):
                if not account_id:
                    return f"❌ Les fonctionnalités de compte nécessitent un account_id"
                return await self._get_account_content(search_type, account_id, max_results)
            
            else:
                return f"❌ Type de recherche non supporté : {search_type}"
                
        except Exception as e:
            logger.error(f"Erreur TMDB API: {e}")
            return f"❌ **Erreur TMDB API**\n\n🔍 Type: {search_type}\n📝 Détail: {str(e)}"
    
    def _get_headers(self) -> dict:
        """Headers pour authentification TMDB"""
        return {
            "Authorization": f"Bearer {TMDB_API_KEY}",
            "Content-Type": "application/json"
        }
    
    async def _search_content(self, search_type: str, query: str, max_results: int) -> str:
        """Recherche de contenu général"""
        endpoint_map = {
            "movie": "/search/movie",
            "tv": "/search/tv", 
            "person": "/search/person",
            "multi": "/search/multi"
        }
        
        url = f"{TMDB_BASE_URL}{endpoint_map[search_type]}"
        params = {
            "query": query,
            "language": "fr-FR",
            "page": 1
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            data = response.json()
            
            results = data.get('results', [])[:max_results]
            
            if not results:
                return f"🔍 **Aucun résultat trouvé**\n\nRecherche '{search_type}' pour : `{query}`"
            
            return await self._format_search_results(results, search_type, query)
    
    async def _get_discovery_content(self, search_type: str, max_results: int) -> str:
        """Contenu de découverte (populaire, tendances, etc.)"""
        endpoint_map = {
            "popular_movies": "/movie/popular",
            "popular_tv": "/tv/popular",
            "trending": "/trending/all/day",
            "top_rated_movies": "/movie/top_rated", 
            "top_rated_tv": "/tv/top_rated"
        }
        
        url = f"{TMDB_BASE_URL}{endpoint_map[search_type]}"
        params = {"language": "fr-FR", "page": 1}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            data = response.json()
            
            results = data.get('results', [])[:max_results]
            return await self._format_discovery_results(results, search_type)
    
    async def _get_detailed_content(self, search_type: str, tmdb_id: int) -> str:
        """Détails complets d'un élément"""
        if search_type == "movie_details":
            return await self._get_movie_details(tmdb_id)
        elif search_type == "tv_details":
            return await self._get_tv_details(tmdb_id)
        elif search_type == "person_details":
            return await self._get_person_details(tmdb_id)
        else:
            return f"❌ Type de détails non supporté : {search_type}"
    
    async def _get_movie_details(self, movie_id: int) -> str:
        """Détails complets d'un film"""
        url = f"{TMDB_BASE_URL}/movie/{movie_id}"
        params = {
            "language": "fr-FR",
            "append_to_response": "credits,videos,keywords,release_dates"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            movie = response.json()
            
            return await self._format_movie_details(movie)
    
    async def _get_tv_details(self, tv_id: int) -> str:
        """Détails complets d'une série"""
        url = f"{TMDB_BASE_URL}/tv/{tv_id}"
        params = {
            "language": "fr-FR",
            "append_to_response": "credits,videos,keywords,content_ratings"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            tv = response.json()
            
            return await self._format_tv_details(tv)
    
    async def _get_person_details(self, person_id: int) -> str:
        """Détails complets d'une personne"""
        url = f"{TMDB_BASE_URL}/person/{person_id}"
        params = {
            "language": "fr-FR",
            "append_to_response": "movie_credits,tv_credits,external_ids"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            person = response.json()
            
            return await self._format_person_details(person)
    
    async def _search_and_get_filmography(self, person_name: str, max_results: int) -> str:
        """Recherche une personne et retourne sa filmographie"""
        # D'abord rechercher la personne
        search_url = f"{TMDB_BASE_URL}/search/person"
        search_params = {
            "query": person_name,
            "language": "fr-FR"
        }
        
        async with httpx.AsyncClient() as client:
            search_response = await client.get(search_url, headers=self._get_headers(), params=search_params)
            search_response.raise_for_status()
            search_data = search_response.json()
            
            persons = search_data.get('results', [])
            if not persons:
                return f"🔍 **Personne non trouvée**\n\nAucun résultat pour : `{person_name}`"
            
            # Prendre la première personne trouvée
            person = persons[0]
            person_id = person['id']
            person_name_found = person['name']
            
            # Obtenir sa filmographie
            filmography = await self._get_person_filmography(person_id, max_results)
            
            return f"🎭 **Filmographie de {person_name_found}**\n\n{filmography}"
    
    async def _get_person_filmography(self, person_id: int, max_results: int) -> str:
        """Filmographie complète d'une personne"""
        url = f"{TMDB_BASE_URL}/person/{person_id}/movie_credits"
        params = {"language": "fr-FR"}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            data = response.json()
            
            # Combiner cast et crew
            all_movies = []
            
            # Films où la personne joue
            for movie in data.get('cast', []):
                movie['role_type'] = 'acting'
                movie['role_detail'] = movie.get('character', 'Acteur/Actrice')
                all_movies.append(movie)
            
            # Films où la personne fait partie de l'équipe technique
            for movie in data.get('crew', []):
                movie['role_type'] = 'crew'
                movie['role_detail'] = movie.get('job', 'Équipe technique')
                all_movies.append(movie)
            
            # Supprimer les doublons et trier par date de sortie (plus récent en premier)
            unique_movies = {}
            for movie in all_movies:
                movie_id = movie['id']
                if movie_id not in unique_movies:
                    unique_movies[movie_id] = movie
                else:
                    # Garder le rôle le plus important (réalisateur > acteur > crew)
                    current = unique_movies[movie_id]
                    if (movie['role_detail'] in ['Director', 'Réalisateur'] or 
                        (current['role_type'] == 'crew' and movie['role_type'] == 'acting')):
                        unique_movies[movie_id] = movie
            
            # Trier par date de sortie (plus récent en premier)
            sorted_movies = sorted(
                unique_movies.values(),
                key=lambda x: x.get('release_date', '1900-01-01'),
                reverse=True
            )
            
            # Limiter aux résultats demandés
            movies = sorted_movies[:max_results]
            
            if not movies:
                return "🎬 **Aucune filmographie trouvée**"
            
            return await self._format_filmography(movies)
    
    async def _get_account_content(self, search_type: str, account_id: int, max_results: int) -> str:
        """Contenu lié au compte utilisateur"""
        endpoint_map = {
            "account_details": f"/account/{account_id}",
            "account_favorites_movies": f"/account/{account_id}/favorite/movies",
            "account_favorites_tv": f"/account/{account_id}/favorite/tv",
            "account_watchlist_movies": f"/account/{account_id}/watchlist/movies", 
            "account_watchlist_tv": f"/account/{account_id}/watchlist/tv",
            "account_rated_movies": f"/account/{account_id}/rated/movies",
            "account_rated_tv": f"/account/{account_id}/rated/tv",
            "account_lists": f"/account/{account_id}/lists"
        }
        
        url = f"{TMDB_BASE_URL}{endpoint_map[search_type]}"
        params = {"language": "fr-FR"}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            data = response.json()
            
            if search_type == "account_details":
                return await self._format_account_details(data)
            else:
                results = data.get('results', [])[:max_results]
                return await self._format_account_results(results, search_type)
    
    # === FORMATAGE DES RÉSULTATS ===
    
    async def _format_search_results(self, results: List[Dict], search_type: str, query: str) -> str:
        """Format les résultats de recherche"""
        type_icons = {
            "movie": "🎬",
            "tv": "📺", 
            "person": "🎭",
            "multi": "🔍"
        }
        
        icon = type_icons.get(search_type, "🔍")
        result_text = f"{icon} **Résultats de recherche** pour `{query}` ({len(results)} trouvé{'s' if len(results) > 1 else ''}):\n\n"
        
        for i, item in enumerate(results, 1):
            media_type = item.get('media_type', search_type)
            
            if media_type == 'movie' or search_type == 'movie':
                result_text += await self._format_movie_item(item, i)
            elif media_type == 'tv' or search_type == 'tv':
                result_text += await self._format_tv_item(item, i)
            elif media_type == 'person' or search_type == 'person':
                result_text += await self._format_person_item(item, i)
            
            result_text += "\n" + "─" * 50 + "\n\n"
        
        return result_text
    
    async def _format_discovery_results(self, results: List[Dict], search_type: str) -> str:
        """Format les résultats de découverte"""
        titles = {
            "popular_movies": "🔥 **Films populaires**",
            "popular_tv": "🔥 **Séries populaires**", 
            "trending": "📈 **Tendances du jour**",
            "top_rated_movies": "⭐ **Films les mieux notés**",
            "top_rated_tv": "⭐ **Séries les mieux notées**"
        }
        
        title = titles.get(search_type, "🎬 **Découverte**")
        result_text = f"{title} ({len(results)} résultat{'s' if len(results) > 1 else ''}):\n\n"
        
        for i, item in enumerate(results, 1):
            media_type = item.get('media_type', 'movie' if 'movie' in search_type else 'tv')
            
            if media_type == 'movie' or 'movie' in search_type:
                result_text += await self._format_movie_item(item, i)
            elif media_type == 'tv' or 'tv' in search_type:
                result_text += await self._format_tv_item(item, i)
            else:
                result_text += await self._format_person_item(item, i)
            
            result_text += "\n" + "─" * 50 + "\n\n"
        
        return result_text
    
    async def _format_movie_item(self, movie: Dict, index: int) -> str:
        """Format un élément film"""
        title = movie.get('title', 'Titre inconnu')
        original_title = movie.get('original_title', '')
        release_date = movie.get('release_date', '')
        vote_average = movie.get('vote_average', 0)
        vote_count = movie.get('vote_count', 0)
        overview = movie.get('overview', 'Synopsis non disponible')
        
        text = f"🎬 **{index}. {title}**"
        
        if original_title and original_title != title:
            text += f" *(titre original: {original_title})*"
        
        text += f"\n📅 **Année :** {release_date[:4] if release_date else 'Inconnue'}\n"
        
        if vote_average > 0:
            stars = "⭐" * min(int(vote_average / 2), 5)
            text += f"⭐ **Note :** {vote_average:.1f}/10 {stars} ({vote_count:,} votes)\n"
        
        if overview and len(overview) > 10:
            synopsis = overview[:250] + "..." if len(overview) > 250 else overview
            text += f"📖 **Synopsis :** {synopsis}\n"
        
        text += f"🆔 **TMDB ID :** {movie.get('id', 'N/A')}"
        
        return text
    
    async def _format_tv_item(self, tv: Dict, index: int) -> str:
        """Format un élément série TV"""
        name = tv.get('name', 'Titre inconnu')
        original_name = tv.get('original_name', '')
        first_air_date = tv.get('first_air_date', '')
        vote_average = tv.get('vote_average', 0)
        vote_count = tv.get('vote_count', 0)
        overview = tv.get('overview', 'Synopsis non disponible')
        
        text = f"📺 **{index}. {name}**"
        
        if original_name and original_name != name:
            text += f" *(titre original: {original_name})*"
        
        text += f"\n📅 **Première diffusion :** {first_air_date[:4] if first_air_date else 'Inconnue'}\n"
        
        if vote_average > 0:
            stars = "⭐" * min(int(vote_average / 2), 5)
            text += f"⭐ **Note :** {vote_average:.1f}/10 {stars} ({vote_count:,} votes)\n"
        
        if overview and len(overview) > 10:
            synopsis = overview[:250] + "..." if len(overview) > 250 else overview
            text += f"📖 **Synopsis :** {synopsis}\n"
        
        text += f"🆔 **TMDB ID :** {tv.get('id', 'N/A')}"
        
        return text
    
    async def _format_person_item(self, person: Dict, index: int) -> str:
        """Format un élément personne"""
        name = person.get('name', 'Nom inconnu')
        known_for_department = person.get('known_for_department', '')
        popularity = person.get('popularity', 0)
        known_for = person.get('known_for', [])
        
        text = f"🎭 **{index}. {name}**\n"
        
        if known_for_department:
            dept_fr = {
                'Acting': 'Acteur/Actrice',
                'Directing': 'Réalisateur/Réalisatrice',
                'Writing': 'Scénariste', 
                'Production': 'Producteur/Productrice'
            }.get(known_for_department, known_for_department)
            text += f"🎬 **Métier :** {dept_fr}\n"
        
        if popularity > 0:
            text += f"📊 **Popularité :** {popularity:.1f}\n"
        
        if known_for:
            titles = []
            for work in known_for[:3]:
                title = work.get('title') or work.get('name', '')
                if title:
                    year = ""
                    if work.get('release_date'):
                        year = f" ({work['release_date'][:4]})"
                    elif work.get('first_air_date'):
                        year = f" ({work['first_air_date'][:4]})"
                    titles.append(f"{title}{year}")
            
            if titles:
                text += f"🌟 **Connu pour :** {', '.join(titles)}\n"
        
        text += f"🆔 **TMDB ID :** {person.get('id', 'N/A')}"
        
        return text
    
    async def _format_filmography(self, movies: List[Dict]) -> str:
        """Format la filmographie d'une personne"""
        if not movies:
            return "🎬 **Aucun film trouvé**"
        
        result_text = f"🎬 **Filmographie** ({len(movies)} film{'s' if len(movies) > 1 else ''}) :\n\n"
        
        for i, movie in enumerate(movies, 1):
            title = movie.get('title', 'Titre inconnu')
            release_date = movie.get('release_date', '')
            role_detail = movie.get('role_detail', '')
            vote_average = movie.get('vote_average', 0)
            
            result_text += f"🎬 **{i}. {title}**"
            
            if release_date:
                result_text += f" ({release_date[:4]})"
            
            result_text += "\n"
            
            if role_detail:
                role_icon = "🎭" if movie.get('role_type') == 'acting' else "🎬"
                result_text += f"{role_icon} **Rôle :** {role_detail}\n"
            
            if vote_average > 0:
                stars = "⭐" * min(int(vote_average / 2), 5)
                result_text += f"⭐ **Note :** {vote_average:.1f}/10 {stars}\n"
            
            result_text += "\n"
        
        return result_text
    
    async def _format_movie_details(self, movie: Dict) -> str:
        """Format les détails complets d'un film"""
        title = movie.get('title', 'Titre inconnu')
        original_title = movie.get('original_title', '')
        release_date = movie.get('release_date', '')
        runtime = movie.get('runtime', 0)
        budget = movie.get('budget', 0)
        revenue = movie.get('revenue', 0)
        vote_average = movie.get('vote_average', 0)
        vote_count = movie.get('vote_count', 0)
        overview = movie.get('overview', 'Synopsis non disponible')
        genres = movie.get('genres', [])
        
        result_text = f"🎬 **{title}**\n\n"
        
        if original_title and original_title != title:
            result_text += f"📝 **Titre original :** {original_title}\n"
        
        if release_date:
            result_text += f"📅 **Date de sortie :** {release_date}\n"
        
        if runtime:
            hours = runtime // 60
            minutes = runtime % 60
            result_text += f"⏱️ **Durée :** {hours}h{minutes:02d}min\n"
        
        if genres:
            genre_names = [g['name'] for g in genres]
            result_text += f"🎭 **Genres :** {', '.join(genre_names)}\n"
        
        if vote_average > 0:
            stars = "⭐" * min(int(vote_average / 2), 5)
            result_text += f"⭐ **Note :** {vote_average:.1f}/10 {stars} ({vote_count:,} votes)\n"
        
        if budget > 0:
            result_text += f"💰 **Budget :** ${budget:,}\n"
        
        if revenue > 0:
            result_text += f"💵 **Box-office :** ${revenue:,}\n"
        
        result_text += "\n"
        
        if overview:
            result_text += f"📖 **Synopsis :**\n{overview}\n\n"
        
        # Cast principal
        credits = movie.get('credits', {})
        cast = credits.get('cast', [])[:5]  # Top 5 acteurs
        if cast:
            result_text += "🎭 **Cast principal :**\n"
            for actor in cast:
                name = actor.get('name', '')
                character = actor.get('character', '')
                if name:
                    result_text += f"• {name}"
                    if character:
                        result_text += f" *(dans le rôle de {character})*"
                    result_text += "\n"
            result_text += "\n"
        
        # Équipe technique
        crew = credits.get('crew', [])
        directors = [c['name'] for c in crew if c.get('job') == 'Director']
        writers = [c['name'] for c in crew if c.get('job') in ['Writer', 'Screenplay']]
        
        if directors:
            result_text += f"🎬 **Réalisateur{'s' if len(directors) > 1 else ''} :** {', '.join(directors)}\n"
        
        if writers:
            result_text += f"✍️ **Scénariste{'s' if len(writers) > 1 else ''} :** {', '.join(writers)}\n"
        
        return result_text
    
    async def _format_tv_details(self, tv: Dict) -> str:
        """Format les détails complets d'une série"""
        name = tv.get('name', 'Titre inconnu')
        original_name = tv.get('original_name', '')
        first_air_date = tv.get('first_air_date', '')
        last_air_date = tv.get('last_air_date', '')
        number_of_seasons = tv.get('number_of_seasons', 0)
        number_of_episodes = tv.get('number_of_episodes', 0)
        episode_run_time = tv.get('episode_run_time', [])
        vote_average = tv.get('vote_average', 0)
        vote_count = tv.get('vote_count', 0)
        overview = tv.get('overview', 'Synopsis non disponible')
        genres = tv.get('genres', [])
        status = tv.get('status', '')
        
        result_text = f"📺 **{name}**\n\n"
        
        if original_name and original_name != name:
            result_text += f"📝 **Titre original :** {original_name}\n"
        
        if first_air_date:
            result_text += f"📅 **Première diffusion :** {first_air_date}\n"
        
        if last_air_date and last_air_date != first_air_date:
            result_text += f"📅 **Dernière diffusion :** {last_air_date}\n"
        
        if status:
            status_fr = {
                'Ended': 'Terminée',
                'Returning Series': 'En cours',
                'Canceled': 'Annulée',
                'In Production': 'En production'
            }.get(status, status)
            result_text += f"📊 **Statut :** {status_fr}\n"
        
        if number_of_seasons:
            result_text += f"📚 **Saisons :** {number_of_seasons}\n"
        
        if number_of_episodes:
            result_text += f"📺 **Épisodes :** {number_of_episodes}\n"
        
        if episode_run_time:
            runtime = episode_run_time[0] if episode_run_time else 0
            result_text += f"⏱️ **Durée par épisode :** ~{runtime}min\n"
        
        if genres:
            genre_names = [g['name'] for g in genres]
            result_text += f"🎭 **Genres :** {', '.join(genre_names)}\n"
        
        if vote_average > 0:
            stars = "⭐" * min(int(vote_average / 2), 5)
            result_text += f"⭐ **Note :** {vote_average:.1f}/10 {stars} ({vote_count:,} votes)\n"
        
        result_text += "\n"
        
        if overview:
            result_text += f"📖 **Synopsis :**\n{overview}\n\n"
        
        # Cast principal
        credits = tv.get('credits', {})
        cast = credits.get('cast', [])[:5]
        if cast:
            result_text += "🎭 **Cast principal :**\n"
            for actor in cast:
                name = actor.get('name', '')
                character = actor.get('character', '')
                if name:
                    result_text += f"• {name}"
                    if character:
                        result_text += f" *(dans le rôle de {character})*"
                    result_text += "\n"
            result_text += "\n"
        
        # Créateurs
        created_by = tv.get('created_by', [])
        if created_by:
            creators = [c['name'] for c in created_by]
            result_text += f"🎬 **Créateur{'s' if len(creators) > 1 else ''} :** {', '.join(creators)}\n"
        
        return result_text
    
    async def _format_person_details(self, person: Dict) -> str:
        """Format les détails complets d'une personne"""
        name = person.get('name', 'Nom inconnu')
        birthday = person.get('birthday', '')
        deathday = person.get('deathday', '')
        place_of_birth = person.get('place_of_birth', '')
        known_for_department = person.get('known_for_department', '')
        biography = person.get('biography', 'Biographie non disponible')
        popularity = person.get('popularity', 0)
        
        result_text = f"🎭 **{name}**\n\n"
        
        if known_for_department:
            dept_fr = {
                'Acting': 'Acteur/Actrice',
                'Directing': 'Réalisateur/Réalisatrice',
                'Writing': 'Scénariste',
                'Production': 'Producteur/Productrice'
            }.get(known_for_department, known_for_department)
            result_text += f"🎬 **Métier principal :** {dept_fr}\n"
        
        if birthday:
            age = ""
            if not deathday:
                today = datetime.now()
                birth_year = int(birthday[:4])
                current_age = today.year - birth_year
                age = f" ({current_age} ans)"
            result_text += f"🎂 **Naissance :** {birthday}{age}\n"
        
        if deathday:
            result_text += f"⚰️ **Décès :** {deathday}\n"
        
        if place_of_birth:
            result_text += f"🌍 **Lieu de naissance :** {place_of_birth}\n"
        
        if popularity > 0:
            result_text += f"📊 **Popularité :** {popularity:.1f}\n"
        
        result_text += "\n"
        
        if biography and len(biography) > 10:
            bio = biography[:500] + "..." if len(biography) > 500 else biography
            result_text += f"📖 **Biographie :**\n{bio}\n\n"
        
        # Films récents
        movie_credits = person.get('movie_credits', {})
        recent_movies = movie_credits.get('cast', [])[:3]
        if recent_movies:
            result_text += "🎬 **Films récents :**\n"
            for movie in recent_movies:
                title = movie.get('title', '')
                release_date = movie.get('release_date', '')
                year = f" ({release_date[:4]})" if release_date else ""
                result_text += f"• {title}{year}\n"
        
        return result_text
    
    async def _format_account_details(self, account: Dict) -> str:
        """Format les détails d'un compte"""
        username = account.get('username', 'Inconnu')
        name = account.get('name', '')
        include_adult = account.get('include_adult', False)
        iso_639_1 = account.get('iso_639_1', '')
        iso_3166_1 = account.get('iso_3166_1', '')
        
        result_text = f"👤 **Compte TMDB**\n\n"
        result_text += f"🆔 **Nom d'utilisateur :** {username}\n"
        
        if name:
            result_text += f"📝 **Nom :** {name}\n"
        
        result_text += f"🔞 **Contenu adulte :** {'Activé' if include_adult else 'Désactivé'}\n"
        
        if iso_639_1:
            result_text += f"🌍 **Langue :** {iso_639_1}\n"
        
        if iso_3166_1:
            result_text += f"🌍 **Pays :** {iso_3166_1}\n"
        
        return result_text
    
    async def _format_account_results(self, results: List[Dict], search_type: str) -> str:
        """Format les résultats liés au compte"""
        titles = {
            "account_favorites_movies": "❤️ **Films favoris**",
            "account_favorites_tv": "❤️ **Séries favorites**",
            "account_watchlist_movies": "📋 **Films en watchlist**",
            "account_watchlist_tv": "📋 **Séries en watchlist**", 
            "account_rated_movies": "⭐ **Films notés**",
            "account_rated_tv": "⭐ **Séries notées**",
            "account_lists": "📝 **Listes personnalisées**"
        }
        
        title = titles.get(search_type, "📋 **Résultats du compte**")
        
        if not results:
            return f"{title}\n\n🔍 **Aucun élément trouvé**"
        
        result_text = f"{title} ({len(results)} élément{'s' if len(results) > 1 else ''}):\n\n"
        
        for i, item in enumerate(results, 1):
            if search_type == "account_lists":
                result_text += await self._format_list_item(item, i)
            elif 'tv' in search_type:
                result_text += await self._format_tv_item(item, i)
            else:
                result_text += await self._format_movie_item(item, i)
            
            result_text += "\n" + "─" * 40 + "\n\n"
        
        return result_text
    
    async def _format_list_item(self, list_item: Dict, index: int) -> str:
        """Format un élément de liste personnalisée"""
        name = list_item.get('name', 'Liste sans nom')
        description = list_item.get('description', '')
        item_count = list_item.get('item_count', 0)
        list_type = list_item.get('list_type', 'movie')
        
        text = f"📝 **{index}. {name}**\n"
        text += f"📊 **Éléments :** {item_count}\n"
        text += f"🎬 **Type :** {list_type}\n"
        
        if description:
            desc = description[:150] + "..." if len(description) > 150 else description
            text += f"📖 **Description :** {desc}\n"
        
        text += f"🆔 **ID Liste :** {list_item.get('id', 'N/A')}"
        
        return text


# Test du tool
if __name__ == "__main__":
    import asyncio
    
    async def test_tmdb_complete():
        tool = TMDBTool()
        
        test_cases = [
            # Test de base
            {"search_type": "movie", "query": "Inception", "max_results": 1},
            
            # Test filmographie (le cas problématique)
            {"search_type": "person_filmography", "query": "Christopher Nolan", "max_results": 5},
            
            # Test détails complets
            {"search_type": "movie_details", "tmdb_id": 27205},  # Inception
            
            # Test découverte
            {"search_type": "trending", "max_results": 3}
        ]
        
        for test in test_cases:
            print(f"\n🧪 Test: {test}")
            print("=" * 80)
            result = await tool.execute(**test)
            print(result)
            print()
    
    asyncio.run(test_tmdb_complete())