"""Host-bound CAD tools shared by deterministic and model turns.

The host selects the saved project and supplies this snapshot. Tool arguments
cannot supply a project, path, dimensions or geometry. Parameter changes are
parsed from the actual user message by the same finite command parser as /cad.
"""
from __future__ import annotations

from copy import deepcopy
import io
import json
from pathlib import Path
import re
from uuid import uuid4
import zipfile

CONFIRM = "我明白，将由持证人员签认"
READ_TOOLS = frozenset({"cad_inspect", "cad_suggest_layers"})
MUTATE_TOOLS = frozenset({"cad_build", "cad_modify", "cad_undo", "cad_export"})
TOOL_NAMES = READ_TOOLS | MUTATE_TOOLS


def operation(text: str, context: dict) -> str:
    """Classify only an explicit current request, never history or attachments."""
    clean = text.replace(CONFIRM, "").strip(" \t\r\n，。；,;!")
    if re.search(r"[?？]|(?:吗|如何|怎么|是否|不要|不必|先不|暂不|不需要|别(?:生成|修改|改|导出|建模|撤销|动))", clean):
        return "cad_inspect"
    if re.fullmatch(r"(?:请)?(?:检查|查看|分析)(?:一下)?(?:这份|当前|已保存的)?(?:CAD|图纸|模型|项目)(?:情况|状态)?", clean, re.I):
        return "cad_inspect"
    if re.fullmatch(r"(?:请)?(?:建议|推荐|识别|解释)(?:一下)?(?:图层|图层用途|图层映射)", clean):
        return "cad_suggest_layers"
    if re.fullmatch(r"(?:请)?(?:生成|重新生成|建模|重建)(?:三维|3D)?(?:模型)?", clean, re.I):
        return "cad_build"
    if re.fullmatch(r"(?:请)?(?:撤销|撤回)(?:上一次|上次|刚才的)?(?:修改|操作)?", clean):
        return "cad_undo"
    if re.fullmatch(r"(?:请)?导出(?:当前|这个)?(?:三维|3D)?(?:模型|GLB|参数|项目模型包)?", clean, re.I):
        return "cad_export"
    from .commands import apply_command
    try:
        apply_command(context["document"], context["draft_config"], clean)
        return "cad_modify"
    except (ValueError, KeyError, TypeError):
        return "cad_inspect"


def parameter_changes(before: dict, after: dict) -> list[dict]:
    changes = []
    def visit(old, new, path):
        if isinstance(old, dict) and isinstance(new, dict):
            for key in sorted(old.keys() | new.keys()):
                visit(old.get(key), new.get(key), (*path, key))
        elif old != new:
            changes.append({"parameter": ".".join(path), "before": old, "after": new})
    visit(before, after, ())
    return changes


def _limited_report(rows: list[dict]) -> list[dict]:
    # Keep actionable failures visible even after many successful source rows.
    failures = {"failed", "unsupported", "invalid"}
    return sorted(rows, key=lambda row: row.get("status") not in failures)[:80]


def _summary(context: dict) -> dict:
    doc, model = context["document"], context.get("model") or {}
    return {"project": context["project"]["name"], "filename": doc.get("filename"),
            "units": doc.get("units"), "config": context["draft_config"],
            "layers": doc.get("layers", []), "objects": len(model.get("objects", [])),
            "report": _limited_report(model.get("report") or [{k: e.get(k) for k in ("id", "layer", "status", "reason")}
                                                   for e in doc.get("entities", [])]),
            "url": "/cad?project_id=" + context["project"]["id"]}


def _export(context: dict, session_id: str, run_id: str, format: str) -> list[dict]:
    from .geometry import export_glb
    from packing_assistant.runtime import agent_loop, cancel
    from packing_assistant.runtime.workspace_ctx import current_worktree
    from packing_assistant.sandbox import assert_write, guarded_write_bytes
    model = context.get("model")
    if not model or not model.get("objects"):
        raise ValueError("尚无可导出模型，请先生成。")
    if context.get("draft_config") != model.get("config"):
        raise ValueError("草稿参数与模型不一致，请先成功生成后再导出。")
    record = {"schema": "civil-buddy.cad3d.parameters.v1", "purpose": "geometry-preview-not-certified-bim",
              **{k: v for k, v in model.items() if k != "objects"},
              "objects": [{k: v for k, v in obj.items() if k not in {"vertices", "faces"}} for obj in model["objects"]]}
    parameters = json.dumps(record, ensure_ascii=False, allow_nan=False, indent=2).encode("utf-8")
    if format == "json":
        data, name = parameters, "cad-parameters.json"
    else:
        glb = export_glb(model)
        if format == "glb":
            data, name = glb, "cad-model.glb"
        else:
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
                bundle.writestr("cad-model.glb", glb)
                bundle.writestr("cad-parameters.json", parameters)
            data, name = stream.getvalue(), "cad-model.zip"
    worktree = current_worktree()
    root = Path(worktree) / ".civil-buddy/out" if worktree else agent_loop._OUT
    target = assert_write(root / agent_loop._safe_sid(session_id) / "cad" / agent_loop._safe_sid(run_id) / name)
    temp = assert_write(target.with_name("." + uuid4().hex + ".tmp"))
    try:
        cancel.check()
        guarded_write_bytes(temp, data)
        cancel.check()
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)
    return [{"name": name, "path": str(target), "tool": "cad_export"}]


