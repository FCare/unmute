"""
Tool pour rechercher des recettes de cuisine avec TheMealDB API.
API gratuite sans clé requise, mais fonctionnant uniquement en anglais.
"""

import logging
from typing import Dict, Any
import httpx

from .base import BaseTool

logger = logging.getLogger(__name__)

class RecipesTool(BaseTool):
    """Tool pour rechercher des recettes de cuisine via TheMealDB API"""
    
    @property
    def name(self) -> str:
        return "search_recipes"
    
    @property
    def description(self) -> str:
        return """Recherche de recettes de cuisine via TheMealDB API.

        ⚠️ IMPORTANT - GESTION TRADUCTION OBLIGATOIRE :
        - L'API fonctionne UNIQUEMENT en ANGLAIS
        - Vous DEVEZ traduire la requête utilisateur français → anglais avant l'API
        - Vous DEVEZ traduire la réponse anglais → français pour l'utilisateur  
        - Convertissez les unités impériales → métriques (cups→ml, lb→kg, °F→°C)
        
        Types de recherche supportés :
        1. Par nom de plat : traduire "pâtes carbonara" → "carbonara"
        2. Par ingrédient principal : traduire "poulet" → "chicken" 
        3. Par catégorie : traduire "dessert" → "dessert", "fruits de mer" → "seafood"
        4. Aléatoire : aucune traduction nécessaire
        
        Exemples de traduction pour recherche :
        - "recette carbonara" → search_type="name", query="carbonara"
        - "que faire avec du poulet" → search_type="ingredient", query="chicken"  
        - "dessert italien" → search_type="category", query="dessert"
        - "surprise-moi" → search_type="random", query=""
        
        LIMITATION API : Un seul ingrédient principal par recherche.
        Pour plusieurs ingrédients, choisir le principal et mentionner les autres dans la réponse.
        
        FORMATAGE RÉPONSE : Traduire TOUT en français :
        - Nom de la recette
        - Liste ingrédients avec conversions (1 cup = 240ml, 1 lb = 450g)  
        - Instructions étape par étape
        - Origine géographique et catégorie
        """
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "search_type": {
                    "type": "string",
                    "enum": ["name", "ingredient", "category", "random"],
                    "description": "Type de recherche à effectuer"
                },
                "query": {
                    "type": "string",
                    "description": "OBLIGATOIRE: Terme traduit EN ANGLAIS pour l'API. Ex: 'poulet'→'chicken', 'pâtes carbonara'→'carbonara', 'dessert'→'dessert'. Vide pour recherche aléatoire."
                },
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "default": 3,
                    "description": "Nombre maximum de recettes à retourner"
                }
            },
            "required": ["search_type", "query"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        """Recherche des recettes avec TheMealDB API"""
        
        search_type = kwargs.get("search_type", "name")
        query = kwargs.get("query", "")
        max_results = kwargs.get("max_results", 3)
        
        # Validation
        max_results = min(max(max_results, 1), 5)
        
        try:
            # Choisir l'endpoint selon le type de recherche
            if search_type == "random":
                recipes = await self._get_random_recipe()
            elif search_type == "name":
                recipes = await self._search_by_name(query, max_results)
            elif search_type == "ingredient":
                recipes = await self._search_by_ingredient(query, max_results)
            elif search_type == "category":
                recipes = await self._search_by_category(query, max_results)
            else:
                return "❌ Type de recherche non supporté"
            
            if not recipes:
                return f"Aucune recette trouvée pour: {query}"
            
            # Formater la réponse avec détails complets
            result = f"🍽️ **Recettes trouvées** ({len(recipes)} résultat{'s' if len(recipes) > 1 else ''}):\n\n"
            
            for i, recipe in enumerate(recipes, 1):
                result += await self._format_recipe(recipe, i)
                result += "\n" + "="*50 + "\n\n"
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur TheMealDB API: {e}")
            return f"❌ Erreur lors de la recherche de recettes: {str(e)}"
    
    async def _search_by_name(self, name: str, max_results: int) -> list:
        """Recherche par nom de plat"""
        url = f"https://www.themealdb.com/api/json/v1/1/search.php"
        params = {"s": name}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            meals = data.get('meals', []) or []
            return meals[:max_results]
    
    async def _search_by_ingredient(self, ingredient: str, max_results: int) -> list:
        """Recherche par ingrédient principal"""
        url = f"https://www.themealdb.com/api/json/v1/1/filter.php"
        params = {"i": ingredient}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            meals = data.get('meals', []) or []
            # Les résultats de filter.php ne contiennent que les infos de base
            # Il faut récupérer les détails complets
            detailed_meals = []
            for meal in meals[:max_results]:
                meal_id = meal.get('idMeal')
                if meal_id:
                    detailed_meal = await self._get_recipe_details(meal_id)
                    if detailed_meal:
                        detailed_meals.append(detailed_meal)
            
            return detailed_meals
    
    async def _search_by_category(self, category: str, max_results: int) -> list:
        """Recherche par catégorie"""
        url = f"https://www.themealdb.com/api/json/v1/1/filter.php"
        params = {"c": category}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            meals = data.get('meals', []) or []
            # Récupérer les détails complets
            detailed_meals = []
            for meal in meals[:max_results]:
                meal_id = meal.get('idMeal')
                if meal_id:
                    detailed_meal = await self._get_recipe_details(meal_id)
                    if detailed_meal:
                        detailed_meals.append(detailed_meal)
            
            return detailed_meals
    
    async def _get_random_recipe(self) -> list:
        """Récupère une recette aléatoire"""
        url = f"https://www.themealdb.com/api/json/v1/1/random.php"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            meals = data.get('meals', []) or []
            return meals
    
    async def _get_recipe_details(self, meal_id: str) -> dict | None:
        """Récupère les détails complets d'une recette"""
        url = f"https://www.themealdb.com/api/json/v1/1/lookup.php"
        params = {"i": meal_id}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            meals = data.get('meals', []) or []
            return meals[0] if meals else None
    
    async def _format_recipe(self, recipe: dict, index: int) -> str:
        """Formate une recette pour affichage"""
        name = recipe.get('strMeal', 'Recette sans nom')
        category = recipe.get('strCategory', '')
        area = recipe.get('strArea', '')
        instructions = recipe.get('strInstructions', 'Instructions non disponibles')
        image = recipe.get('strMealThumb', '')
        youtube = recipe.get('strYoutube', '')
        
        # Construire la liste des ingrédients
        ingredients = []
        for i in range(1, 21):  # strIngredient1 à strIngredient20
            ingredient = recipe.get(f'strIngredient{i}', '').strip()
            measure = recipe.get(f'strMeasure{i}', '').strip()
            
            if ingredient and ingredient.lower() not in ['', 'null']:
                if measure:
                    ingredients.append(f"• {measure} {ingredient}")
                else:
                    ingredients.append(f"• {ingredient}")
        
        # Formater la réponse
        result = f"🍽️ **{index}. {name}**\n"
        
        if category or area:
            result += f"📍 "
            if category:
                result += f"Catégorie: {category}"
            if area:
                result += f" | Origine: {area}" if category else f"Origine: {area}"
            result += "\n"
        
        result += "\n📋 **Ingrédients:**\n"
        if ingredients:
            result += "\n".join(ingredients)
        else:
            result += "• Liste d'ingrédients non disponible"
        
        result += "\n\n👨‍🍳 **Instructions:**\n"
        # Découper les instructions en paragraphes plus lisibles
        if instructions:
            # Remplacer les points par des retours à la ligne pour plus de clarté
            instructions_formatted = instructions.replace('. ', '.\n• ').strip()
            if not instructions_formatted.startswith('•'):
                instructions_formatted = '• ' + instructions_formatted
            result += instructions_formatted
        
        # Ajouter liens supplémentaires si disponibles
        links = []
        if image:
            links.append(f"🖼️ [Photo de la recette]({image})")
        if youtube:
            links.append(f"📺 [Vidéo YouTube]({youtube})")
        
        if links:
            result += "\n\n📱 **Liens:**\n" + "\n".join(links)
        
        return result

# Test du tool
if __name__ == "__main__":
    import asyncio
    
    async def test_recipes_tool():
        tool = RecipesTool()
        
        test_cases = [
            {"search_type": "name", "query": "carbonara", "max_results": 1},
            {"search_type": "ingredient", "query": "chicken", "max_results": 2},
            {"search_type": "category", "query": "dessert", "max_results": 1},
            {"search_type": "random", "query": ""}
        ]
        
        for test in test_cases:
            print(f"\n🧪 Test: {test}")
            print("=" * 60)
            result = await tool.execute(**test)
            print(result)
            print()
    
    asyncio.run(test_recipes_tool())