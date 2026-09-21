"""Reproduce the pinned, offline Three.js viewer assets from the npm registry."""
from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path
import tarfile
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.180.0"
URL = f"https://registry.npmjs.org/three/-/three-{VERSION}.tgz"
INTEGRITY = "o+qycAMZrh+TsE01GqWUxUIKR1AL0S8pq7zDkYOQw8GqfX8b8VoCKYUoHbhiX5j+7hr8XsuHDVU6+gkQJQKg9w=="
FILES = {
    "package/build/three.module.min.js": "three.module.js",
    "package/build/three.core.min.js": "three.core.js",
    "package/examples/jsm/controls/OrbitControls.js": "OrbitControls.js",
    "package/LICENSE": "LICENSE.txt",
}


def main() -> None:
    with urlopen(URL, timeout=60) as response:
        data = response.read(20 * 1024 * 1024)
    if base64.b64encode(hashlib.sha512(data).digest()).decode() != INTEGRITY:
        raise ValueError("Three.js archive integrity mismatch")
    target = ROOT / "demo/static/vendor/three"
    target.mkdir(parents=True, exist_ok=True)
    manifest = {"version": VERSION, "source": URL, "integrity": "sha512-" + INTEGRITY, "files": {}}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for source, name in FILES.items():
            member = archive.extractfile(source)
            if member is None:
                raise ValueError("Missing vendored asset: " + source)
            text = member.read().decode("utf-8")
            if name == "three.module.js":
                text = text.replace("./three.core.min.js", "./three.core.js")
            if name == "OrbitControls.js":
                text = text.replace("from 'three'", "from './three.module.js'")
            content = text.encode("utf-8")
            (target / name).write_bytes(content)
            manifest["files"][name] = hashlib.sha256(content).hexdigest()
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("Vendored Three.js", VERSION, "with pinned integrity and MIT license")


if __name__ == "__main__":
    main()
