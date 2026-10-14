# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('C:/Users/conta/AppData/Local/Programs/Python/Python311/tcl/tcl8.6', '_tcl_data'), ('C:/Users/conta/AppData/Local/Programs/Python/Python311/tcl/tk8.6', '_tk_data'), ('C:/Users/conta/AppData/Local/Programs/Python/Python311/Lib/tkinter', 'tkinter'), ('assets/cliplink.ico', 'assets')]
binaries = [('C:/Users/conta/AppData/Local/Programs/Python/Python311/DLLs/tcl86t.dll', '.'), ('C:/Users/conta/AppData/Local/Programs/Python/Python311/DLLs/tk86t.dll', '.'), ('D:/Plugins Desenvolvidos/Clip Link/ClipLink_Desktop_Beta_0.2.4/tools/ffmpeg.exe', 'tools'), ('D:/Plugins Desenvolvidos/Clip Link/ClipLink_Desktop_Beta_0.2.4/tools/node.exe', 'tools')]
hiddenimports = ['yt_dlp.jsinterp', 'tkinter', '_tkinter']
tmp_ret = collect_all('yt_dlp')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('yt_dlp_ejs')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('curl_cffi')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['desktop_app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=['D:/Plugins Desenvolvidos/Clip Link/ClipLink_Desktop_Beta_0.2.4/pyinstaller_hooks'],
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
    name='ClipLink',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='D:/Plugins Desenvolvidos/Clip Link/ClipLink_Desktop_Beta_0.2.4/build/ClipLink-version-info.txt',
    icon=['D:/Plugins Desenvolvidos/Clip Link/ClipLink_Desktop_Beta_0.2.4/assets/cliplink.ico'],
)
