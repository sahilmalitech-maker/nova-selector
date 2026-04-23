# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata


app_name = "Nova Image Scout"
spec_dir = Path(globals().get("__file__", "nova_image_scout.spec")).resolve().parent
generated_dir = spec_dir / "packaging" / "generated"
icon_path = generated_dir / "NovaImageScout.icns"
tesseract_runtime = generated_dir / "tesseract-runtime"

datas = []
binaries = []
hiddenimports = [
    "tensorflow",
    "tensorflow.keras",
    "tensorflow.keras.applications",
    "tensorflow.keras.applications.mobilenet_v2",
    "keras",
    "h5py",
]

for distribution_name in ("tensorflow", "keras", "numpy", "pytesseract", "Pillow"):
    try:
        datas += copy_metadata(distribution_name)
    except Exception as exc:
        print(f"Skipping metadata copy for {distribution_name}: {exc}")

if tesseract_runtime.exists():
    datas.append((str(tesseract_runtime), "tesseract-runtime"))


a = Analysis(
    ["nova_image_scout.py"],
    pathex=[str(spec_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pandas",
        "matplotlib",
        "IPython",
        "jupyter_client",
        "jupyter_core",
        "notebook",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=app_name,
)

app = BUNDLE(
    coll,
    name=f"{app_name}.app",
    icon=str(icon_path) if icon_path.exists() else None,
    bundle_identifier="com.nova.imagescout",
    info_plist={
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "CFBundleName": app_name,
        "CFBundleDisplayName": app_name,
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        "NSHumanReadableCopyright": "Copyright 2026 Nova Image Scout",
    },
)
