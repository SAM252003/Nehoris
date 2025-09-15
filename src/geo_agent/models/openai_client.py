import os
from typing import List, Dict
from openai import OpenAI
from .base import BaseLLMClient

class OpenAIClient(BaseLLMClient):
def __init__(self, model: str):
    self.model = model
    self.name = f"openai:{model}"
    self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def answer(self, messages: List[Dict], temperature: float = 0.2) -> str:
    resp = self.client.chat.completions.create(
        model=self.model,
        messages=messages,
        temperature=temperature,
    )
    return resp.choices[0].message.content or ""