"""Provision official OCR models locally; no user document is read or uploaded.

Run with .venv-logistics's Python after installing requirements-logistics-ocr.txt.
Normal workbench document inference runs offline and never performs this download.
"""
from __future__ import annotations

from datetime import datetime, timezone
from importlib.metadata import version
import json
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    import sys
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
    from paddleocr import PPStructureV3
    options = dict(use_doc_orientation_classify=False, use_doc_unwarping=False,
                   use_textline_orientation=False, use_formula_recognition=False,
                   use_chart_recognition=False, use_region_detection=False,
                   device="cpu", enable_mkldnn=False)
    config = os.environ.get("CIVIL_LOGISTICS_OCR_CONFIG", "")
    if config:
        values = json.loads(Path(config).read_text(encoding="utf-8"))
        if not isinstance(values, dict) or any(not k.endswith(("_model_dir", "_model_name")) for k in values):
            raise ValueError("OCR configuration only accepts local model directories and names")
        for key, value in values.items():
            if not isinstance(value, str) or "://" in value or (key.endswith("_model_dir") and not Path(value).is_dir()):
                raise ValueError("Model directories must exist locally")
        options.update(values)
    print("Preparing official PP-StructureV3 models. No document input is used.", flush=True)
    pipeline = PPStructureV3(**options)
    models = set()
    cache = Path.home() / ".paddlex" / "official_models"
    # The fixed pinned pipeline exposes the merged model configuration. Disabled
    # model entries are excluded unless they already have a complete local cache.
    def visit(value):
        if isinstance(value, dict):
            if value.get("model_name"):
                folder = Path(value["model_dir"]) if value.get("model_dir") else cache / value["model_name"]
                if folder.is_dir():
                    for path in folder.iterdir():
                        if path.is_file() and path.suffix in {".json", ".yml", ".yaml", ".pdiparams", ".pdmodel", ".pdparams", ".safetensors"}:
                            models.add(path.resolve())
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(pipeline._merged_paddlex_config)
    if not models or not any(path.suffix in {".pdiparams", ".pdparams", ".safetensors"} for path in models):
        raise RuntimeError("No local model weights were located; readiness was not published")
    payload = {"schema": "civil.logistics.ocr-ready.v1", "python": str(Path(sys.executable).resolve()),
               "created_at": datetime.now(timezone.utc).isoformat(), "paddleocr": version("paddleocr"),
               "paddlepaddle": version("paddlepaddle"),
               "models": [{"path": str(path), "bytes": path.stat().st_size} for path in sorted(models)]}
    target = ROOT / "output" / "logistics-ocr-ready.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=target.parent, prefix="ocr-ready-", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
        pipeline.close()
    print(f"OCR models prepared: {len(models)} local model files. Readiness: {target}", flush=True)


if __name__ == "__main__":
    main()
