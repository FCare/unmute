import datetime
from typing import Dict, Any
from .base import BaseTool

class TimeTool(BaseTool):
    """Outil pour obtenir l'heure et la date actuelles"""
    
    @property
    def name(self) -> str:
        return "get_current_time"
    
    @property
    def description(self) -> str:
        return "Obtient l'heure et la date actuelles"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    async def execute(self, **kwargs: Any) -> str:
        """Retourne l'heure actuelle"""
        now = datetime.datetime.now()
        return now.strftime("%H:%M:%S le %d/%m/%Y")