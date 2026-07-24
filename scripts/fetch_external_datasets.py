#!/usr/bin/env python3
"""拉取公开 3D-BPP 样例到 data/external（无需 git 也能拿 D-Wave txt）。"""

from __future__ import annotations

import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "data" / "external"

FILES = {
    "sample_data_1.txt": "https://raw.githubusercontent.com/dwave-examples/3d-bin-packing/main/input/sample_data_1.txt",
    "sample_data_2.txt": "https://raw.githubusercontent.com/dwave-examples/3d-bin-packing/main/input/sample_data_2.txt",
}


def main() -> int:
    EXT.mkdir(parents=True, exist_ok=True)
    for name, url in FILES.items():
        p = EXT / name
        try:
            urllib.request.urlretrieve(url, p)
            print(f"OK {p} ({p.stat().st_size} bytes)")
        except Exception as e:
            print(f"FAIL {name}: {e}")
            return 1
    print(
        "可选再 clone（需 git/网络）:\n"
        "  git clone --depth 1 https://github.com/kcliu2/CLP-Datasets.git data/external/CLP-Datasets\n"
        "  git clone --depth 1 https://github.com/enzoruiz/3dbinpacking.git data/external/3dbinpacking"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
