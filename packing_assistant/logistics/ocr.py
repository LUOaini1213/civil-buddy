"""Optional local PP-StructureV3 adapter in an isolated Python process.

Official protocol: paddleocr.ai/latest/en/version3.x/pipeline_usage/PP-StructureV3.html
Models must be provisioned separately. Document inference never downloads models or
uses a remote OCR endpoint. Missing capabilities fail explicitly, not as empty cargo.
"""
from __future__ import annotations

from html.parser import HTMLParser
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

REPO = Path(__file__).resolve().parents[2]
MAX_OUTPUT = 10 * 1024 * 1024
MAX_PIXELS = 25_000_000
MAX_PAGES = 40


def _check():
    from packing_assistant.runtime.cancel import check
    check()


def capability() -> dict:
    configured = os.environ.get("CIVIL_LOGISTICS_OCR_PYTHON", "")
    executable = Path(configured) if configured else REPO / ".venv-logistics" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    environment_found = executable.is_file()
    manifest = Path(os.environ.get("CIVIL_LOGISTICS_OCR_READY_MANIFEST", "")) if os.environ.get("CIVIL_LOGISTICS_OCR_READY_MANIFEST") else REPO / "output/logistics-ocr-ready.json"
    ready = False
    reason = "模型未就绪或未完成本地预热验证。"
    if environment_found:
        try:
            if manifest.is_file() and manifest.stat().st_size <= 256000:
                value = json.loads(manifest.read_text(encoding="utf-8"))
                models = value.get("models", [])
                ready = value.get("schema") == "civil.logistics.ocr-ready.v1" and bool(value.get("paddleocr")) and bool(value.get("paddlepaddle")) and Path(value.get("python", "")).resolve() == executable.resolve() and isinstance(models, list) and 1 <= len(models) <= 512
                for model in models:
                    path = Path(model["path"])
                    stat = path.stat()
                    ready = ready and path.is_file() and stat.st_size == model["bytes"]
        except (OSError, ValueError, TypeError, KeyError):
            ready = False
    else:
        reason = "本地 OCR 环境未安装；请配置 CIVIL_LOGISTICS_OCR_PYTHON。"
    return {"available": bool(ready), "ready": bool(ready), "environment_found": environment_found,
            "engine": "PP-StructureV3", "local_only": True, "python": str(executable), "reason": "" if ready else reason}


