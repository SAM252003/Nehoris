"""
Client Ollama minimal et robuste.

Dépendances: `requests`
ENV supportés:
  - OLLAMA_HOST (ex: http://localhost:11434)
  - OLLAMA_TIMEOUT (sec)
"""

from __future__ import annotations
import os
from typing import Any, Dict, Iterable, List, Optional, Generator, Union
import requests


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, model: str = "llama3.1", host: Optional[str] = None, timeout: Optional[int] = None):
        self.model = model
        self.host = (host or os.getenv("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")
        self.timeout = int(timeout or os.getenv("OLLAMA_TIMEOUT") or 180)
        self._session = requests.Session()

    # ----------------- API publique -----------------
    def answer(
        self,
        messages: Union[List[Dict[str, str]], str],
        model: Optional[str] = None,
        temperature: float = 0.1,
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> str:
        """
        Renvoie uniquement le texte. Utilise /api/chat, fallback /api/generate.
        - messages: [{"role":"user","content":"..."}] ou str
        - options: dict d'options Ollama (ex: {"top_p":0.9,"num_ctx":4096,"stop":["###"]})
        - stream: si True, lève une erreur (ce client expose un générateur séparé: answer_stream)
        """
        if stream:
            raise ValueError("Use answer_stream(...) for streaming.")
        return self.answer_with_meta(messages, model=model, temperature=temperature, options=options)["text"]

    def answer_with_meta(
        self,
        messages: Union[List[Dict[str, str]], str],
        model: Optional[str] = None,
        temperature: float = 0.1,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Retourne {"text": str, "sources": []}
        - Essaye d'abord /api/chat
        - Fallback /api/generate
        """
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        _model = model or self.model
        _opts = {"temperature": float(temperature)}
        if options:
            _opts.update(options)

        # Tentative chat
        try:
            text = self._chat(messages, _model, _opts, stream=False)
            if text:
                return {"text": text, "sources": []}
        except Exception as e:
            # On tente le fallback seulement si l'API chat échoue
            # (on ne masque pas l'erreur si generate échoue aussi)
            chat_err = e
        else:
            chat_err = None

        # Fallback generate
        prompt = "\n".join([m.get("content", "") for m in messages])
        try:
            text = self._generate(prompt, _model, _opts, stream=False)
            return {"text": text, "sources": []}
        except Exception as gen_err:
            raise OllamaError(f"Ollama failed (chat: {chat_err!r}, generate: {gen_err!r})")

    def answer_stream(
        self,
        messages: Union[List[Dict[str, str]], str],
        model: Optional[str] = None,
        temperature: float = 0.1,
        options: Optional[Dict[str, Any]] = None,
    ) -> Generator[str, None, None]:
        """
        Générateur de texte (streaming) via /api/chat, fallback /api/generate si besoin.
        Yield des morceaux de texte au fur et à mesure.
        """
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        _model = model or self.model
        _opts = {"temperature": float(temperature)}
        if options:
            _opts.update(options)

        try:
            yield from self._chat_stream(messages, _model, _opts)
            return
        except Exception:
            pass

        # fallback
        prompt = "\n".join([m.get("content", "") for m in messages])
        yield from self._generate_stream(prompt, _model, _opts)

    def health(self) -> bool:
        try:
            r = self._session.get(f"{self.host}/api/tags", timeout=self.timeout)
            r.raise_for_status()
            return True
        except Exception:
            return False

    def list_models(self) -> List[str]:
        r = self._session.get(f"{self.host}/api/tags", timeout=self.timeout)
        r.raise_for_status()
        data = r.json() or {}
        return [m.get("name", "") for m in data.get("models", []) if m.get("name")]

    # ----------------- internes -----------------
    def _chat(self, messages: List[Dict[str, str]], model: str, options: Dict[str, Any], stream: bool) -> str:
        url = f"{self.host}/api/chat"
        resp = self._session.post(
            url,
            json={"model": model, "messages": messages, "options": options, "stream": stream},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        # formats possibles selon versions
        if isinstance(data, dict):
            if "message" in data and isinstance(data["message"], dict):
                return data["message"].get("content", "") or ""
        if isinstance(data, list) and data:
            msg = data[-1].get("message", {})
            return (msg or {}).get("content", "") or ""
        return ""

    def _chat_stream(self, messages: List[Dict[str, str]], model: str, options: Dict[str, Any]) -> Iterable[str]:
        url = f"{self.host}/api/chat"
        with self._session.post(
            url,
            json={"model": model, "messages": messages, "options": options, "stream": True},
            timeout=self.timeout,
            stream=True,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                # suivant versions: lignes JSON avec {"message":{"content":"..."}, "done":false}
                try:
                    import json
                    obj = json.loads(line)
                    chunk = ((obj.get("message") or {}).get("content") or "")
                    if chunk:
                        yield chunk
                except Exception:
                    # si ce n'est pas du JSON, on yield la ligne brute
                    yield line

    def _generate(self, prompt: str, model: str, options: Dict[str, Any], stream: bool) -> str:
        url = f"{self.host}/api/generate"
        resp = self._session.post(
            url,
            json={"model": model, "prompt": prompt, "options": options, "stream": stream},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        # format: {"response": "...", "done": true, ...}
        return data.get("response", "") or ""

    def _generate_stream(self, prompt: str, model: str, options: Dict[str, Any]) -> Iterable[str]:
        url = f"{self.host}/api/generate"
        with self._session.post(
            url,
            json={"model": model, "prompt": prompt, "options": options, "stream": True},
            timeout=self.timeout,
            stream=True,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    import json
                    obj = json.loads(line)
                    chunk = obj.get("response") or ""
                    if chunk:
                        yield chunk
                except Exception:
                    yield line
