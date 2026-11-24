# PyInstaller spec. Build with: pyinstaller WebsiteScrapper.spec
import os
from PyInstaller.utils.hooks import collect_all, collect_data_files

datas, binaries, hiddenimports = [], [], []
for pkg in ("openpyxl",):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h
datas += collect_data_files("certifi")  # CA bundle so HTTPS works in the frozen app

icon = "assets/icon.icns" if os.path.exists("assets/icon.icns") else None

a = Analysis(
    ["run_app.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["matplotlib", "scipy", "IPython", "pytest", "lxml"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="WebsiteScrapper",
    console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="WebsiteScrapper")
app = BUNDLE(
    coll,
    name="WebsiteScrapper.app",
    icon=icon,
    bundle_identifier="com.coderexo.WebsiteScrapper",
    info_plist={
        "CFBundleName": "Website Email Scraper",
        "CFBundleShortVersionString": "1.1.0",
        "NSHighResolutionCapable": True,
    },
)
