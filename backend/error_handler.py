"""
Gestionnaire d'erreurs avancé pour l'amélioration de la robustesse
"""
import time
import traceback
from typing import Any, Dict, Optional, Callable
from functools import wraps
import logging

logger = logging.getLogger(__name__)

class CircuitBreaker:
    """Circuit breaker pour éviter les cascades d'erreurs"""

    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def is_available(self) -> bool:
        """Vérifie si le service est disponible"""
        if self.state == "CLOSED":
            return True
        elif self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
                return True
            return False
        else:  # HALF_OPEN
            return True

    def record_success(self):
        """Enregistre un succès"""
        self.failure_count = 0
        self.state = "CLOSED"

    def record_failure(self):
        """Enregistre un échec"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

# Circuit breakers par provider
circuit_breakers = {
    "openai": CircuitBreaker(),
    "perplexity": CircuitBreaker(),
    "gemini": CircuitBreaker(),
    "ollama": CircuitBreaker()
}

def with_retry_and_circuit_breaker(provider: str, max_retries: int = 3, backoff_factor: float = 1.5):
    """
    Décorateur combinant retry logic et circuit breaker
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            circuit_breaker = circuit_breakers.get(provider)

            if not circuit_breaker or not circuit_breaker.is_available():
                raise Exception(f"Service {provider} temporairement indisponible (circuit breaker ouvert)")

            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    result = await func(*args, **kwargs)
                    if circuit_breaker:
                        circuit_breaker.record_success()
                    return result

                except Exception as e:
                    last_exception = e
                    logger.warning(f"Tentative {attempt + 1}/{max_retries + 1} échouée pour {provider}: {str(e)}")

                    if circuit_breaker:
                        circuit_breaker.record_failure()

                    if attempt < max_retries:
                        wait_time = backoff_factor ** attempt
                        logger.info(f"Attente de {wait_time:.1f}s avant nouvelle tentative...")
                        import asyncio
                        await asyncio.sleep(wait_time)
                    else:
                        break

            if last_exception:
                logger.error(f"Échec définitif après {max_retries + 1} tentatives pour {provider}")
                raise last_exception

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            circuit_breaker = circuit_breakers.get(provider)

            if not circuit_breaker or not circuit_breaker.is_available():
                logger.error(f"🔌 Circuit breaker ouvert pour {provider}")
                raise Exception(f"Service {provider} temporairement indisponible (circuit breaker ouvert)")

            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    if circuit_breaker:
                        circuit_breaker.record_success()
                    return result

                except Exception as e:
                    last_exception = e
                    logger.warning(f"Tentative {attempt + 1}/{max_retries + 1} échouée pour {provider}: {str(e)}")

                    if circuit_breaker:
                        circuit_breaker.record_failure()

                    if attempt < max_retries:
                        wait_time = backoff_factor ** attempt
                        logger.info(f"Attente de {wait_time:.1f}s avant nouvelle tentative...")
                        import time
                        time.sleep(wait_time)
                    else:
                        break

            if last_exception:
                logger.error(f"Échec définitif après {max_retries + 1} tentatives pour {provider}")
                raise last_exception

        # Retourner la version appropriée selon si la fonction est async
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator

def enhanced_error_handler(func: Callable) -> Callable:
    """
    Gestionnaire d'erreurs enrichi avec logging détaillé
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time

            # Log succès avec métriques
            logger.info(f"✅ {func.__name__} réussi en {execution_time:.2f}s")
            return result

        except Exception as e:
            execution_time = time.time() - start_time

            # Collecter les informations d'erreur
            error_info = {
                "function": func.__name__,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "execution_time": execution_time,
                "args": str(args) if len(str(args)) < 200 else str(args)[:200] + "...",
                "kwargs": {k: str(v) if len(str(v)) < 100 else str(v)[:100] + "..." for k, v in kwargs.items()},
                "stack_trace": traceback.format_exc()
            }

            # Log détaillé de l'erreur
            logger.error(f"❌ {func.__name__} a échoué après {execution_time:.2f}s: {error_info}")

            # Enrichir l'exception avec des informations de contexte
            e.error_context = error_info
            raise e

    return wrapper

def timeout_handler(timeout_seconds: int = 30):
    """
    Décorateur pour gérer les timeouts de manière compatible async
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            import asyncio
            try:
                result = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout_seconds)
                return result
            except asyncio.TimeoutError:
                logger.error(f"⏱️ {func.__name__} a timeout après {timeout_seconds}s")
                raise Exception(f"Timeout après {timeout_seconds}s")

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Pour les fonctions sync dans un contexte async, on utilise une approche plus simple
            import time
            import threading

            result = [None]
            exception = [None]

            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    exception[0] = e

            thread = threading.Thread(target=target)
            thread.start()
            thread.join(timeout=timeout_seconds)

            if thread.is_alive():
                logger.error(f"⏱️ {func.__name__} a timeout après {timeout_seconds}s")
                raise Exception(f"Timeout après {timeout_seconds}s")

            if exception[0]:
                raise exception[0]

            return result[0]

        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator

def get_error_stats() -> Dict[str, Any]:
    """Retourne les statistiques d'erreurs des circuit breakers"""
    return {
        provider: {
            "state": cb.state,
            "failure_count": cb.failure_count,
            "last_failure_time": cb.last_failure_time,
            "is_available": cb.is_available()
        }
        for provider, cb in circuit_breakers.items()
    }

def reset_circuit_breaker(provider: str) -> bool:
    """Reset manuel d'un circuit breaker"""
    if provider in circuit_breakers:
        circuit_breakers[provider].failure_count = 0
        circuit_breakers[provider].state = "CLOSED"
        circuit_breakers[provider].last_failure_time = None
        logger.info(f"🔄 Circuit breaker {provider} remis à zéro")
        return True
    return False

def create_safe_llm_call(provider: str, timeout: int = 60):
    """
    Crée un appel LLM sécurisé avec retry et circuit breaker (sans timeout pour éviter les problèmes de signal)
    """
    @with_retry_and_circuit_breaker(provider, max_retries=2)
    @enhanced_error_handler
    def safe_llm_call(llm_func, *args, **kwargs):
        return llm_func(*args, **kwargs)

    return safe_llm_call