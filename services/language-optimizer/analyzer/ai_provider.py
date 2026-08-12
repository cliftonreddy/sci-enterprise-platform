"""
analyzer/ai_provider.py — pluggable AI backend for Tier 3 analysis.

Implement AIProvider (three methods) to swap Claude for any model.
Built-in providers: AnthropicProvider, OpenAIProvider, OllamaProvider.

Usage in server.py — select via AI_PROVIDER env var:
    AI_PROVIDER=anthropic   ANTHROPIC_API_KEY=sk-...
    AI_PROVIDER=openai      OPENAI_API_KEY=sk-...   OPENAI_MODEL=gpt-4o
    AI_PROVIDER=ollama      OLLAMA_URL=http://host:11434  OLLAMA_MODEL=llama3
"""
from abc import ABC, abstractmethod
import requests


class AIProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for logging."""
        ...

    @property
    @abstractmethod
    def available(self) -> bool:
        """True if credentials/config are present."""
        ...

    @abstractmethod
    def complete(self, prompt: str, max_tokens: int = 4000) -> str:
        """Send prompt, return text response. Raise on API error."""
        ...


class AnthropicProvider(AIProvider):
    """Claude via Anthropic Messages API."""

    _API_URL = "https://api.anthropic.com/v1/messages"
    _MODEL   = "claude-sonnet-4-6"

    def __init__(self, api_key: str = ""):
        self._api_key = api_key or ""
        self._headers = {
            "Content-Type": "application/json",
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-dangerous-direct-browser-access": "true",
        }

    @property
    def name(self) -> str:
        return "Anthropic (Claude)"

    @property
    def available(self) -> bool:
        return bool(self._api_key and self._api_key.startswith("sk-ant-"))

    def complete(self, prompt: str, max_tokens: int = 4000) -> str:
        payload = {
            "model": self._MODEL,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        r = requests.post(self._API_URL, headers=self._headers, json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise RuntimeError(f"Anthropic API error: {data['error']['message']}")
        return data["content"][0]["text"]


class OpenAIProvider(AIProvider):
    """GPT-4o (or any OpenAI-compatible model) via Chat Completions API."""

    _API_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key: str = "", model: str = "gpt-4o"):
        self._api_key = api_key or ""
        self._model   = model
        self._headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

    @property
    def name(self) -> str:
        return f"OpenAI ({self._model})"

    @property
    def available(self) -> bool:
        return bool(self._api_key and self._api_key.startswith("sk-"))

    def complete(self, prompt: str, max_tokens: int = 4000) -> str:
        payload = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        r = requests.post(self._API_URL, headers=self._headers, json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise RuntimeError(f"OpenAI API error: {data['error']['message']}")
        return data["choices"][0]["message"]["content"]


class OllamaProvider(AIProvider):
    """Local model via Ollama (llama3, mistral, codellama, etc.)."""

    def __init__(self, url: str = "http://localhost:11434", model: str = "llama3"):
        self._url   = url.rstrip("/")
        self._model = model

    @property
    def name(self) -> str:
        return f"Ollama ({self._model} @ {self._url})"

    @property
    def available(self) -> bool:
        try:
            r = requests.get(f"{self._url}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def complete(self, prompt: str, max_tokens: int = 4000) -> str:
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        r = requests.post(f"{self._url}/api/generate", json=payload, timeout=300)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise RuntimeError(f"Ollama error: {data['error']}")
        return data["response"]
