"""HTTP client for the local OpenClaw agent."""

import logging
from typing import Optional

import httpx

logger = logging.getLogger("wizclaw.openclaw")

_DEFAULT_TIMEOUT = 120.0


class OpenClawClient:
    """Thin wrapper around the OpenClaw HTTP API.

    Provides both sync (health_check) and async (aquery) methods.
    """

    def __init__(self, base_url: str, token: str = "", agent_id: str = "main", timeout: float = _DEFAULT_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.agent_id = agent_id
        self.timeout = timeout

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def aquery(self, user_query: str, system_prompt: Optional[str] = None) -> str:
        """Send a query to OpenClaw asynchronously and return the assistant's reply."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_query})

        payload = {
            "model": f"openclaw:{self.agent_id}",
            "messages": messages,
        }

        url = f"{self.base_url}/v1/chat/completions"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(url, json=payload, headers=self._headers())
                resp.raise_for_status()
                data = resp.json()
                choices = data.get("choices", [])
                if not choices:
                    return "[OpenClaw] No response choices returned."
                return choices[0].get("message", {}).get("content", "")
            except httpx.ConnectError:
                raise ConnectionError(f"Cannot connect to OpenClaw at {self.base_url}")
            except httpx.HTTPStatusError as e:
                raise RuntimeError(f"OpenClaw returned HTTP {e.response.status_code}: {e.response.text[:500]}")

    async def ahealth_check(self) -> bool:
        """Return True if OpenClaw is reachable (async)."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/v1/models", headers=self._headers())
                return resp.status_code == 200
        except Exception:
            return False

    def health_check(self) -> bool:
        """Return True if OpenClaw is reachable (sync, for CLI use)."""
        try:
            resp = httpx.get(
                f"{self.base_url}/v1/models",
                headers=self._headers(),
                timeout=5.0,
            )
            return resp.status_code == 200
        except Exception:
            return False
