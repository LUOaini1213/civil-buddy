"""Portable complete planning records; bounded ZIP, no extraction or solver runs."""
from copy import deepcopy
from datetime import datetime, timezone
import base64
import hashlib
import io
import json
import math
import re
import stat
from uuid import uuid4
import zipfile
import zlib

from packing_assistant.runtime.cancel import check
from .planning_records import (SCHEMA, MAX_RECORD, MAX_SOURCE, MAX_SOURCE_FILES, SHA256,
                               _validate_result, bundle_status, decode_source_file, digest,
                               validate_source, validate_weekly)
from .schedule import MAX_HISTORY, PROJECT_ID, _name

BUNDLE_SCHEMA = "civil-buddy.planning-bundle.v1"
MAX_BUNDLE = 40 * 1024 * 1024
MAX_EXPANDED = 48 * 1024 * 1024
MAX_PROJECT = 16 * 1024 * 1024
MAX_MANIFEST = 64 * 1024
AUTH_FIELDS = frozenset({"signed", "confirmed", "confirmation", "approval", "approvals", "authorization",
                         "authorizations", "signoff", "confirm_ok", "export_authorized"})
SNAPSHOT_FIELDS = {"name", "plan", "result", "method", "weekly", "baseline", "revision", "updated_at", "synthetic", "import_source"}
RECORD_FIELDS = SNAPSHOT_FIELDS | {"schema", "id", "created_at", "history"}


def _json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")


def _loads(data):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("项目包 JSON 含重复字段。")
            value[key] = item
        return value
    def bad(_):
        raise ValueError("项目包不接受非有限数值。")
    try:
        return json.loads(data, object_pairs_hook=pairs, parse_constant=bad)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("项目包 JSON 损坏或嵌套过深。") from exc


def _timestamp(value):
    if not isinstance(value, str) or len(value) > 50 or datetime.fromisoformat(value).tzinfo is None:
        raise ValueError("项目包时间记录无效。")


def _messages(value):
    return isinstance(value, list) and len(value) <= 1000 and all(isinstance(s, str) and len(s) <= 4000 for s in value)


