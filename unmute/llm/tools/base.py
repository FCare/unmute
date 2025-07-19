from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseTool(ABC):
    """Classe de base pour tous les outils"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Nom unique de l'outil"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Description de l'outil"""
        pass
    
    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """Schéma des paramètres JSON Schema"""
        pass
    
    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        """Exécute l'outil avec les paramètres donnés"""
        pass
    
    def get_definition(self) -> Dict[str, Any]:
        """Retourne la définition OpenAI/Ollama de l'outil"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }