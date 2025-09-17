# backend/routes/llm.py
from fastapi import APIRouter, Body
from pydantic import BaseModel
from src.geo_agent.models import get_llm_client
from src.geo_agent.config import settings

router = APIRouter(prefix="/llm", tags=["llm"])

class TestModelRequest(BaseModel):
    prompt: str
    model: str
    provider: str = "ollama"

@router.get("/status")
def llm_status():
    """
    Vérifie le statut de tous les LLM configurés.
    """
    status = {}

    # Test Ollama
    try:
        ollama_client = get_llm_client("ollama")
        if hasattr(ollama_client, 'health'):
            status["ollama"] = {
                "available": ollama_client.health(),
                "models": ollama_client.list_models() if ollama_client.health() else []
            }
        else:
            status["ollama"] = {"available": False, "error": "Pas de méthode health()"}
    except Exception as e:
        status["ollama"] = {"available": False, "error": str(e)}

    # Test OpenAI
    try:
        if settings.OPENAI_API_KEY:
            openai_client = get_llm_client("openai")
            status["openai"] = {
                "available": openai_client.health() if hasattr(openai_client, 'health') else True,
                "api_key_set": bool(settings.OPENAI_API_KEY)
            }
        else:
            status["openai"] = {"available": False, "error": "OPENAI_API_KEY non définie"}
    except Exception as e:
        status["openai"] = {"available": False, "error": str(e)}

    # Test Claude/Anthropic
    try:
        if settings.ANTHROPIC_API_KEY:
            anthropic_client = get_llm_client("anthropic")
            status["anthropic"] = {
                "available": anthropic_client.health() if hasattr(anthropic_client, 'health') else True,
                "api_key_set": bool(settings.ANTHROPIC_API_KEY)
            }
        else:
            status["anthropic"] = {"available": False, "error": "ANTHROPIC_API_KEY non définie"}
    except Exception as e:
        status["anthropic"] = {"available": False, "error": str(e)}

    # Test Gemini
    try:
        if settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY:
            gemini_client = get_llm_client("gemini")
            status["gemini"] = {
                "available": gemini_client.health() if hasattr(gemini_client, 'health') else True,
                "api_key_set": bool(settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY)
            }
        else:
            status["gemini"] = {"available": False, "error": "GEMINI_API_KEY ou GOOGLE_API_KEY non définie"}
    except Exception as e:
        status["gemini"] = {"available": False, "error": str(e)}

    # Configuration actuelle
    status["current_config"] = {
        "provider": settings.LLM_PROVIDER,
        "model": settings.LLM_MODEL,
        "temperature": settings.TEMPERATURE
    }

    return status

@router.post("/test")
def llm_test(prompt: str = Body("Ping?")):
    """
    Appel simple au LLM courant (défini par les vars d'env).
    Renvoie le modèle utilisé et la sortie brute.
    """
    try:
        client = get_llm_client()

        # Test si le client a une méthode answer
        if hasattr(client, 'answer'):
            out = client.answer(prompt, model=settings.LLM_MODEL, temperature=settings.TEMPERATURE)
        elif hasattr(client, 'answer_with_meta'):
            result = client.answer_with_meta(prompt, model=settings.LLM_MODEL, temperature=settings.TEMPERATURE)
            out = result.get("text", "")
        else:
            out = "Client LLM ne supporte ni answer() ni answer_with_meta()"

        return {"ok": True, "model_used": settings.LLM_MODEL, "output": out}

    except Exception as e:
        return {"ok": False, "error": str(e), "model_used": settings.LLM_MODEL}

@router.post("/test-with-model")
def llm_test_with_model(request: TestModelRequest):
    """
    Test avec un modèle spécifique.
    """
    try:
        client = get_llm_client(request.provider, request.model)

        if hasattr(client, 'answer'):
            out = client.answer(request.prompt, model=request.model, temperature=0.1)
        elif hasattr(client, 'answer_with_meta'):
            result = client.answer_with_meta(request.prompt, model=request.model, temperature=0.1)
            out = result.get("text", "")
        else:
            out = "Client LLM ne supporte ni answer() ni answer_with_meta()"

        return {"ok": True, "provider": request.provider, "model_used": request.model, "output": out}

    except Exception as e:
        return {"ok": False, "error": str(e), "provider": request.provider, "model_used": request.model}

@router.post("/test-gpt5-web")
def test_gpt5_with_web_search(prompt: str = Body(...)):
    """
    Test GPT-5 avec recherche web pour du GEO réel
    """
    try:
        client = get_llm_client("openai", "gpt-5-mini")

        if hasattr(client, 'answer'):
            out = client.answer(prompt, model="gpt-5-mini", temperature=0.1, web_search=True)
        else:
            out = "Client OpenAI ne supporte pas GPT-5"

        return {"ok": True, "provider": "openai", "model_used": "gpt-5-mini", "web_search": True, "output": out}

    except Exception as e:
        return {"ok": False, "error": str(e), "provider": "openai", "model_used": "gpt-5-mini"}