from abc import ABC, abstractmethod
from typing import List, Dict

class BaseLLMClient(ABC):
    name: str

    @abstractmethod
    def answer(self, messages: List[Dict], temperature: float = 0.2) -> str:
        pass