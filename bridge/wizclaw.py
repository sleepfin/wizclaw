"""Standalone entry point for wizclaw.exe (PyInstaller).

This file is the target of the PyInstaller spec.  It must NOT be run
as ``python bridge/wizclaw.py`` from within the repo (the package
import would fail).  Use ``python -m bridge`` for development instead.
"""

from bridge.cli import main

if __name__ == "__main__":
    main()
