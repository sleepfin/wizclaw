"""OpenClaw process detection and lifecycle management."""

import logging
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx

logger = logging.getLogger("wisclaw.launcher")

_STDERR_LOG = Path(tempfile.gettempdir()) / "openclaw-stderr.log"


class OpenClawLauncher:
    """Detect whether OpenClaw is running and start it if needed."""

    def __init__(
        self,
        url: str = "http://localhost:18789",
        start_timeout: int = 30,
        poll_interval: float = 0.5,
    ):
        self.url = url.rstrip("/")
        self.start_timeout = start_timeout
        self.poll_interval = poll_interval
        self._process: Optional[subprocess.Popen] = None
        self._stderr_file = None

    def is_running(self) -> bool:
        """Return True if OpenClaw responds to GET /v1/models."""
        try:
            resp = httpx.get(
                f"{self.url}/v1/models",
                timeout=3.0,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def find_executable(self) -> Optional[str]:
        """Locate the openclaw binary on PATH."""
        return shutil.which("openclaw")

    def start(self) -> bool:
        """Start openclaw gateway as a background process.

        Polls /v1/models until it returns 200 or the timeout expires.
        Returns True if OpenClaw becomes reachable within the timeout.
        """
        exe = self.find_executable()
        if exe is None:
            logger.error("openclaw executable not found on PATH")
            return False

        port = self._parse_port()

        logger.info("Starting openclaw gateway on port %s ...", port)
        try:
            self._stderr_file = open(_STDERR_LOG, "w", encoding="utf-8")
            self._process = subprocess.Popen(
                [exe, "gateway", "--port", str(port)],
                stdout=subprocess.DEVNULL,
                stderr=self._stderr_file,
            )
        except OSError as exc:
            logger.error("Failed to launch openclaw: %s", exc)
            self._close_stderr()
            return False

        return self._wait_until_ready()

    def ensure_running(self) -> bool:
        """Return True if OpenClaw is already running or was started successfully."""
        if self.is_running():
            logger.info("OpenClaw is already running at %s", self.url)
            return True

        success = self.start()

        # Handle race: another process started OpenClaw while we were launching
        if success and self._process is not None and self._process.poll() is not None:
            logger.info("OpenClaw was started by another process")
            self._close_stderr()
            self._process = None

        return success

    def terminate(self) -> None:
        """Terminate the managed OpenClaw process if we started it."""
        if self._process is not None and self._process.poll() is None:
            logger.info("Terminating managed OpenClaw process (pid=%d)", self._process.pid)
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._close_stderr()

    def _parse_port(self) -> int:
        """Extract port number from self.url, default 18789."""
        parsed = urlparse(self.url)
        return parsed.port or 18789

    def _close_stderr(self) -> None:
        """Close the stderr log file if open."""
        if self._stderr_file is not None:
            try:
                self._stderr_file.close()
            except Exception:
                pass
            self._stderr_file = None

    def _read_stderr_log(self) -> str:
        """Read the stderr log contents for diagnostics."""
        try:
            return _STDERR_LOG.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            return ""

    def _wait_until_ready(self) -> bool:
        """Poll the health endpoint until ready or timeout."""
        deadline = time.monotonic() + self.start_timeout
        while time.monotonic() < deadline:
            # Check if the process exited prematurely
            if self._process is not None and self._process.poll() is not None:
                self._close_stderr()
                stderr_output = self._read_stderr_log()
                logger.error(
                    "openclaw process exited with code %d",
                    self._process.returncode,
                )
                if stderr_output:
                    logger.error("openclaw stderr:\n%s", stderr_output)
                return False

            if self.is_running():
                logger.info("OpenClaw is ready at %s", self.url)
                return True

            time.sleep(self.poll_interval)

        self._close_stderr()
        stderr_output = self._read_stderr_log()
        logger.error(
            "OpenClaw did not become ready within %ds",
            self.start_timeout,
        )
        if stderr_output:
            logger.error("openclaw stderr:\n%s", stderr_output)
        return False
