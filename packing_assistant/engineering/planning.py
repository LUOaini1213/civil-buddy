"""Deterministic, explicit-workday CPM and resource diagnostics.

Offsets are half-open working-day boundaries. Date fields show occupied days,
so a positive-duration task's end is its last working day; a milestone is a
point at the start of its date. Actual dates are records, not rescheduling
constraints. No resources, durations, calendars or task links are inferred.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
import heapq
import math
import re

from packing_assistant.runtime.cancel import check

MAX_TASKS = 250
MAX_RESOURCES = 32
MAX_DEPENDENCIES = 2500
MAX_ASSIGNMENTS = 500
MAX_DAYS = 3653
MIN_YEAR = 1900
MAX_YEAR = 2100
TASK_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
RELATIONS = frozenset({"FS", "SS", "FF", "SF"})


def _object(value, required, optional, label):
    if not isinstance(value, dict) or set(value) - required - optional or required - set(value):
        raise ValueError(f"{label}字段缺失或包含不支持的字段。")
    return value


def _integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{label}须为 {low}–{high} 的整数，不接受布尔值。")
    return value


def _identifier(value, label):
    if not isinstance(value, str) or not TASK_ID.fullmatch(value):
        raise ValueError(f"{label}须以英文字母开头，仅含字母、数字、下划线或连字符，最多 64 字符。")
    return value


def _name(value, label):
    if (not isinstance(value, str) or not value.strip() or len(value) > 100
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise ValueError(f"{label}须为 1–100 个字符，不得含控制字符。")
    return value.strip()


def _date(value, label):
    if not isinstance(value, str) or not DATE.fullmatch(value):
        raise ValueError(f"{label}须使用 YYYY-MM-DD 日期。")
    try:
        result = date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{label}不是有效日期。") from None
    if not MIN_YEAR <= result.year <= MAX_YEAR:
        raise ValueError(f"{label}年份须在 {MIN_YEAR}–{MAX_YEAR} 之间。")
    return result


def _calendar(plan):
    """Include the tenth anniversary, within the shared supported date range."""
    start = date.fromisoformat(plan["start_date"])
    try:
        limit = start.replace(year=start.year + 10)
    except ValueError:  # February 29 -> February 28 ten years later.
        limit = start.replace(year=start.year + 10, day=28)
    limit = min(limit, date(MAX_YEAR, 12, 31))
    weekdays = set(plan["calendar"]["weekdays"])
    holidays = set(plan["calendar"]["holidays"])
    dates, current = [], start
    while current <= limit:
        if len(dates) % 64 == 0:
            check()
        if current.weekday() in weekdays and current.isoformat() not in holidays:
            dates.append(current.isoformat())
        current += timedelta(days=1)
    if not dates:
        raise ValueError("明确的工作日历在未来 10 年及 1900–2100 日期范围内没有可用工作日。")
    return dates


def _structure(plan):
    tasks = {row["id"]: row for row in plan["tasks"]}
    children = defaultdict(list)
    for row in plan["tasks"]:
        if row["parent_id"] is not None:
            if row["parent_id"] not in tasks:
                raise ValueError(f"{row['id']}：未知 WBS 父任务 {row['parent_id']}。")
            children[row["parent_id"]].append(row["id"])
    for ident in tasks:
        seen, cursor = set(), ident
        while cursor is not None:
            if cursor in seen:
                raise ValueError(f"WBS 父子关系存在循环：{ident}。")
            seen.add(cursor)
            if len(seen) > 40:
                raise ValueError("WBS 层级最多 40 层。")
            cursor = tasks[cursor]["parent_id"]
    summaries = set(children)
    for ident in summaries:
        row = tasks[ident]
        if (row["duration"] != 0 or row["dependencies"] or row["resources"]
                or row["progress"] != 0 or row["actual_start"] is not None or row["actual_finish"] is not None):
            raise ValueError(f"{ident}：WBS 汇总任务只作容器，duration/progress 须为 0，依赖、资源及实际日期须为空；结果由子任务派生。")
    leaves = {ident: row for ident, row in tasks.items() if ident not in summaries}
    successors = defaultdict(list)
    indegree = {ident: 0 for ident in leaves}
    for ident, row in leaves.items():
        seen_predecessors = set()
        for dep in row["dependencies"]:
            pred = dep["task_id"]
            if pred not in tasks:
                raise ValueError(f"{ident}：未知前置任务 {pred}。")
            if pred in summaries:
                raise ValueError(f"{ident}：暂不支持引用 WBS 汇总任务 {pred} 的依赖，请明确具体叶子任务。")
            if pred == ident:
                raise ValueError(f"{ident}：任务不能依赖自身。")
            if pred not in seen_predecessors:
                successors[pred].append(ident)
                indegree[ident] += 1
                seen_predecessors.add(pred)
    ready = [ident for ident, count in indegree.items() if count == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        check()
        ident = heapq.heappop(ready)
        order.append(ident)
        for successor in successors[ident]:
            indegree[successor] -= 1
            if indegree[successor] == 0:
                heapq.heappush(ready, successor)
    if len(order) != len(leaves):
        cyclic = sorted(ident for ident, count in indegree.items() if count)
        raise ValueError("依赖存在循环，涉及任务：" + ", ".join(cyclic))
    return tasks, children, leaves, order


def _weight(predecessor, successor, dependency):
    # Each relationship is exactly S_successor >= S_predecessor + weight.
    return dependency["lag"] + (predecessor["duration"] if dependency["type"][0] == "F" else 0) - (successor["duration"] if dependency["type"][1] == "F" else 0)


def _offsets(leaves, order, calendar_length=None):
    early, outgoing = {}, defaultdict(list)
    for ident in order:
        check()
        row = leaves[ident]
        start = 0
        for dep in row["dependencies"]:
            predecessor = dep["task_id"]
            weight = _weight(leaves[predecessor], row, dep)
            start = max(start, early[predecessor] + weight)
            outgoing[predecessor].append((ident, weight))
        early[ident] = start
        if start + row["duration"] > MAX_DAYS:
            raise ValueError("计划工期超过 10 年边界，请拆分计划或核对依赖时距。")
    duration = max(early[ident] + row["duration"] for ident, row in leaves.items())
    late = {}
    for ident in reversed(order):
        check()
        task_duration = leaves[ident]["duration"]
        limits = [duration - task_duration, *(late[successor] - weight for successor, weight in outgoing[ident])]
        if calendar_length is not None:
            # A positive task may finish at the boundary after the final day;
            # a milestone still needs its own supported date at that boundary.
            limits.append(calendar_length - max(1, task_duration))
        late[ident] = min(limits)
    return early, late, duration


def _check_calendar_bounds(dates, leaves, early, late):
    for ident, row in leaves.items():
        if (late[ident] < early[ident]
                or any(offset < 0 or offset >= len(dates) or offset + row["duration"] > len(dates) for offset in (early[ident], late[ident]))):
            raise ValueError("按当前工作日历排程超过 10 年或 1900–2100 日期范围，请拆分计划或核对工期。")


def validate_plan(plan):
    """Return a normalized copy, rejecting unknown fields and implicit durations."""
    check()
    _object(plan, {"start_date", "calendar", "tasks", "resources"}, set(), "计划")
    start = _date(plan["start_date"], "计划起点")
    _object(plan["calendar"], {"weekdays", "holidays"}, set(), "工作日历")
    weekdays, holidays = plan["calendar"]["weekdays"], plan["calendar"]["holidays"]
    if (not isinstance(weekdays, list) or not 1 <= len(weekdays) <= 7
            or any(type(day) is not int or not 0 <= day <= 6 for day in weekdays)
            or len(set(weekdays)) != len(weekdays)):
        raise ValueError("weekdays 须为不重复的 0–6 整数列表，0 为周一，至少一个工作日。")
    if not isinstance(holidays, list) or len(holidays) > MAX_DAYS:
        raise ValueError("holidays 须为最多 3653 个明确日期的列表。")
    holiday_dates = [_date(value, "假日").isoformat() for value in holidays]
    if len(set(holiday_dates)) != len(holiday_dates):
        raise ValueError("假日日期重复。")
    if not isinstance(plan["resources"], list) or len(plan["resources"]) > MAX_RESOURCES:
        raise ValueError(f"资源最多 {MAX_RESOURCES} 项。")
    resources, resource_ids = [], set()
    for row in plan["resources"]:
        _object(row, {"id", "name", "capacity"}, set(), "资源")
        ident = _identifier(row["id"], "资源编号")
        if ident in resource_ids:
            raise ValueError(f"资源编号重复：{ident}。")
        resource_ids.add(ident)
        resources.append({"id": ident, "name": _name(row["name"], "资源名称"), "capacity": _integer(row["capacity"], 1, 10000, "资源容量")})
    if not isinstance(plan["tasks"], list) or not 1 <= len(plan["tasks"]) <= MAX_TASKS:
        raise ValueError(f"任务须为 1–{MAX_TASKS} 项的列表。")
    tasks, task_ids, total_dependencies, total_assignments = [], set(), 0, 0
    for row in plan["tasks"]:
        check()
        _object(row, {"id", "name", "duration"}, {"progress", "parent_id", "dependencies", "resources", "actual_start", "actual_finish"}, "任务")
        ident = _identifier(row["id"], "任务编号")
        if ident in task_ids:
            raise ValueError(f"任务编号重复：{ident}。")
        task_ids.add(ident)
        duration = _integer(row["duration"], 0, MAX_DAYS, f"{ident} 工期")
        progress = row.get("progress", 0)
        if type(progress) not in (int, float) or not 0 <= progress <= 100 or not math.isfinite(progress):
            raise ValueError(f"{ident}：progress 须为 0–100 的有限数值。")
        parent = row.get("parent_id")
        if parent is not None:
            _identifier(parent, f"{ident} 父任务编号")
        actual = {key: None if row.get(key) is None else _date(row[key], f"{ident} {key}").isoformat() for key in ("actual_start", "actual_finish")}
        if actual["actual_start"] and actual["actual_finish"] and actual["actual_finish"] < actual["actual_start"]:
            raise ValueError(f"{ident}：实际完成早于实际开始。")
        dependencies = row.get("dependencies", [])
        if not isinstance(dependencies, list) or len(dependencies) > MAX_TASKS * 4:
            raise ValueError(f"{ident}：依赖须为有界列表。")
        deps, seen = [], set()
        for dep in dependencies:
            _object(dep, {"task_id", "type", "lag"}, set(), "依赖")
            pred = _identifier(dep["task_id"], "前置任务编号")
            relation = dep["type"]
            if not isinstance(relation, str) or relation not in RELATIONS:
                raise ValueError("依赖类型只支持 FS、SS、FF、SF。")
            lag = _integer(dep["lag"], -MAX_DAYS, MAX_DAYS, "依赖时距")
            if (pred, relation) in seen:
                raise ValueError(f"{ident}：同一前置任务的 {relation} 关系重复。")
            seen.add((pred, relation))
            deps.append({"task_id": pred, "type": relation, "lag": lag})
        assignments = row.get("resources", {})
        if not isinstance(assignments, dict) or len(assignments) > MAX_RESOURCES:
            raise ValueError(f"{ident}：资源需求须为已知资源编号到整数需求量的对象。")
        assigned = {}
        for resource_id, demand in assignments.items():
            if resource_id not in resource_ids:
                raise ValueError(f"{ident}：未知资源 {resource_id}。")
            assigned[resource_id] = _integer(demand, 1, 10000, f"{ident} 资源需求")
        if duration == 0 and assigned:
            raise ValueError(f"{ident}：零工期里程碑不占用时间区间，不能分配持续资源。")
        total_dependencies += len(deps)
        total_assignments += len(assigned)
        tasks.append({"id": ident, "name": _name(row["name"], "任务名称"), "duration": duration,
                      "progress": progress, "parent_id": parent, "dependencies": deps, "resources": assigned, **actual})
    if total_dependencies > MAX_DEPENDENCIES or total_assignments > MAX_ASSIGNMENTS:
        raise ValueError(f"计划最多 {MAX_DEPENDENCIES} 条依赖、{MAX_ASSIGNMENTS} 项任务资源分配。")
    clean = {"start_date": start.isoformat(), "calendar": {"weekdays": sorted(weekdays), "holidays": sorted(holiday_dates)}, "tasks": tasks, "resources": resources}
    _, _, leaves, order = _structure(clean)
    dates = _calendar(clean)
    early, late, _ = _offsets(leaves, order, len(dates))
    _check_calendar_bounds(dates, leaves, early, late)
    check()
    return clean


def _end(dates, start, duration):
    return dates[start + duration - 1] if duration else dates[start]


def _resource_report(plan, leaves, early, dates):
    conflicts, resources = [], []
    for resource in plan["resources"]:
        check()
        events = defaultdict(list)
        for ident, row in leaves.items():
            if resource["id"] in row["resources"]:
                demand = row["resources"][resource["id"]]
                events[early[ident]].append((ident, demand))
                events[early[ident] + row["duration"]].append((ident, -demand))
        points, active, peak = sorted(events), {}, 0
        for index, point in enumerate(points[:-1]):
            check()
            for ident, change in events[point]:
                if change > 0:
                    active[ident] = change
                else:
                    active.pop(ident, None)
            demand = sum(active.values())
            peak = max(peak, demand)
            if demand > resource["capacity"]:
                finish = points[index + 1]
                conflicts.append({"resource_id": resource["id"], "start_offset": point, "finish_offset": finish,
                                  "start": dates[point], "end": dates[finish - 1], "demand": demand,
                                  "capacity": resource["capacity"], "task_ids": sorted(active)})
        resources.append({**resource, "peak_demand": peak, "overallocated": peak > resource["capacity"]})
    return conflicts, resources


def calculate(plan):
    """Calculate all leaf-task floats plus derived WBS and resource conflicts."""
    clean = validate_plan(plan)
    tasks, children, leaves, order = _structure(clean)
    dates = _calendar(clean)
    early, late, duration = _offsets(leaves, order, len(dates))
    rows = {}
    for ident, row in leaves.items():
        check()
        start, finish, latest = early[ident], early[ident] + row["duration"], late[ident]
        rows[ident] = {**row, "is_summary": False, "milestone": row["duration"] == 0,
                       "start": dates[start], "end": _end(dates, start, row["duration"]),
                       "early_start": dates[start], "early_finish": _end(dates, start, row["duration"]),
                       "late_start": dates[latest], "late_finish": _end(dates, latest, row["duration"]),
                       "start_offset": start, "finish_offset": finish,
                       "early_start_offset": start, "early_finish_offset": finish,
                       "late_start_offset": latest, "late_finish_offset": latest + row["duration"],
                       "total_float": latest - start, "critical": latest == start}
    descendants = {}

    def summarize(ident):
        if ident in leaves:
            return [ident]
        if ident in descendants:
            return descendants[ident]
        check()
        ids = [leaf for child in children[ident] for leaf in summarize(child)]
        descendants[ident] = ids
        members = [rows[leaf] for leaf in ids]
        first = min(row["start_offset"] for row in members)
        last = max(row["finish_offset"] for row in members)
        total_duration = sum(row["duration"] for row in members)
        progress = sum(row["progress"] * row["duration"] for row in members) / total_duration if total_duration else sum(row["progress"] for row in members) / len(members)
        actual_starts = [row["actual_start"] for row in members if row["actual_start"]]
        actual_finishes = [row["actual_finish"] for row in members if row["actual_finish"]]
        rows[ident] = {**tasks[ident], "is_summary": True, "milestone": False, "descendant_ids": ids,
                       "duration": last - first, "progress": progress, "start_offset": first, "finish_offset": last,
                       "early_start_offset": first, "early_finish_offset": last,
                       "late_start_offset": min(row["late_start_offset"] for row in members),
                       "late_finish_offset": max(row["late_finish_offset"] for row in members),
                       "start": min(row["start"] for row in members), "end": max(row["end"] for row in members),
                       "early_start": min(row["early_start"] for row in members), "early_finish": max(row["early_finish"] for row in members),
                       "late_start": min(row["late_start"] for row in members), "late_finish": max(row["late_finish"] for row in members),
                       "total_float": None, "critical": any(row["critical"] for row in members),
                       "actual_start": min(actual_starts) if actual_starts else None,
                       "actual_finish": max(actual_finishes) if len(actual_finishes) == len(members) else None}
        return ids

    for ident in tasks:
        summarize(ident)
    conflicts, resource_rows = _resource_report(clean, leaves, early, dates)
    warnings = []
    if dates[0] != clean["start_date"]:
        warnings.append(f"计划起点不是工作日，首个可用工作日为 {dates[0]}；原始起点保留。")
    if any(row["actual_start"] or row["actual_finish"] for row in leaves.values()):
        warnings.append("实际开始/完成日期作为原始记录保留；本次 CPM 未使用实际记录锁定工序或重排剩余工期。")
    if conflicts:
        warnings.append("当前 CPM 计划存在资源超配；已列明冲突，尚未按资源容量重排。")
    if any(row["actual_finish"] and row["progress"] < 100 for row in leaves.values()):
        warnings.append("部分任务已有实际完成日期，但 progress 未到 100；原始记录未自动更改，请核对。")
    check()
    return {"plan": clean, "result": {
        "kind": "cpm", "engine": {"name": "civil-buddy-cpm", "version": "1"},
        "tasks": [rows[row["id"]] for row in clean["tasks"]], "duration_workdays": duration,
        "start_date": dates[0], "finish_date": max(row["end"] for row in rows.values()),
        "critical_task_ids": [ident for ident in order if rows[ident]["critical"]],
        "topological_order": order, "resource_conflicts": conflicts, "resources": resource_rows,
        "resource_feasible": not conflicts, "resource_optimized": False, "warnings": warnings,
        "assumptions": ["所有工序使用明确的同一工作日历；工期与依赖时距均为整数工作日。",
                        "FS/SS/FF/SF 按工作日边界计算；允许负时距，但任务不早于工程起点。",
                        "offset 采用 [start_offset, finish_offset)；日期 end/early_finish/late_finish 为最后占用工作日，零工期里程碑为当日开始时点。",
                        "关键任务为总时差为零的叶子任务；汇总任务由子任务范围和工期加权进度派生，不独立计算时差。",
                        "CPM 只分析依赖工期，资源超配只作诊断；未求资源受限最短工期。",
                        "实际日期仅作记录，未进行完成工作量、剩余工期或赶工费用推断。"],
    }}
