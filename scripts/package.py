"""Build dist/geodetic_control_browser-<version>.zip for 'Install from ZIP'."""
import configparser
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
plugin = root / "geodetic_control_browser"
meta = configparser.ConfigParser()
meta.read(plugin / "metadata.txt")
version = meta["general"]["version"]
out = root / "dist" / f"geodetic_control_browser-{version}.zip"
out.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for f in plugin.rglob("*"):
        if f.is_file() and "__pycache__" not in f.parts:
            z.write(f, f.relative_to(root))
print(out)
