"""
Système de cache en mémoire pour optimiser les performances de l'API
"""
import hashlib
import time
from typing import Any, Dict, Optional
from functools import wraps

class MemoryCache:
    def __init__(self, default_ttl: int = 3600):  # 1 heure par défaut
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = default_ttl

    def _generate_key(self, *args, **kwargs) -> str:
        """Génère une clé unique basée sur les arguments"""
        key_data = str(args) + str(sorted(kwargs.items()))
        return hashlib.md5(key_data.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """Récupère une valeur du cache"""
        if key in self._cache:
            entry = self._cache[key]
            if time.time() < entry["expires_at"]:
                entry["hits"] += 1
                return entry["value"]
            else:
                # Supprime les entrées expirées
                del self._cache[key]
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Stocke une valeur dans le cache"""
        expires_at = time.time() + (ttl or self.default_ttl)
        self._cache[key] = {
            "value": value,
            "expires_at": expires_at,
            "created_at": time.time(),
            "hits": 0
        }

    def delete(self, key: str) -> bool:
        """Supprime une entrée du cache"""
        return self._cache.pop(key, None) is not None

    def clear(self) -> None:
        """Vide complètement le cache"""
        self._cache.clear()

    def stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du cache"""
        now = time.time()
        active_entries = [entry for entry in self._cache.values() if now < entry["expires_at"]]

        return {
            "total_entries": len(self._cache),
            "active_entries": len(active_entries),
            "expired_entries": len(self._cache) - len(active_entries),
            "total_hits": sum(entry["hits"] for entry in active_entries),
            "memory_usage_mb": len(str(self._cache)) / (1024 * 1024)
        }

    def cleanup(self) -> int:
        """Nettoie les entrées expirées"""
        now = time.time()
        expired_keys = [key for key, entry in self._cache.items() if now >= entry["expires_at"]]
        for key in expired_keys:
            del self._cache[key]
        return len(expired_keys)

# Instance globale du cache
cache = MemoryCache()

def cached(ttl: int = 3600, key_prefix: str = ""):
    """
    Décorateur pour mettre en cache les résultats de fonction

    Args:
        ttl: Durée de vie en secondes
        key_prefix: Préfixe pour la clé de cache
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Génère la clé de cache
            cache_key = f"{key_prefix}:{func.__name__}:{cache._generate_key(*args, **kwargs)}"

            # Tente de récupérer depuis le cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                print(f"✅ Cache HIT pour {func.__name__}")
                return cached_result

            # Exécute la fonction et met en cache
            print(f"🔄 Cache MISS pour {func.__name__}")
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result

        return wrapper
    return decorator

def cache_llm_response(provider: str, model: str, prompt: str, temperature: float):
    """Cache spécialisé pour les réponses LLM"""
    return cached(ttl=1800, key_prefix=f"llm:{provider}:{model}")  # 30 minutes

# Fonction utilitaire pour nettoyer périodiquement le cache
def schedule_cache_cleanup():
    """Lance un nettoyage périodique du cache (à appeler dans un scheduler)"""
    cleaned = cache.cleanup()
    if cleaned > 0:
        print(f"🧹 Cache nettoyé: {cleaned} entrées expirées supprimées")
    return cleaned