def _verify_result(plan, result, method):
    """Recheck numerical feasibility, never call OR-Tools or replace stored dates."""
    from .planning import calculate, _calendar, _end
    from .planning_exchange import _validate_resource_result
    _validate_result(plan, result)
    reference = calculate(plan)["result"]  # Deterministic CPM validation only.
    if method == "cpm":
        if digest(reference) != digest(result):
            raise ValueError("项目包 CPM 结果与计划不一致或引擎格式不支持。")
        return
    if method != "resource" or result.get("kind") != "resource":
        raise ValueError("项目包计算方式与结果不一致。")
    extra = {"solver_status", "proven_optimal", "lower_bound_workdays", "cpm_duration_workdays", "resource_load", "critical_basis"}
    if set(result) != set(reference) | extra:
        raise ValueError("项目包资源结果含未知或缺失字段。")
    _validate_resource_result(plan, result)
    dates, expected_rows = _calendar(plan), {}
    original = {r["id"]: r for r in reference["tasks"]}
    for row in result["tasks"]:
        check()
        old = original[row["id"]]
        expected = deepcopy(old)
        start, finish = row["start_offset"], row["finish_offset"]
        expected.update(cpm_start=old["start"], cpm_end=old["end"], cpm_critical=old["critical"],
                        cpm_total_float=old["total_float"], resource_delay_workdays=start - old["start_offset"])
        for key in ("early_start", "early_finish", "late_start", "late_finish"):
            expected["cpm_" + key], expected["cpm_" + key + "_offset"] = old[key], old[key + "_offset"]
            expected[key] = expected[key + "_offset"] = None
        expected.update(start_offset=start, finish_offset=finish, duration=finish-start,
                        start=dates[start], end=_end(dates, start, finish-start), critical=False, total_float=None)
        expected_rows[row["id"]] = expected
    for expected in expected_rows.values():
        if expected["is_summary"]:
            members = [expected_rows[ident] for ident in expected["descendant_ids"]]
            expected.update(start=min(r["start"] for r in members), end=max(r["end"] for r in members))
    expected_ordered = [expected_rows[r["id"]] for r in reference["tasks"]]
    # The first released resource records kept CPM offsets in their old
    # unprefixed columns. Accept that exact known layout without rewriting
    # historical values or re-solving the resource schedule.
    legacy_rows = deepcopy(expected_ordered)
    for row in legacy_rows:
        for key in ("early_start", "early_finish", "late_start", "late_finish"):
            row[key + "_offset"] = row.pop("cpm_" + key + "_offset")
            row.pop("cpm_" + key)
    if digest(result["tasks"]) not in (digest(expected_ordered), digest(legacy_rows)):
        raise ValueError("项目包资源结果任务参数或日期不一致。")
    leaves = [r for r in expected_rows.values() if not r["is_summary"]]
    duration = max(r["finish_offset"] for r in leaves)
    fixed = {"duration_workdays": duration, "finish_date": max(r["end"] for r in expected_rows.values()),
             "start_date": dates[0], "critical_task_ids": [], "topological_order": reference["topological_order"],
             "resource_conflicts": [], "resource_feasible": True, "resource_optimized": True,
             "cpm_duration_workdays": reference["duration_workdays"]}
    for key, value in fixed.items():
        if digest(result[key]) != digest(value):
            raise ValueError(f"项目包资源结果 {key} 不一致。")
    loads, summaries = [], []
    for resource in plan["resources"]:
        check()
        daily = {}
        for row in leaves:
            demand = row["resources"].get(resource["id"], 0)
            if demand:
                for offset in range(row["start_offset"], row["finish_offset"]):
                    if offset % 128 == 0:
                        check()
                    daily[offset] = daily.get(offset, 0) + demand
        peak = max(daily.values(), default=0)
        loads.append({**resource, "peak": peak, "days": [{"date": dates[d], "demand": v} for d, v in sorted(daily.items())]})
        summaries.append({**resource, "peak_demand": peak, "overallocated": False})
    if digest(result["resource_load"]) != digest(loads) or digest(result["resources"]) != digest(summaries):
        raise ValueError("项目包资源负荷记录不一致。")
    engine = result["engine"]
    if (not isinstance(engine, dict) or set(engine) != {"name", "version"} or engine["name"] != "OR-Tools CP-SAT"
            or not isinstance(engine["version"], str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,3}", engine["version"])):
        raise ValueError("项目包资源引擎记录无效。")
    bound = result["lower_bound_workdays"]
    if (result["solver_status"] not in ("OPTIMAL", "FEASIBLE") or type(result["proven_optimal"]) is not bool
            or result["proven_optimal"] != (result["solver_status"] == "OPTIMAL")
            or type(bound) not in (int, float) or not math.isfinite(bound)
            or not reference["duration_workdays"] <= bound <= duration
            or result["proven_optimal"] and bound != duration):
        raise ValueError("项目包资源求解状态记录无效。")
    if not _messages(result["warnings"]) or not _messages(result["assumptions"]) or not isinstance(result["critical_basis"], str) or len(result["critical_basis"]) > 1000:
        raise ValueError("项目包结果说明格式无效。")


def _reset_auth(container):
    for key in AUTH_FIELDS:
        container.pop(key, None)


def validate_record(record):
    from .planning import validate_plan
    if not isinstance(record, dict):
        raise ValueError("项目包记录必须是对象。")
    _reset_auth(record)
    if (set(record) - RECORD_FIELDS - {"bundle_origin"} or RECORD_FIELDS - set(record)
            or record["schema"] != SCHEMA or not isinstance(record["id"], str) or not PROJECT_ID.fullmatch(record["id"])
            or not isinstance(record["history"], list) or len(record["history"]) > MAX_HISTORY):
        raise ValueError("项目包记录格式、编号或历史数量无效。")
    _timestamp(record["created_at"])
    previous = 0
    for item in [*record["history"], record]:
        check()
        if not isinstance(item, dict):
            raise ValueError("项目包历史格式无效。")
        _reset_auth(item)
        if item is not record and set(item) != SNAPSHOT_FIELDS:
            raise ValueError("项目包历史含未知字段。")
        _name(item["name"])
        if type(item["revision"]) is not int or not previous < item["revision"] <= 1000000000:
            raise ValueError("项目包修订号必须严格递增。")
        previous = item["revision"]
        _timestamp(item["updated_at"])
        if type(item["synthetic"]) is not bool or item["method"] not in ("cpm", "resource"):
            raise ValueError("项目包来源或计算方式无效。")
        plan = validate_plan(item["plan"])
        if digest(plan) != digest(item["plan"]):
            raise ValueError("项目包计划须为完整规范输入，不能隐式补充参数。")
        validate_weekly(item["weekly"], plan)
        validate_source(item["import_source"])
        _verify_result(plan, item["result"], item["method"])
        baseline = item["baseline"]
        if baseline is not None:
            if not isinstance(baseline, dict):
                raise ValueError("项目包基线无效。")
            _reset_auth(baseline)
            if set(baseline) != {"created_at", "revision", "plan", "result"} or type(baseline["revision"]) is not int or not 0 < baseline["revision"] <= item["revision"]:
                raise ValueError("项目包基线修订无效。")
            _timestamp(baseline["created_at"])
            base_plan = validate_plan(baseline["plan"])
            if digest(base_plan) != digest(baseline["plan"]):
                raise ValueError("项目包基线计划不完整。")
            _verify_result(base_plan, baseline["result"], baseline["result"].get("kind"))
    if "bundle_origin" in record:
        origin = record["bundle_origin"]
        if (not isinstance(origin, dict) or set(origin) != {"project_id", "revision", "imported_at", "optimality_reverified"}
                or not isinstance(origin["project_id"], str) or not PROJECT_ID.fullmatch(origin["project_id"])
                or type(origin["revision"]) is not int or origin["revision"] < 1 or origin["optimality_reverified"] is not False):
            raise ValueError("项目包来源记录无效。")
        _timestamp(origin["imported_at"])
    return record


def export_bundle(store, ident, expected_revision):
    from demo.projects import _mutation
    # Hold the same revision lock through snapshot and validation.
    with _mutation(store._path()):
        record = store._read(ident)
        store._expected(record, expected_revision)
        files = record.pop("source_files", {})
        validate_record(record)
        status = bundle_status({**record, "source_files": files})
        portable = dict(record, checksum=digest(record))
        project = _json(portable)
        if len(project) > MAX_PROJECT:
            raise ValueError("项目历史记录超过 16 MiB 项目包上限。")
        members = {"project.json": project}
        for sha, blob in sorted(files.items()):
            check()
            members[f"sources/{sha}.bin"] = decode_source_file(sha, blob)
        if sum(map(len, members.values())) > MAX_EXPANDED - MAX_MANIFEST:
            raise ValueError("项目包展开尺寸超过 48 MiB。")
        manifest = {"schema": BUNDLE_SCHEMA, "created_at": datetime.now(timezone.utc).isoformat(),
                    "confirmation_required": True, "missing_sources": status["missing_sources"],
                    "members": {name: {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)} for name, data in members.items()}}
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", _json(manifest))
            for name, data in members.items():
                check()
                archive.writestr(name, data)
        payload = stream.getvalue()
        if len(payload) > MAX_BUNDLE:
            raise ValueError("项目包超过 40 MiB。")
        check()
        return payload


