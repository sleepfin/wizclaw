"""WebSocket client that connects the local bridge daemon to the cloud."""

import asyncio
import json
import logging
import ssl
import time

import certifi
import websockets

from bridge import __version__
from bridge.openclaw import OpenClawClient

logger = logging.getLogger("wizclaw.client")


class BridgeClient:
    """Connects to the cloud WS endpoint, forwards tool requests to OpenClaw."""

    def __init__(self, config: dict):
        self.cloud_url = config["cloud_url"]
        self.api_key = config["api_key"]
        self.reconnect_max = config.get("reconnect_interval_max", 30)
        self.request_timeout = config.get("request_timeout", 120)
        self.openclaw = OpenClawClient(
            base_url=config["openclaw_url"],
            token=config.get("openclaw_token", ""),
            agent_id=config.get("openclaw_agent_id", "main"),
            timeout=self.request_timeout,
        )

    async def run(self):
        """Main loop with exponential-backoff reconnection."""
        backoff = 1
        while True:
            try:
                await self._connect_and_listen()
                backoff = 1  # reset on clean disconnect
            except (
                websockets.ConnectionClosedError,
                websockets.InvalidStatusCode,
                ConnectionRefusedError,
                OSError,
            ) as e:
                logger.warning("Connection lost: %s. Reconnecting in %ds...", e, backoff)
            except Exception as e:
                logger.error("Unexpected error: %s. Reconnecting in %ds...", e, backoff)

            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, self.reconnect_max)

    async def _connect_and_listen(self):
        url = f"{self.cloud_url}?api_key={self.api_key}"
        logger.info("Connecting to %s", self.cloud_url)

        ssl_ctx = None
        if self.cloud_url.startswith("wss://"):
            ssl_ctx = ssl.create_default_context(cafile=certifi.where())

        async with websockets.connect(url, ping_interval=30, ping_timeout=10, ssl=ssl_ctx) as ws:
            logger.info("Connected to cloud")
            await self._send_status(ws)

            async for raw in ws:
                await self._handle_message(ws, raw)

    async def _handle_message(self, ws, raw: str):
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Bad JSON from cloud: %s", raw[:200])
            return

        msg_type = msg.get("type")

        if msg_type == "tool_request":
            request_id = msg.get("request_id", "")
            tool_name = msg.get("tool_name", "")
            arguments = msg.get("arguments", {})
            logger.info("Tool request: id=%s tool=%s", request_id, tool_name)
            await self._handle_tool_request(ws, request_id, tool_name, arguments)

        elif msg_type == "ping":
            await ws.send(json.dumps({"type": "pong"}))

        else:
            logger.debug("Unknown message type: %s", msg_type)

    async def _handle_tool_request(self, ws, request_id: str, tool_name: str, arguments: dict):
        """Execute a tool request and send the response back."""
        t_recv = time.time()
        logger.info("[TIMING] tool_request RECEIVED id=%s tool=%s", request_id, tool_name)

        response = {
            "type": "tool_response",
            "request_id": request_id,
            "success": False,
            "result": None,
            "error": None,
        }

        try:
            if tool_name == "local_openclaw":
                query = arguments.get("query", "")
                logger.info("[TIMING] OpenClaw query START id=%s", request_id)
                result = await self.openclaw.aquery(query)
                t_oclaw = time.time()
                logger.info("[TIMING] OpenClaw query DONE id=%s (%.3fs)", request_id, t_oclaw - t_recv)
                response["success"] = True
                response["result"] = result
            else:
                response["error"] = f"Unsupported tool: {tool_name}"
        except ConnectionError as e:
            response["error"] = f"OpenClaw unreachable: {e}"
            logger.error("OpenClaw unreachable: %s", e)
        except Exception as e:
            response["error"] = f"Tool execution failed: {e}"
            logger.error("Tool execution failed: %s", e, exc_info=True)

        await ws.send(json.dumps(response))
        t_sent = time.time()
        logger.info("[TIMING] tool_response SENT id=%s success=%s (%.3fs total since recv)", request_id, response["success"], t_sent - t_recv)

    async def _send_status(self, ws):
        """Send status message after connecting."""
        openclaw_ok = await self.openclaw.ahealth_check()
        status = {
            "type": "status",
            "openclaw_status": "healthy" if openclaw_ok else "unreachable",
            "client_version": __version__,
        }
        await ws.send(json.dumps(status))
        logger.info("Status sent: openclaw=%s", status["openclaw_status"])
