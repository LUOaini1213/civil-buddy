"""OpenTelemetry 真导出（可选）。

环境变量:
  PACKING_OTEL=1
  OTEL_EXPORTER_OTLP_ENDPOINT   默认 http://127.0.0.1:4318/v1/traces
  OTEL_SERVICE_NAME             默认 packing-agent
  PACKING_OTEL_FILE=1           同时写 output/otel/spans.jsonl（无 collector 也能验收）
  PACKING_LANGFUSE=1            可选 langfuse（需密钥）
"""

from __future__ import annotations

import json
import os
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from packing_assistant.config import HARNESS_VERSION, TRACE_DIR

_INIT_LOCK = threading.Lock()
_INITIALIZED = False
_INIT_ERROR: Optional[str] = None
_FILE_LOCK = threading.Lock()


def otel_enabled() -> bool:
    return (os.getenv("PACKING_OTEL") or "").strip().lower() in ("1", "true", "yes")


def otel_file_enabled() -> bool:
    return (os.getenv("PACKING_OTEL_FILE") or "").strip().lower() in ("1", "true", "yes")


def langfuse_enabled() -> bool:
    return (os.getenv("PACKING_LANGFUSE") or "").strip().lower() in ("1", "true", "yes")


def otel_status() -> Dict[str, Any]:
    return {
        "enabled": otel_enabled(),
        "file_export": otel_file_enabled(),
        "initialized": _INITIALIZED,
        "error": _INIT_ERROR,
        "endpoint": os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        or "http://127.0.0.1:4318/v1/traces",
        "service_name": os.getenv("OTEL_SERVICE_NAME") or "packing-agent",
    }


def ensure_otel() -> bool:
    """初始化 TracerProvider + OTLP HTTP exporter；成功返回 True。"""
    global _INITIALIZED, _INIT_ERROR
    if not otel_enabled():
        return False
    if _INITIALIZED:
        return _INIT_ERROR is None
    with _INIT_LOCK:
        if _INITIALIZED:
            return _INIT_ERROR is None
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

            service = os.getenv("OTEL_SERVICE_NAME") or "packing-agent"
            resource = Resource.create(
                {
                    "service.name": service,
                    "service.version": HARNESS_VERSION,
                    "packing.harness": HARNESS_VERSION,
                }
            )
            provider = TracerProvider(resource=resource)

            # OTLP HTTP
            endpoint = (
                os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
                or "http://127.0.0.1:4318/v1/traces"
            )
            try:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter,
                )

                exporter = OTLPSpanExporter(endpoint=endpoint)
                provider.add_span_processor(BatchSpanProcessor(exporter))
            except Exception as e:
                _INIT_ERROR = f"otlp_exporter: {e}"

            # 文件导出：默认开启（无 collector 也能验收真 span）
            try:
                provider.add_span_processor(
                    SimpleSpanProcessor(_JsonlSpanExporter(_otel_file_path()))
                )
            except Exception as e:
                if not _INIT_ERROR:
                    _INIT_ERROR = f"file_exporter: {e}"

            trace.set_tracer_provider(provider)
            _INITIALIZED = True
            return True
        except Exception as e:
            _INIT_ERROR = str(e)
            _INITIALIZED = True
            return False


def _otel_file_path() -> Path:
    d = Path(TRACE_DIR).resolve().parent / "otel"
    d.mkdir(parents=True, exist_ok=True)
    return d / "spans.jsonl"


