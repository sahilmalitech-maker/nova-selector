# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata


app_name = "Nova Image Scout"
spec_dir = Path(globals().get("__file__", "nova_image_scout.windows.spec")).resolve().parent
generated_dir = spec_dir / "packaging" / "generated"
icon_path = generated_dir / "NovaImageScout.ico"
windows_tesseract_runtime = generated_dir / "windows-tesseract-runtime"
auth_config_path = generated_dir / "auth_config.local.json"

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

if windows_tesseract_runtime.exists():
    datas.append((str(windows_tesseract_runtime), "tesseract-runtime"))

if auth_config_path.exists():
    datas.append((str(auth_config_path), "nova_scout_app/auth"))


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
        "IPython",
        "jupyter_client",
        "jupyter_core",
        "matplotlib",
        "notebook",
        "pandas",
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
    icon=str(icon_path) if icon_path.exists() else None,
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
