from typing import Dict, Any
from .base import BaseTool

class CalculatorTool(BaseTool):
    """Outil pour effectuer des calculs mathématiques"""
    
    @property
    def name(self) -> str:
        return "calculate"
    
    @property
    def description(self) -> str:
        return "Effectue un calcul mathématique simple"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "L'expression mathématique à calculer (ex: 2+2, 15*3)"
                }
            },
            "required": ["expression"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        """Effectue un calcul mathématique simple"""
        expression = kwargs.get("expression")
        if not expression:
            return "Erreur: paramètre 'expression' manquant"
            
        try:
            # Sécurisé pour les calculs de base
            allowed_chars = set("0123456789+-*/().,  ")
            if not all(c in allowed_chars for c in expression):
                return "Expression non autorisée - seuls les chiffres et opérateurs de base sont permis"
            
            result = eval(expression)
            return f"{expression} = {result}"
        except Exception as e:
            return f"Erreur de calcul: {e}"