def _unpack(data):
    if not isinstance(data, bytes) or not data or len(data) > MAX_BUNDLE:
        raise ValueError("项目包须非空且不超过 40 MiB。")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        names = [item.filename for item in entries]
        if (not 2 <= len(entries) <= MAX_SOURCE_FILES + 2 or len(set(names)) != len(names)
                or "manifest.json" not in names or "project.json" not in names):
            raise ValueError("项目包成员缺失、重复或数量超过上限。")
        if any(name not in {"manifest.json", "project.json"} and not re.fullmatch(r"sources/[0-9a-f]{64}\.bin", name) for name in names):
            raise ValueError("项目包只能包含固定白名单文件，不能含路径穿越或未知成员。")
        if any(item.flag_bits & 1 or stat.S_ISLNK(item.external_attr >> 16) or item.is_dir()
               or item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) for item in entries):
            raise ValueError("项目包不接受链接、目录、加密或未知压缩格式。")
        if any(item.file_size > max(1, item.compress_size) * 1500 for item in entries):
            raise ValueError("项目包压缩比异常。")
        if sum(item.file_size for item in entries) > MAX_EXPANDED:
            raise ValueError("项目包展开尺寸超过 48 MiB。")
        contents, total = {}, 0
        for entry in entries:
            check()
            limit = MAX_MANIFEST if entry.filename == "manifest.json" else MAX_PROJECT if entry.filename == "project.json" else MAX_SOURCE
            if entry.file_size > limit:
                raise ValueError("项目包单个成员超过尺寸上限。")
            with archive.open(entry) as source:
                contents[entry.filename] = source.read(limit + 1)
            total += len(contents[entry.filename])
            if len(contents[entry.filename]) != entry.file_size or len(contents[entry.filename]) > limit or total > MAX_EXPANDED:
                raise ValueError("项目包实际展开尺寸与声明不符。")
        manifest = _loads(contents.pop("manifest.json"))
        if not isinstance(manifest, dict):
            raise ValueError("项目包清单无效。")
        _reset_auth(manifest)
        if (set(manifest) != {"schema", "created_at", "confirmation_required", "missing_sources", "members"}
                or manifest["schema"] != BUNDLE_SCHEMA or manifest["confirmation_required"] is not True
                or not isinstance(manifest["members"], dict) or set(manifest["members"]) != set(contents)):
            raise ValueError("项目包清单格式或文件列表不匹配。")
        _timestamp(manifest["created_at"])
        for name, raw in contents.items():
            meta = manifest["members"][name]
            if (not isinstance(meta, dict) or set(meta) != {"sha256", "size"} or type(meta["size"]) is not int
                    or meta["size"] != len(raw) or meta["sha256"] != hashlib.sha256(raw).hexdigest()):
                raise ValueError("项目包文件大小或 SHA-256 校验失败。")
        record = _loads(contents.pop("project.json"))
        if not isinstance(record, dict) or record.pop("checksum", None) != digest(record):
            raise ValueError("项目包记录 checksum 校验失败。")
        validate_record(record)
        files = {}
        for name, raw in contents.items():
            sha = name.removeprefix("sources/").removesuffix(".bin")
            if hashlib.sha256(raw).hexdigest() != sha or not raw:
                raise ValueError("项目包原文件内容与路径 SHA-256 不一致。")
            files[sha] = {"size": len(raw), "data": base64.b64encode(raw).decode("ascii")}
        record["source_files"] = files
        if digest(manifest["missing_sources"]) != digest(bundle_status(record)["missing_sources"]):
            raise ValueError("项目包原文件缺项清单不一致。")
        return record


def import_bundle(store, data):
    from demo.projects import _mutation
    store._writable()
    try:
        record = _unpack(data)
    except (zipfile.BadZipFile, zlib.error, NotImplementedError, KeyError, TypeError, UnicodeError, RecursionError, AttributeError, OverflowError, IndexError) as exc:
        raise ValueError("项目包损坏或格式不支持，未导入。") from exc
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    record["bundle_origin"] = {"project_id": record["id"], "revision": record["revision"],
                               "imported_at": now, "optimality_reverified": False}
    record.update(id=uuid4().hex, created_at=now, updated_at=now)
    check()
    with _mutation(store._path()):
        if len(list(store.root.glob("*.json"))) >= 100:
            raise ValueError("排程项目达到 100 个上限。")
        store._write(record)  # Atomic replacement + final cancel checkpoint.
    return store._public(record)
