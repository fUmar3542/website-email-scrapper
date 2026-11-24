# PyInstaller spec. Build with: pyinstaller EmailTool.spec
import os
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []
for pkg in ("openpyxl",):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h

icon = "assets/icon.icns" if os.path.exists("assets/icon.icns") else None

a = Analysis(
    ["run_app.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["requests", "bs4", "lxml", "matplotlib", "scipy", "IPython", "pytest"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="EmailTool",
    console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="EmailTool")
app = BUNDLE(
    coll,
    name="EmailTool.app",
    icon=icon,
    bundle_identifier="com.coderexo.emailtool",
    info_plist={
        "CFBundleShortVersionString": "1.0.0",
        "NSHighResolutionCapable": True,
    },
)
