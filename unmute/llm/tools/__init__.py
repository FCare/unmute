import json
import importlib
import pkgutil
import logging
from typing import Dict, List, Any
from .base import BaseTool

logger = logging.getLogger(__name__)

class ToolRegistry:
    """Registry pour gérer automatiquement tous les outils"""
    
    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}
        self._load_all_tools()
    
    def _load_all_tools(self):
        """Charge automatiquement tous les outils du répertoire"""
        # Import automatique de tous les modules du package tools
        import unmute.llm.tools as tools_package
        
        for _, module_name, _ in pkgutil.iter_modules(tools_package.__path__):
            if module_name not in ['base', '__init__']:
                try:
                    module = importlib.import_module(f'unmute.llm.tools.{module_name}')
                    
                    # Cherche toutes les classes qui héritent de BaseTool
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and 
                            issubclass(attr, BaseTool) and 
                            attr != BaseTool):
                            
                            # Instancie et enregistre l'outil
                            tool_instance = attr()
                            self.tools[tool_instance.name] = tool_instance
                            logger.info(f"Outil chargé: {tool_instance.name}")
                            
                except Exception as e:
                    logger.error(f"Erreur lors du chargement de {module_name}: {e}")
    
    @property
    def tool_definitions(self) -> List[Dict[str, Any]]:
        """Retourne les définitions de tous les outils pour Ollama"""
        return [tool.get_definition() for tool in self.tools.values()]
    
    async def execute_tool(self, tool_call: Dict[str, Any]) -> str:
        """Exécute un outil et retourne le résultat"""
        function_name = tool_call["function"]["name"]
        
        if function_name not in self.tools:
            return f"Erreur: outil '{function_name}' non trouvé"
        
        try:
            # Ollama peut passer les arguments comme string ou dict
            arguments = tool_call["function"]["arguments"]
            if isinstance(arguments, str):
                args = json.loads(arguments)
            else:
                args = arguments
                
            result = await self.tools[function_name].execute(**args)
            return str(result)
        except Exception as e:
            logger.error(f"Erreur lors de l'exécution de {function_name}: {e}")
            return f"Erreur lors de l'exécution de {function_name}: {e}"

# Instance globale
tool_registry = ToolRegistry()