class _JsonlSpanExporter:
    """最小 SpanExporter：写 JSONL，便于无 Jaeger 时验收。"""

    def __init__(self, path: Path) -> None:
        self.path = path

    def export(self, spans) -> int:
        # 0 = SUCCESS in otel sdk
        lines = []
        for s in spans:
            try:
                ctx = s.get_span_context()
                rec = {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "name": s.name,
                    "trace_id": format(ctx.trace_id, "032x") if ctx else "",
                    "span_id": format(ctx.span_id, "016x") if ctx else "",
                    "start_ns": getattr(s, "start_time", None),
                    "end_ns": getattr(s, "end_time", None),
                    "attributes": dict(s.attributes or {}),
                    "status": str(getattr(getattr(s, "status", None), "status_code", "")),
                }
                lines.append(json.dumps(rec, ensure_ascii=False, default=str))
            except Exception:
                continue
        if lines:
            with _FILE_LOCK:
                with self.path.open("a", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")
        try:
            from opentelemetry.sdk.trace.export import SpanExportResult

            return SpanExportResult.SUCCESS
        except Exception:
            return 0

    def shutdown(self) -> None:
        return None


def _coerce_attr(v: Any) -> Any:
    if isinstance(v, (str, int, float, bool)):
        return v
    if v is None:
        return ""
    return str(v)


@contextmanager
def span(name: str, attributes: Optional[Dict[str, Any]] = None) -> Iterator[None]:
    attrs = dict(attributes or {})
    if "run_id" in attrs and "packing.run_id" not in attrs:
        attrs["packing.run_id"] = attrs["run_id"]
    if "node" in attrs and "packing.node" not in attrs:
        attrs["packing.node"] = attrs["node"]
    if "tool" in attrs and "packing.tool" not in attrs:
        attrs["packing.tool"] = attrs["tool"]

    if otel_enabled():
        ensure_otel()
        # 无 collector 时默认也写文件，保证「真导出」可验
        if not otel_file_enabled():
            os.environ.setdefault("PACKING_OTEL_FILE", "1")
            # re-init file processor only if first ensure already ran without file
        try:
            from opentelemetry import trace

            tracer = trace.get_tracer("packing-agent", HARNESS_VERSION)
            with tracer.start_as_current_span(name) as s:
                for k, v in attrs.items():
                    try:
                        s.set_attribute(str(k), _coerce_attr(v))
                    except Exception:
                        pass
                t0 = time.perf_counter()
                try:
                    yield
                except Exception as e:
                    try:
                        s.set_attribute("error", True)
                        s.set_attribute("error.message", str(e)[:500])
                    except Exception:
                        pass
                    raise
                finally:
                    try:
                        s.set_attribute("duration_ms", int((time.perf_counter() - t0) * 1000))
                    except Exception:
                        pass
            return
        except Exception:
            pass

    # file-only 轻量记录（OTEL SDK 不可用时）
    if otel_enabled() or otel_file_enabled():
        t0 = time.perf_counter()
        err = None
        try:
            yield
        except Exception as e:
            err = e
            raise
        finally:
            _write_fallback_span(name, attrs, t0, err)
        return
    yield


def _write_fallback_span(
    name: str, attrs: Dict[str, Any], t0: float, err: Optional[BaseException]
) -> None:
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "name": name,
        "duration_ms": int((time.perf_counter() - t0) * 1000),
        "attributes": {k: _coerce_attr(v) for k, v in attrs.items()},
        "error": str(err) if err else None,
        "exporter": "fallback_jsonl",
    }
    try:
        path = _otel_file_path()
        with _FILE_LOCK:
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def record_event(name: str, payload: Optional[Dict[str, Any]] = None) -> None:
    if not langfuse_enabled():
        return
    try:
        import langfuse  # type: ignore  # noqa: F401

        _ = (name, payload)
    except Exception:
        return


def force_flush() -> None:
    """测试结束时冲刷 batch processor。"""
    if not otel_enabled():
        return
    try:
        from opentelemetry import trace

        provider = trace.get_tracer_provider()
        if hasattr(provider, "force_flush"):
            provider.force_flush()
    except Exception:
        pass


def spans_file() -> Path:
    return _otel_file_path()


def _duration_ms(rec: Dict[str, Any]) -> Optional[int]:
    if rec.get("duration_ms") is not None:
        try:
            return int(rec["duration_ms"])
        except (TypeError, ValueError):
            pass
    attrs = rec.get("attributes") or {}
    if attrs.get("duration_ms") is not None:
        try:
            return int(attrs["duration_ms"])
        except (TypeError, ValueError):
            pass
    start = rec.get("start_ns")
    end = rec.get("end_ns")
    if start is not None and end is not None:
        try:
            return int((int(end) - int(start)) / 1_000_000)
        except (TypeError, ValueError):
            return None
    return None


def list_spans(limit: int = 400) -> List[Dict[str, Any]]:
    """Read exported JSONL spans. Not a fixture list."""
    path = _otel_file_path()
    if not path.is_file():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(rec, dict):
            continue
        attrs = rec.get("attributes") or {}
        if not isinstance(attrs, dict):
            attrs = {}
        run_id = (
            rec.get("run_id")
            or attrs.get("run_id")
            or attrs.get("packing.run_id")
            or ""
        )
        node = rec.get("node") or attrs.get("node") or attrs.get("packing.node") or ""
        tool = rec.get("tool") or attrs.get("tool") or attrs.get("packing.tool") or ""
        rows.append(
            {
                "name": rec.get("name") or "",
                "run_id": str(run_id) if run_id is not None else "",
                "node": str(node) if node else "",
                "tool": str(tool) if tool else "",
                "duration_ms": _duration_ms(rec),
                "ts": rec.get("ts") or "",
                "span_id": rec.get("span_id") or "",
                "trace_id": rec.get("trace_id") or "",
            }
        )
    if limit and len(rows) > limit:
        return rows[-int(limit) :]
    return rows


def dashboard_payload(limit: int = 400) -> Dict[str, Any]:
    spans = list_spans(limit=limit)
    return {
        "ok": True,
        "schema": "otel.dashboard.v1",
        "fixture": False,
        "source": str(_otel_file_path()),
        "n": len(spans),
        "spans": spans,
        "status": otel_status(),
    }
