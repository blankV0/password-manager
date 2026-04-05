# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — Password Manager v1.0.0
Build: pyinstaller PasswordManager.spec
Resultado: dist/PasswordManager/PasswordManager.exe
"""

import os
import sys
from pathlib import Path

ROOT = os.path.abspath(".")

# ── Dados que devem ser copiados junto ao .exe ──────────────────────────────
# (source, dest_dir_relativo_ao_exe)
datas = [
    # .env (configuração)
    (os.path.join(ROOT, ".env"), "."),
    # Pasta data/ (preferences, vault DB)
    (os.path.join(ROOT, "data"), "data"),
    # Pasta certs/ (CA do servidor)
    (os.path.join(ROOT, "certs"), "certs"),
    # Pacote gerador1 (módulos do colega)
    (os.path.join(ROOT, "gerador1"), "gerador1"),
]

# ── Hidden imports (módulos que PyInstaller pode não detetar) ────────────────
hidden_imports = [
    # cryptography (AES-GCM)
    "cryptography",
    "cryptography.hazmat.primitives.ciphers.aead",
    "cryptography.hazmat.primitives.kdf.scrypt",
    "cryptography.hazmat.backends",
    # argon2 (KDF)
    "argon2",
    "argon2.low_level",
    "argon2._password_hasher",
    # requests / urllib3
    "requests",
    "urllib3",
    # tkinter (normalmente incluído, mas por segurança)
    "tkinter",
    "tkinter.ttk",
    "tkinter.messagebox",
    "tkinter.simpledialog",
    # dotenv
    "dotenv",
    # src subpackages
    "src",
    "src.config",
    "src.config.settings",
    "src.core",
    "src.core.crypto",
    "src.core.encryption",
    "src.models",
    "src.models.local_auth",
    "src.services",
    "src.storage",
    "src.storage.vault_crypto",
    "src.ui",
    "src.ui.login_gui",
    "src.ui.vault_gui",
    "src.ui.settings_page",
    "src.ui.admin_panel",
    "src.utils",
    "src.utils.logging_config",
    "src.auth",
    # gerador1
    "gerador1.inicio",
    "gerador1.gerador",
    "gerador1.verificador",
    "gerador1.utilizador",
    "gerador1.politicas",
]

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "numpy", "pandas", "scipy", "PIL", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PasswordManager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # Sem janela de consola (windowed)
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PasswordManager",
)
