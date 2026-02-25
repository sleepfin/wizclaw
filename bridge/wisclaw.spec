# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for building wisclaw.exe."""

import os

import certifi

# SPECPATH is the directory containing this spec file (bridge/)
spec_dir = os.path.abspath(SPECPATH)
repo_root = os.path.dirname(spec_dir)

# Bundle certifi CA certificates so HTTPS works in the packaged binary
certifi_dir = os.path.dirname(certifi.where())

a = Analysis(
    [os.path.join(spec_dir, "wisclaw.py")],
    pathex=[repo_root],
    binaries=[],
    datas=[(certifi_dir, "certifi")],
    hiddenimports=[
        "yaml",
        "_yaml",
        "websockets",
        "websockets.client",
        "websockets.legacy",
        "websockets.legacy.client",
        "httpx",
        "httpx._transports",
        "httpx._transports.default",
        "httpcore",
        "httpcore._async",
        "httpcore._sync",
        "anyio",
        "anyio._backends",
        "anyio._backends._asyncio",
        "certifi",
        "h11",
        "h11._readers",
        "h11._writers",
        "sniffio",
        "idna",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="wisclaw",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
