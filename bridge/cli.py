"""CLI entry points for wizclaw bridge daemon.

Single-command experience:
    wizclaw           — auto-config (first run) + start OpenClaw + connect
    wizclaw config    — re-run the configuration wizard
    wizclaw version   — print version and exit
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import platform
import ssl
import sys

import certifi
import httpx
import websockets

from bridge import __version__
from bridge.config import load_config, save_config, get_config_path, _DEFAULTS, detect_openclaw_config
from bridge.client import BridgeClient
from bridge.launcher import OpenClawLauncher
from bridge.openclaw import OpenClawClient


def _setup_windows():
    """Apply Windows-specific runtime fixes."""
    if platform.system() != "Windows":
        return

    # Force UTF-8 console output to avoid garbled text on non-UTF-8 codepages
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    # Use SelectorEventLoop for websockets compatibility on Windows
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _make_ssl_context() -> ssl.SSLContext:
    """Create an SSL context using certifi CA bundle.

    Needed for PyInstaller builds where the system CA store may be absent.
    """
    return ssl.create_default_context(cafile=certifi.where())


async def _check_ws_reachable(url: str) -> tuple[bool, str]:
    """Try a WebSocket handshake to verify the URL is reachable.

    The server will likely close with 4001 (no api_key), but a successful
    TCP + WS handshake proves the address is valid and reachable.
    """
    ssl_ctx = _make_ssl_context() if url.startswith("wss://") else None
    try:
        async with websockets.connect(url, open_timeout=5, ssl=ssl_ctx):
            return True, ""
    except websockets.exceptions.ConnectionClosedError:
        # Server closed after handshake (e.g. 4001) — address is reachable
        return True, ""
    except websockets.exceptions.InvalidHandshake:
        # Server rejected upgrade (403, 401, etc.) but TCP is reachable
        return True, ""
    except ConnectionResetError:
        # Server reset the connection (e.g. no api_key) — still reachable
        return True, ""
    except (ConnectionRefusedError, OSError) as e:
        return False, f"Cannot connect to {url}: [{type(e).__name__}] {e}"
    except asyncio.TimeoutError:
        return False, f"Connection timed out for {url}"
    except Exception as e:
        return False, f"Cannot connect to {url}: [{type(e).__name__}] {e}"


async def _check_api_key(cloud_url: str, api_key: str) -> tuple[bool, str]:
    """Verify the API key by connecting with it to the cloud WebSocket.

    If the server closes with code 4001, the key is invalid/revoked.
    If the connection stays open, the key is valid.
    """
    url = f"{cloud_url}?api_key={api_key}"
    ssl_ctx = _make_ssl_context() if cloud_url.startswith("wss://") else None
    try:
        async with websockets.connect(url, open_timeout=5, ssl=ssl_ctx) as ws:
            # Connection stayed open — key is valid
            await ws.close()
            return True, ""
    except websockets.exceptions.ConnectionClosedError as e:
        if e.code == 4001:
            return False, "API key is invalid or revoked"
        return False, f"Connection closed unexpectedly (code={e.code}): {e.reason}"
    except websockets.exceptions.InvalidStatus as e:
        status = getattr(e, "status_code", None) or getattr(e.response, "status_code", None)
        if status == 401 or status == 403:
            return False, "API key is invalid or revoked"
        return False, f"Server rejected connection (HTTP {status})"
    except (ConnectionRefusedError, OSError) as e:
        return False, f"Cannot connect to server: [{type(e).__name__}] {e}"
    except asyncio.TimeoutError:
        return False, "Connection timed out"
    except Exception as e:
        return False, f"Connection failed: {e}"


def _validate_cloud_url(url: str) -> tuple[bool, str]:
    """Validate cloud WebSocket URL format and reachability."""
    if not url.startswith(("ws://", "wss://")):
        return False, "URL must start with ws:// or wss://"
    return asyncio.run(_check_ws_reachable(url))


def _validate_api_key(api_key: str, cloud_url: str) -> tuple[bool, str]:
    """Validate API key format. Connectivity check is skipped because the
    server may reset connections before the WebSocket handshake completes,
    making it impossible to distinguish valid from invalid keys."""
    if not api_key.startswith("evo_"):
        return False, "API key must start with 'evo_'"
    if len(api_key) < 10:
        return False, "API key is too short"
    return True, ""


def _validate_openclaw_url(url: str) -> tuple[bool, str]:
    """Validate OpenClaw URL format and check health endpoint."""
    if not url.startswith(("http://", "https://")):
        return False, "URL must start with http:// or https://"
    try:
        resp = httpx.get(f"{url.rstrip('/')}/v1/models", timeout=5.0)
        if resp.status_code == 200:
            return True, ""
        return False, f"OpenClaw returned HTTP {resp.status_code}"
    except httpx.ConnectError:
        return False, f"Cannot connect to OpenClaw at {url}"
    except httpx.TimeoutException:
        return False, f"Connection timed out for {url}"
    except Exception as e:
        return False, f"Health check failed: {e}"


def _prompt_with_validation(
    prompt: str,
    default: str,
    validate_fn,
) -> str:
    """Prompt the user in a retry loop until validation passes.

    validate_fn receives the value and returns (ok, error_message).
    Ctrl+C or EOF exits the process cleanly.
    """
    while True:
        try:
            value = input(prompt).strip()
        except (KeyboardInterrupt, EOFError):
            print("\nConfiguration cancelled.")
            sys.exit(1)
        if not value:
            value = default
        ok, err = validate_fn(value)
        if ok:
            return value
        print(f"  ERROR: {err}")
        print("  Please try again.\n")


# ---------------------------------------------------------------------------
# Interactive configuration wizard
# ---------------------------------------------------------------------------

def _run_config_wizard(force: bool = False) -> dict:
    """Run the interactive configuration wizard and return the saved config."""
    cfg = load_config()

    if not force and cfg.get("api_key"):
        print(f"Config already exists at {get_config_path()}")
        print("Use 'wizclaw config --force' to overwrite.")
        return cfg

    print("=== wizclaw setup ===\n")

    # --- Cloud WebSocket URL (format + reachability) ---
    default_cloud = cfg.get("cloud_url", _DEFAULTS["cloud_url"])
    cloud_url = _prompt_with_validation(
        prompt=f"Cloud WebSocket URL [{default_cloud}]: ",
        default=default_cloud,
        validate_fn=_validate_cloud_url,
    )
    cfg = {**cfg, "cloud_url": cloud_url}

    # --- API Key (format + server verification) ---
    api_key = _prompt_with_validation(
        prompt="API Key (evo_...): ",
        default=cfg.get("api_key", _DEFAULTS["api_key"]),
        validate_fn=lambda key: _validate_api_key(key, cloud_url),
    )
    cfg = {**cfg, "api_key": api_key}

    # --- Auto-detect OpenClaw settings from ~/.openclaw/openclaw.json ---
    detected = detect_openclaw_config()

    # --- OpenClaw URL (format + health check, with skip option) ---
    default_openclaw = cfg.get("openclaw_url", _DEFAULTS["openclaw_url"])
    if detected.get("url"):
        default_openclaw = detected["url"]
        print(f"  (Auto-detected OpenClaw at {default_openclaw})")
    print("  (Enter 'skip' to skip connectivity check if OpenClaw is not running yet)")
    while True:
        try:
            raw = input(f"OpenClaw URL [{default_openclaw}]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nConfiguration cancelled.")
            sys.exit(1)
        if not raw:
            raw = default_openclaw
        if raw.lower() == "skip":
            cfg = {**cfg, "openclaw_url": default_openclaw}
            print(f"  Skipping connectivity check. Using: {default_openclaw}")
            break
        ok, err = _validate_openclaw_url(raw)
        if ok:
            cfg = {**cfg, "openclaw_url": raw}
            break
        print(f"  ERROR: {err}")
        print("  Enter a valid URL or 'skip' to skip.\n")

    # --- OpenClaw Token (optional, no connectivity check) ---
    if not cfg.get("openclaw_token") and detected.get("token"):
        detected_token = detected["token"]
        print(f"  Auto-detected OpenClaw token: {detected_token[:8]}...")
        cfg = {**cfg, "openclaw_token": detected_token}
    else:
        token_display = "****" if cfg.get("openclaw_token") else "none"
        try:
            openclaw_token = input(
                f"OpenClaw Token (empty to keep current, 'clear' to remove) [current: {token_display}]: "
            ).strip()
        except (KeyboardInterrupt, EOFError):
            print("\nConfiguration cancelled.")
            sys.exit(1)
        if openclaw_token.lower() == "clear":
            cfg = {**cfg, "openclaw_token": ""}
        elif openclaw_token:
            cfg = {**cfg, "openclaw_token": openclaw_token}

    # --- OpenClaw Agent ID (has default, no connectivity check) ---
    default_agent = cfg.get("openclaw_agent_id", _DEFAULTS["openclaw_agent_id"])
    try:
        agent_id = input(f"OpenClaw Agent ID [{default_agent}]: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nConfiguration cancelled.")
        sys.exit(1)
    if not agent_id:
        agent_id = default_agent
    cfg = {**cfg, "openclaw_agent_id": agent_id}

    save_config(cfg)
    print(f"\nConfig saved to {get_config_path()}")
    return cfg


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------

def cmd_config(args):
    """Re-run the configuration wizard."""
    is_force = getattr(args, "force", False)
    _run_config_wizard(force=is_force)


def cmd_version(_args):
    """Print version and exit."""
    print(f"wizclaw {__version__}")


def cmd_run(_args):
    """Default command: auto-config + ensure OpenClaw + connect to cloud."""
    cfg = load_config()

    # Step 1: first-run configuration wizard if no API key
    if not cfg.get("api_key"):
        print("No configuration found. Starting setup wizard...\n")
        cfg = _run_config_wizard(force=True)
        if not cfg.get("api_key"):
            print("API key is required. Aborting.")
            sys.exit(1)
        print()

    # Step 2: auto-start OpenClaw if enabled
    launcher = None
    if cfg.get("openclaw_auto_start", True):
        launcher = OpenClawLauncher(url=cfg["openclaw_url"])
        if not launcher.ensure_running():
            if launcher.find_executable() is None:
                print("OpenClaw is not installed.")
                print("Install it from: https://github.com/anthropics/openclaw")
                print("Or disable auto-start: set openclaw_auto_start to false in config.")
                sys.exit(1)
            else:
                print("Failed to start OpenClaw. Check logs for details.")
                sys.exit(1)
    else:
        # Auto-start disabled — just check connectivity
        oc = OpenClawClient(
            base_url=cfg["openclaw_url"],
            token=cfg.get("openclaw_token", ""),
            agent_id=cfg.get("openclaw_agent_id", "main"),
        )
        if not oc.health_check():
            print(f"WARNING: OpenClaw not reachable at {cfg['openclaw_url']}")
            print("Bridge will keep retrying after connecting to cloud.\n")

    # Step 3: connect to cloud
    print(f"Starting wizclaw bridge daemon...")
    print(f"  Cloud:    {cfg['cloud_url']}")
    print(f"  OpenClaw: {cfg['openclaw_url']}")
    print(f"  Config:   {get_config_path()}")
    print()

    client = BridgeClient(cfg)
    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        if launcher is not None:
            launcher.terminate()


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def main():
    _setup_windows()
    _setup_logging()

    parser = argparse.ArgumentParser(
        prog="wizclaw",
        description="Bridge daemon connecting local OpenClaw to the cloud",
    )
    subparsers = parser.add_subparsers(dest="command")

    # wizclaw config [--force]
    config_parser = subparsers.add_parser(
        "config", help="Re-run the configuration wizard",
    )
    config_parser.add_argument(
        "--force", action="store_true", help="Overwrite existing config",
    )

    # wizclaw version
    subparsers.add_parser("version", help="Show version")

    args = parser.parse_args()

    if args.command == "config":
        cmd_config(args)
    elif args.command == "version":
        cmd_version(args)
    else:
        # Default: no subcommand → run the bridge
        cmd_run(args)


if __name__ == "__main__":
    main()