def _kill(process):
    if process.poll() is None:
        if os.name == "nt":
            subprocess.run([str(Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/taskkill.exe"), "/PID", str(process.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
        else:
            import signal
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process.poll() is None:
            process.kill()
    process.wait(timeout=10)


def _worker_environment(pages):
    env = {key: value for key, value in os.environ.items()
           if not any(token in key.upper() for token in ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL"))
           and not key.upper().endswith("_PROXY")}
    env.update(PYTHONPATH=str(REPO), PYTHON_DOTENV_DISABLED="1", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
               PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK="True", CIVIL_OCR_PAGES=json.dumps(pages or []))
    return env


def extract_tables(data: bytes, suffix: str, *, pages: list[int] | None = None) -> dict:
    """Host API, patchable in offline tests. Returns tables with cell evidence."""
    _check()
    if suffix not in (".pdf", ".png", ".jpg", ".jpeg") or not isinstance(data, bytes) or not 0 < len(data) <= 20 * 1024 * 1024:
        raise ValueError("OCR 输入类型或大小无效")
    if suffix != ".pdf":
        from PIL import Image
        try:
            with Image.open(BytesIO(data)) as img:
                if img.width * img.height > MAX_PIXELS or getattr(img, "n_frames", 1) != 1:
                    raise ValueError("图片超过 2500 万像素或为多帧图片")
                img.verify()
        except (OSError, Image.DecompressionBombError) as exc:
            raise ValueError("图片损坏或像素超限") from exc
    if pages is not None and (len(pages) > MAX_PAGES or any(type(n) is not int or not 1 <= n <= MAX_PAGES for n in pages)):
        raise ValueError("OCR 页码超限")
    cap = capability()
    if not cap["available"]:
        raise ValueError(cap["reason"])
    with tempfile.TemporaryDirectory(prefix="civil-logistics-ocr-") as temp:
        folder = Path(temp)
        source, output, logs = folder / ("input" + suffix), folder / "result.json", folder / "worker.log"
        source.write_bytes(data)
        env = _worker_environment(pages)
        kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        started = time.monotonic()
        with logs.open("wb") as log:
            process = subprocess.Popen([cap["python"], str(Path(__file__).resolve()), "--worker", str(source), str(output)], cwd=REPO, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log, **kwargs)
            try:
                while process.poll() is None:
                    _check()
                    if time.monotonic() - started > 240:
                        raise ValueError("本地 OCR 超过 240 秒；请减少页数")
                    if logs.stat().st_size > 2 * 1024 * 1024 or (output.exists() and output.stat().st_size > MAX_OUTPUT):
                        raise ValueError("本地 OCR 输出超过限制")
                    time.sleep(.05)
                _check()
                if process.returncode != 0 or not output.is_file():
                    raise ValueError("本地 OCR 未完成；请确认 PaddleOCR 及模型已在本机预热，正常解析不下载模型。")
                if output.stat().st_size > MAX_OUTPUT:
                    raise ValueError("OCR 结果过大")
                result = json.loads(output.read_text(encoding="utf-8"))
                if result.get("error"):
                    raise ValueError(str(result["error"])[:300])
                if not isinstance(result.get("tables"), list):
                    raise ValueError("OCR 结果结构无效")
                _check()
                return result
            finally:
                _kill(process)


class _TableHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows, self.row, self.cell = [], None, None
        self.spans = []
        self.merged = False
        self.count = 0

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            values = dict(attrs)
            try:
                self.colspan = int(values.get("colspan", 1))
                rowspan = int(values.get("rowspan", 1))
            except ValueError as exc:
                raise ValueError("OCR 表格合并格无效") from exc
            if not 1 <= self.colspan <= 128 or not 1 <= rowspan <= 100:
                raise ValueError("OCR 表格合并范围过大")
            self.merged |= self.colspan > 1 or rowspan > 1
            self.cell = []
        elif tag == "br" and self.cell is not None:
            self.cell.append(" ")

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.count += 1
            if self.count > 200000:
                raise ValueError("OCR 表格单元格过多")
            self.row.append(("".join(self.cell).strip(), self.count - 1))
            self.row.extend(("", None) for _ in range(self.colspan - 1))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if len(self.rows) >= 10000 or len(self.row) > 128:
                raise ValueError("OCR 表格行列超限")
            self.rows.append(self.row)
            self.row = None


def _bbox(value):
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, (list, tuple)):
        return None
    if len(value) == 4 and all(isinstance(v, (int, float)) for v in value):
        return list(value)
    if len(value) == 8 and all(isinstance(v, (int, float)) for v in value):
        return [min(value[::2]), min(value[1::2]), max(value[::2]), max(value[1::2])]
    if value and all(isinstance(v, (list, tuple)) and len(v) == 2 for v in value):
        return [min(v[0] for v in value), min(v[1] for v in value), max(v[0] for v in value), max(v[1] for v in value)]
    return None


def tables_from_result(result: dict, *, page: int, pdf: bool = False) -> dict:
    """Normalize documented PP-StructureV3 JSON; usable with injected offline results."""
    tables, issues = [], []
    result = result.get("res", result)
    for table in result.get("table_res_list", []):
        html = table.get("pred_html", "")
        if not isinstance(html, str) or len(html) > 2 * 1024 * 1024:
            raise ValueError("OCR 表格 HTML 过大")
        parser = _TableHTML()
        parser.feed(html)
        # A merged row cannot safely be aligned using the flat cell boxes. Keep the
        # source report explicit instead of shifting values into the wrong fields.
        if parser.merged:
            issues.append({"severity": "error", "code": "ocr_merged_cells", "message": f"第 {page} 页 OCR 表格含合并单元格，首版不自动展开；请使用原生 Excel 或人工整理。"})
            continue
        boxes = table.get("cell_box_list", [])
        fallback = _bbox(table.get("bbox"))
        source = {"page": page, "coordinate_system": "pdf_raster_pixels" if pdf else "image_pixels"}
        if pdf:
            source["dpi"] = 150
        if fallback:
            source["bbox"] = fallback
        rows = []
        for ri, cells in enumerate(parser.rows, 1):
            row = []
            for ci, (raw, index) in enumerate(cells, 1):
                location = {**source, "row": ri, "column": ci}
                box = _bbox(boxes[index]) if index is not None and index < len(boxes) else fallback
                if box:
                    location["bbox"] = box
                row.append({"raw": raw, "source": location, "ocr": True})
            rows.append(row)
        tables.append({"rows": rows, "source": source})
    if not tables and not issues:
        issues.append({"severity": "error", "code": "ocr_no_tables", "message": f"第 {page} 页 OCR 没有返回表格；未将散落文字猜为物料行。"})
    return {"tables": tables, "issues": issues}


def _worker(source: Path, output: Path):
    # This restriction is confined to the disposable worker, never global in the web host.
    import socket
    def offline(*args, **kwargs):
        raise OSError("Civil Buddy document OCR is offline; provision models separately")
    socket.create_connection = offline
    socket.socket.connect = offline
    socket.socket.connect_ex = offline
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK="True")
    from paddleocr import PPStructureV3
    from PIL import Image
    import numpy as np
    options = dict(use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False,
                   use_formula_recognition=False, use_chart_recognition=False, device="cpu",
                   # Paddle 3.3.1 on Windows raises an unsupported PIR ArrayAttribute
                   # during layout inference with oneDNN enabled. Native CPU works.
                   enable_mkldnn=False, use_region_detection=False)
    config = os.environ.get("CIVIL_LOGISTICS_OCR_CONFIG", "")
    if config:
        path = Path(config)
        if not path.is_file() or path.stat().st_size > 64000:
            raise ValueError("OCR 本地模型配置无效")
        values = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(values, dict) or any(not k.endswith(("_model_dir", "_model_name")) for k in values):
            raise ValueError("OCR 配置仅允许本地模型目录和模型名称")
        for key, value in values.items():
            if not isinstance(value, str) or "://" in value or (key.endswith("_model_dir") and not Path(value).is_dir()):
                raise ValueError("OCR 模型路径必须在本机")
        options.update(values)
    pipeline = PPStructureV3(**options)
    tables, issues = [], []
    requested = json.loads(os.environ.get("CIVIL_OCR_PAGES", "[]"))
    pdf = source.suffix.lower() == ".pdf"

    def process(img, page):
        if img.width * img.height > MAX_PIXELS:
            raise ValueError("OCR 页面像素超过限制")
        # PP-Structure 3.7 enables this separate lazy model in predict(), despite
        # use_doc_orientation_classify=False above. Keep original-image geometry
        # and avoid an unexpected model download during an offline document run.
        for result in pipeline.predict(np.asarray(img.convert("RGB"))[:, :, ::-1], use_table_orientation_classify=False):
            payload = result.json
            if callable(payload):
                payload = payload()
            if isinstance(payload, str):
                payload = json.loads(payload)
            normalized = tables_from_result(payload, page=page, pdf=pdf)
            tables.extend(normalized["tables"])
            issues.extend(normalized["issues"])

    if pdf:
        import pypdfium2
        with pypdfium2.PdfDocument(source) as document:
            if len(document) > MAX_PAGES:
                raise ValueError("OCR PDF 超过 40 页")
            for number in (requested or list(range(1, len(document) + 1))):
                page = document[number - 1]
                if page.get_width() * page.get_height() * (150 / 72) ** 2 > MAX_PIXELS:
                    raise ValueError("OCR PDF 页面像素超过限制")
                bitmap = page.render(scale=150 / 72)
                try:
                    process(bitmap.to_pil(), number)
                finally:
                    bitmap.close()
                    page.close()
    else:
        with Image.open(source) as img:
            process(img, 1)
    payload = json.dumps({"tables": tables, "issues": issues}, ensure_ascii=False).encode("utf-8")
    if len(payload) > MAX_OUTPUT:
        raise ValueError("OCR 结果超过限制")
    output.write_bytes(payload)


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] != "--worker":
        raise SystemExit("usage: ocr.py --worker INPUT OUTPUT")
    try:
        _worker(Path(sys.argv[2]), Path(sys.argv[3]))
    except Exception:
        # Do not echo document text, model logs, local paths or parser tracebacks into HTTP.
        Path(sys.argv[3]).write_text(json.dumps({"error": "本地 OCR 失败；请核对模型缓存、依赖及表格版式。"}, ensure_ascii=False), encoding="utf-8")
        raise SystemExit(1)
