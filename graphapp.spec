# -*- mode: python ; coding: utf-8 -*-
# Eseguibile Windows di GraphApp: pyinstaller graphapp.spec  ->  dist/GraphApp/GraphApp.exe
# Modalità a cartella (onedir): l'avvio è molto più rapido di un singolo .exe con Qt, matplotlib e scipy.
import os
import re

from PyInstaller.utils.win32.versioninfo import (FixedFileInfo, StringFileInfo, StringStruct, StringTable,
                                                 VarFileInfo, VarStruct, VSVersionInfo)

# versione dal tag della release (GRAPHAPP_VERSION=v1.2.3, impostata da release.yml); 0.0.0 nelle build locali
match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", os.environ.get("GRAPHAPP_VERSION", ""))
numbers = tuple(int(n) for n in match.groups()) + (0,) if match else (0, 0, 0, 0)
app_version = ".".join(str(n) for n in numbers[:3])

# risorsa di versione (Proprietà → Dettagli): un .exe senza metadati è più facilmente scambiato per malware
version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=numbers, prodvers=numbers),
    kids=[
        StringFileInfo([StringTable('040904B0', [
            StringStruct('CompanyName', 'Giuseppe Piscopo'),
            StringStruct('FileDescription', 'GraphApp'),
            StringStruct('FileVersion', app_version),
            StringStruct('InternalName', 'GraphApp'),
            StringStruct('LegalCopyright', 'Copyright 2026 Giuseppe Piscopo, Apache License 2.0'),
            StringStruct('OriginalFilename', 'GraphApp.exe'),
            StringStruct('ProductName', 'GraphApp'),
            StringStruct('ProductVersion', app_version),
        ])]),
        VarFileInfo([VarStruct('Translation', [1033, 1200])]),  # inglese (USA), Unicode
    ],
)

a = Analysis(
    ['graphapp.py'],
    pathex=[],
    binaries=[],
    # file d'esempio aperti da «Carica dati…» e lingue dell'interfaccia (tutta la cartella: una lingua nuova
    # si aggiunge con il solo file .json)
    datas=[('data/examples', 'data/examples'), ('src/locales', 'src/locales')],
    # backend caricati da matplotlib solo al salvataggio dell'immagine (non visibili all'analisi degli import)
    hiddenimports=['matplotlib.backends.backend_pdf', 'matplotlib.backends.backend_svg'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'PyQt5', 'PySide2', 'PySide6', 'IPython', 'pytest'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GraphApp',
    debug=False,
    strip=False,
    upx=False,
    console=False,  # applicazione a finestre, senza console
    version=version_info,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='GraphApp',
)
