# -*- mode: python ; coding: utf-8 -*-
# Eseguibile Windows di GraphApp: pyinstaller graphapp.spec  ->  dist/GraphApp/GraphApp.exe
# Modalità a cartella (onedir): l'avvio è molto più rapido di un singolo .exe con Qt, matplotlib e scipy.

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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='GraphApp',
)
