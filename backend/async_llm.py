"""
Module pour l'optimisation asynchrone des appels LLM
Permet de traiter plusieurs prompts en parallèle avec pool de connexions
"""
import asyncio
import time
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

from src.geo_agent.models import get_llm_client
from backend.cache import cache

# Configuration du pool
MAX_CONCURRENT_REQUESTS = 3  # Réduit pour éviter la surcharge des APIs
REQUEST_TIMEOUT = 180  # secondes (3 minutes pour les gros audits)

logger = logging.getLogger(__name__)

class AsyncLLMPool:
    def __init__(self, max_workers: int = MAX_CONCURRENT_REQUESTS):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.active_requests = 0

    def _execute_llm_request(self, provider: str, model: Optional[str], temperature: float, prompt: str) -> Tuple[str, str, float]:
        """Exécute une requête LLM unique avec mesure du temps et gestion d'erreur robuste"""
        from backend.error_handler import create_safe_llm_call

        start_time = time.time()

        try:
            # Vérifier le cache d'abord
            cache_key = f"llm:{provider}:{model}:{cache._generate_key(prompt, temperature)}"
            cached_result = cache.get(cache_key)

            if cached_result:
                logger.info(f"✅ Cache HIT pour {provider}")
                return cached_result[0], cached_result[1], time.time() - start_time

            # Créer un appel LLM sécurisé
            safe_call = create_safe_llm_call(provider, timeout=25)

            def llm_call():
                client = get_llm_client(provider)
                if not client:
                    raise Exception(f"Provider {provider} non disponible")
                return client.answer(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    model=model
                )

            # Appel LLM sécurisé avec retry et circuit breaker
            response = safe_call(llm_call)
            execution_time = time.time() - start_time

            # Mettre en cache seulement si succès
            cache.set(cache_key, (response, provider), 1800)  # 30 minutes
            logger.info(f"✅ LLM {provider} réussi en {execution_time:.2f}s")

            return response, provider, execution_time

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)

            # Différencier les types d'erreur pour un meilleur debugging
            if "timeout" in error_msg.lower():
                logger.error(f"⏱️ Timeout LLM {provider} après {execution_time:.2f}s")
                return f"⏱️ Timeout {provider} (>{int(execution_time)}s)", provider, execution_time
            elif "circuit breaker" in error_msg.lower():
                logger.error(f"🔌 Circuit breaker ouvert pour {provider}")
                return f"🔌 {provider} temporairement indisponible", provider, execution_time
            elif "non disponible" in error_msg.lower():
                logger.error(f"❌ Provider {provider} non configuré")
                return f"❌ {provider} non configuré", provider, execution_time
            else:
                logger.error(f"❌ Erreur LLM {provider}: {error_msg}")
                return f"❌ Erreur {provider}: {error_msg[:100]}", provider, execution_time

    async def process_batch_async(self, requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Traite un batch de requêtes LLM en parallèle

        Args:
            requests: Liste de dict avec keys: provider, model, temperature, prompt

        Returns:
            Liste des résultats avec timing et métriques
        """
        start_time = time.time()
        results = []

        # Créer les tâches
        loop = asyncio.get_event_loop()
        tasks = []

        for i, req in enumerate(requests):
            task = loop.run_in_executor(
                self.executor,
                self._execute_llm_request,
                req["provider"],
                req.get("model"),
                req.get("temperature", 0.2),
                req["prompt"]
            )
            tasks.append((i, task))

        # Exécuter en parallèle avec timeout
        try:
            completed_tasks = await asyncio.wait_for(
                asyncio.gather(*[task for _, task in tasks], return_exceptions=True),
                timeout=REQUEST_TIMEOUT
            )

            for i, result in enumerate(completed_tasks):
                if isinstance(result, Exception):
                    results.append({
                        "index": i,
                        "response": f"Erreur: {str(result)}",
                        "provider": requests[i]["provider"],
                        "execution_time": REQUEST_TIMEOUT,
                        "error": True
                    })
                else:
                    response, provider, exec_time = result
                    results.append({
                        "index": i,
                        "response": response,
                        "provider": provider,
                        "execution_time": exec_time,
                        "error": False
                    })

        except asyncio.TimeoutError:
            logger.error(f"Timeout global après {REQUEST_TIMEOUT}s")
            for i, req in enumerate(requests):
                results.append({
                    "index": i,
                    "response": "Timeout",
                    "provider": req["provider"],
                    "execution_time": REQUEST_TIMEOUT,
                    "error": True
                })

        total_time = time.time() - start_time

        # Ajouter les métriques globales
        return {
            "results": results,
            "metrics": {
                "total_requests": len(requests),
                "successful_requests": sum(1 for r in results if not r["error"]),
                "failed_requests": sum(1 for r in results if r["error"]),
                "total_time": total_time,
                "average_time": sum(r["execution_time"] for r in results) / len(results) if results else 0,
                "cache_hits": sum(1 for r in results if r["execution_time"] < 0.1),  # Approximation
                "parallel_efficiency": len(requests) / total_time if total_time > 0 else 0
            }
        }

    def close(self):
        """Ferme le pool d'exécution"""
        self.executor.shutdown(wait=True)

# Instance globale
llm_pool = AsyncLLMPool()

async def process_llm_batch(provider_requests: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Interface principale pour traiter un batch de requêtes LLM

    Args:
        provider_requests: Liste de requêtes avec provider, model, temperature, prompt

    Returns:
        Résultats avec métriques de performance
    """
    return await llm_pool.process_batch_async(provider_requests)

def optimize_request_batching(prompts: List[str], provider: str, model: Optional[str] = None, temperature: float = 0.2) -> List[Dict[str, Any]]:
    """
    Optimise le batching des requêtes pour un provider donné
    """
    # Grouper les prompts similaires pour maximiser le cache hit
    from collections import defaultdict
    import hashlib

    grouped_prompts = defaultdict(list)

    for i, prompt in enumerate(prompts):
        # Hash basé sur les premiers mots pour grouper les prompts similaires
        prompt_hash = hashlib.md5(prompt[:50].encode()).hexdigest()[:8]
        grouped_prompts[prompt_hash].append((i, prompt))

    # Créer les requêtes optimisées
    requests = []
    for group_prompts in grouped_prompts.values():
        for i, prompt in group_prompts:
            requests.append({
                "index": i,
                "provider": provider,
                "model": model,
                "temperature": temperature,
                "prompt": prompt
            })

    return requests