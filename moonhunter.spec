
# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_submodules

# Colectăm toate submodulele pentru h3 și timezonefinder
h3_modules = collect_submodules('h3')
timezonefinder_modules = collect_submodules('timezonefinder')

# Definim calea pentru fișierele de date
poze_path = 'poze_cer'
poze_files = []
if os.path.exists(poze_path):
    for file in os.listdir(poze_path):
        poze_files.append((os.path.join(poze_path, file), os.path.join('poze_cer', file)))

a = Analysis(
    ['moonhunter.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('compass.png', '.'),
        ('lista_localitati_cu_statii.xlsx', '.'),
        ('de421.bsp', '.'),
        # Adăugăm toate fișierele din folderul poze_cer
        *poze_files,
    ],
    hiddenimports=[
        *h3_modules,
        *timezonefinder_modules,
        'importlib.metadata',
        'skyfield',
        'skyfield.api',
        'skyfield.almanac',
        'pandas',
        'pytz',
        'requests',
        'requests.packages',
        'requests.adapters',
        'requests.auth',
        'requests.certs',
        'requests.cookies',
        'requests.exceptions', 
        'requests.hooks',
        'requests.models',
        'requests.packages',
        'requests.structures',
        'requests.sessions',
        'requests.status_codes',
        'requests.utils',
        'urllib3',
        'urllib3.contrib',
        'urllib3.util',
        'certifi',
        'idna',
        'chardet',
        'charset_normalizer',
        'datetime',
        'math',
        'json',
        'sys',
        'os',
        'win32event',
        'win32api',
        'winerror',
        'PyQt5',
        'PyQt5.QtWidgets',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
    ],
    hookspath=['.'],  # Include directorul curent pentru hook-h3.py
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MoonHunter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Lăsăm True pentru a vedea erorile
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['moon_icon.ico'],
)