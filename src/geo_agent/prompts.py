from typing import List

GENERIC_SYSTEM = (
"Tu es un assistant utile et concis. Réponds de façon claire, neutre et factuelle."
)

def build_user_prompt(query: str) -> List[dict]:
    return [{"role": "user", "content": query}]