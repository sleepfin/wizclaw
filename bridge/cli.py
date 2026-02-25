"""CLI entry points for wisclaw bridge daemon.

Single-command experience:
    wisclaw           — auto-config (first run) + start OpenClaw + connect
    wisclaw config    — re-run the configuration wizard
    wisclaw version   — print version and exit
"""

import argparse
import asyncio
import getpass
import logging
import platform
import sys

from bridge import __version__
from bridge.config import load_config, save_config, get_config_path, _DEFAULTS
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


def _getpass_safe(prompt: str) -> str:
    """getpass with fallback for terminals where it fails (e.g. Git Bash mintty)."""
    try:
        return getpass.getpass(prompt)
    except (OSError, EOFError):
        print("WARNING: Unable to hide input. Your input will be visible.")
        return input(prompt)


def _setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ---------------------------------------------------------------------------
# Interactive configuration wizard
# ---------------------------------------------------------------------------

def _run_config_wizard(force: bool = False) -> dict:
    """Run the interactive configuration wizard and return the saved config."""
    cfg = load_config()

    if not force and cfg.get("api_key"):
        print(f"Config already exists at {get_config_path()}")
        print("Use 'wisclaw config --force' to overwrite.")
        return cfg

    print("=== wisclaw setup ===\n")

    cloud_url = input(
        f"Cloud WebSocket URL [{cfg.get('cloud_url', _DEFAULTS['cloud_url'])}]: "
    ).strip()
    if cloud_url:
        if not cloud_url.startswith("wss://"):
            print("WARNING: Cloud URL should use wss:// for encrypted connections.")
        cfg = {**cfg, "cloud_url": cloud_url}

    api_key = _getpass_safe("API Key (evo_...): ").strip()
    if api_key:
        if not api_key.startswith("evo_"):
            print("WARNING: API key does not start with 'evo_'. Please verify.")
        cfg = {**cfg, "api_key": api_key}

    openclaw_url = input(
        f"OpenClaw URL [{cfg.get('openclaw_url', _DEFAULTS['openclaw_url'])}]: "
    ).strip()
    if openclaw_url:
        cfg = {**cfg, "openclaw_url": openclaw_url}

    token_display = "****" if cfg.get("openclaw_token") else "none"
    openclaw_token = _getpass_safe(
        f"OpenClaw Token (empty for none) [current: {token_display}]: "
    ).strip()
    cfg = {**cfg, "openclaw_token": openclaw_token}

    agent_id = input(
        f"OpenClaw Agent ID [{cfg.get('openclaw_agent_id', _DEFAULTS['openclaw_agent_id'])}]: "
    ).strip()
    if agent_id:
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
    print(f"wisclaw {__version__}")


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
    print(f"Starting wisclaw bridge daemon...")
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
        prog="wisclaw",
        description="Bridge daemon connecting local OpenClaw to the cloud",
    )
    subparsers = parser.add_subparsers(dest="command")

    # wisclaw config [--force]
    config_parser = subparsers.add_parser(
        "config", help="Re-run the configuration wizard",
    )
    config_parser.add_argument(
        "--force", action="store_true", help="Overwrite existing config",
    )

    # wisclaw version
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