def execute(context: dict, name: str, args: dict, *, user_text: str, session_id: str,
            run_id: str, confirmed: bool = False) -> dict:
    """Return result and an updated snapshot; never mutate the caller on failure."""
    from packing_assistant.runtime import cancel
    from packing_assistant.runtime.civil_config import decide_gate, load_config
    cancel.check()
    if name not in TOOL_NAMES or not isinstance(args, dict):
        return {"ok": False, "error_code": "unknown_tool", "reason": "没有这个 CAD 操作。"}
    if args and (name != "cad_export" or set(args) - {"format"}):
        return {"ok": False, "error_code": "invalid_args", "reason": "CAD 工具不能接收项目、坐标、尺寸或用户确认。"}
    if name == "cad_export" and args.get("format", "zip") not in {"glb", "json", "zip"}:
        return {"ok": False, "error_code": "invalid_args", "reason": "只支持 GLB、JSON 或 ZIP 导出。"}
    allowed = operation(user_text, context)
    if name in MUTATE_TOOLS and name != allowed:
        return {"ok": False, "error_code": "read_only_intent", "reason": "本轮用户未请求这项 CAD 操作。"}
    if name in MUTATE_TOOLS and not load_config().allow_write():
        return {"ok": False, "error_code": "read_only", "reason": "当前为只读模式，不能修改或导出 CAD 项目。"}
    if name in MUTATE_TOOLS and decide_gate(intent="run", risk="high" if name == "cad_export" else "low",
                                            confirmed=confirmed, cfg=load_config()) == "hitl":
        return {"ok": False, "error_code": "approval_required", "reason": "当前策略要求本轮用户亲自输入确认句后执行。"}
    if name == "cad_inspect":
        return {"ok": True, "summary": "已检查选中的 CAD 项目；图纸、参数和逐项处理情况如下。", **_summary(context)}
    if name == "cad_suggest_layers":
        return {"ok": True, "summary": "以下仅为图层用途建议，请返回 CAD 页确认后再生成。",
                "suggestions": [{"layer": layer["name"], "suggested_role": layer.get("suggested_role", "ignore")}
                                for layer in context["document"].get("layers", [])]}
    if name == "cad_export":
        if not confirmed:
            return {"ok": False, "error_code": "approval_required", "reason": "模型导出需要本轮用户亲自输入签认确认句。"}
        requested_format = "glb" if re.search(r"GLB", user_text, re.I) else "json" if "参数" in user_text else "zip"
        files = _export(context, session_id, run_id, args.get("format", requested_format))
        return {"ok": True, "summary": "已导出模型文件。", "files": files}
    from .commands import apply_command
    from .geometry import build_model
    updated = deepcopy(context)
    before = deepcopy(context["draft_config"])
    if name == "cad_modify":
        clean = user_text.replace(CONFIRM, "").strip(" \t\r\n，。；,;!")
        updated["draft_config"] = apply_command(context["document"], before, clean)["config"]
    elif name == "cad_undo":
        if not context.get("undo_config"):
            return {"ok": False, "error_code": "no_history", "reason": "没有可撤销的已生成版本。"}
        updated["draft_config"] = deepcopy(context["undo_config"])
    model = build_model(updated["document"], updated["draft_config"])
    if not model.get("objects"):
        return {"ok": False, "error_code": "geometry_failed", "reason": "没有可生成的构件，保留上一个可用模型。",
                "report": _limited_report(model.get("report", []))}
    cancel.check()
    model["source"] = {k: updated["document"].get(k) for k in ("filename", "sha256", "units")}
    updated.update(model=model, draft_config=deepcopy(model["config"]), applied_config=deepcopy(model["config"]),
                   undo_config=deepcopy((context.get("model") or {}).get("config")))
    changes = parameter_changes(before, updated["draft_config"])
    count = len(model["objects"])
    failed = model.get("summary", {}).get("failed", 0)
    summary = f"已生成 {count} 个几何构件" + (f"；仍有 {failed} 个实体未处理，请查看报告。" if failed else "。")
    return {"ok": True, "summary": summary, "changes": changes, "report": _limited_report(model.get("report", [])),
            "cad_context": updated, "cad_changed": True}


def reply_for(results: list[dict], context: dict) -> str:
    """Outcome text is grounded in tool results, never a model's success claim."""
    if not results:
        return "本轮尚未执行 CAD 工具。可要求检查图纸、建议图层、生成模型、把墙高改成3.6米、撤销或导出模型。"
    lines = []
    for result in results:
        lines.append(str(result.get("summary") or result.get("reason") or "CAD 操作未完成。"))
        if "objects" in result:
            lines.append(f"图纸：{result.get('filename')}；已生成构件：{result['objects']}；"
                         f"已选单位：{result.get('config', {}).get('unit') or '待确认'}。")
        for row in result.get("changes", []):
            lines.append(f"- {row['parameter']}：{row['before']} → {row['after']}")
        for row in result.get("suggestions", []):
            lines.append(f"- {row['layer']}：{row['suggested_role']}（待确认）")
        for row in [r for r in result.get("report", []) if r.get("status") in {"failed", "unsupported", "invalid"}][:12]:
            lines.append(f"- 实体 {row.get('id')}（{row.get('layer')}）：{row.get('reason')}")
        if result.get("error_code") == "approval_required":
            lines.append("请在确认栏亲自输入：" + CONFIRM)
    lines.append("[打开 CAD 项目](/cad?project_id=" + context["project"]["id"] + ")")
    return "\n\n".join(lines)
