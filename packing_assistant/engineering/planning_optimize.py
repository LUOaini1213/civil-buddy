"""Resource-constrained workday scheduling with OR-Tools CP-SAT.

Model follows Google's interval/cumulative scheduling formulation. Inputs remain
explicit Civil Buddy data, and the solver runs in the existing disposable worker.
"""
from __future__ import annotations

from copy import deepcopy
from importlib.metadata import version
import math

from packing_assistant.runtime.cancel import check


def optimize(plan, *, seconds=10):
    check()
    if type(seconds) not in (int, float) or not 0 < seconds <= 1e9 or not math.isfinite(seconds):
        raise ValueError("求解时限须为正有限秒数。")
    from ortools.sat.python import cp_model
    from .planning import MAX_DAYS, _calendar, _end, calculate
    computed = calculate(plan)
    plan, result = computed["plan"], deepcopy(computed["result"])
    parents = {t["parent_id"] for t in plan["tasks"] if t["parent_id"]}
    tasks = {t["id"]: t for t in plan["tasks"] if t["id"] not in parents}
    if not tasks:
        raise ValueError("请先添加具体工序。")
    dates = _calendar(plan)
    horizon = min(MAX_DAYS, len(dates))
    rows = {t["id"]: t for t in result["tasks"]}
    model = cp_model.CpModel()
    starts, finishes, intervals = {}, {}, {}
    for ident, task in tasks.items():
        check()
        duration = task["duration"]
        # Positive intervals can occupy the last supported working day. A
        # milestone is a point and therefore needs a date of its own.
        last_start = horizon - duration if duration else min(horizon, len(dates) - 1)
        if rows[ident]["start_offset"] > last_start:
            raise ValueError("资源排程超过 10 年或有效日期范围。")
        starts[ident] = model.new_int_var(rows[ident]["start_offset"], last_start, "s_" + ident)
        finishes[ident] = model.new_int_var(0, horizon, "f_" + ident)
        intervals[ident] = model.new_interval_var(starts[ident], task["duration"], finishes[ident], "i_" + ident)
    for ident, task in tasks.items():
        for dependency in task["dependencies"]:
            pred, kind, lag = dependency["task_id"], dependency["type"], dependency["lag"]
            left = finishes[pred] if kind[0] == "F" else starts[pred]
            right = finishes[ident] if kind[1] == "F" else starts[ident]
            model.add(right >= left + lag)
    for resource in plan["resources"]:
        members = [ident for ident, task in tasks.items() if task["duration"] and task["resources"].get(resource["id"], 0)]
        demands = [tasks[ident]["resources"][resource["id"]] for ident in members]
        if any(demand > resource["capacity"] for demand in demands):
            raise ValueError(f"资源 {resource['id']} 单项需求超过容量，无法排程。")
        if members:
            model.add_cumulative([intervals[ident] for ident in members], demands, resource["capacity"])
    makespan = model.new_int_var(0, horizon, "makespan")
    model.add_max_equality(makespan, list(finishes.values()))
    model.minimize(makespan)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = min(30, max(.01, float(seconds)))
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    check()
    status = solver.solve(model)
    check()
    if status == cp_model.INFEASIBLE:
        raise ValueError("在所给工序、资源和日期范围内无可行排程。")
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise ValueError("求解时限内未找到可行方案；不能据此判断项目不可行。")
    offsets = {ident: (solver.value(starts[ident]), solver.value(finishes[ident])) for ident in tasks}
    # Independent numeric verification before returning solver results.
    for ident, task in tasks.items():
        check()
        start, finish = offsets[ident]
        if (finish - start != task["duration"] or start < rows[ident]["start_offset"]
                or start >= len(dates) or finish > horizon):
            raise ValueError("排程结果工期校验失败。")
        for dep in task["dependencies"]:
            a = offsets[dep["task_id"]][1 if dep["type"][0] == "F" else 0]
            b = offsets[ident][1 if dep["type"][1] == "F" else 0]
            if b < a + dep["lag"]:
                raise ValueError("排程结果依赖校验失败。")
    load = []
    for resource in plan["resources"]:
        check()
        daily = {}
        for ident, task in tasks.items():
            demand = task["resources"].get(resource["id"], 0)
            if not demand:
                continue
            for offset in range(*offsets[ident]):
                if offset % 64 == 0:
                    check()
                daily[offset] = daily.get(offset, 0) + demand
        if any(value > resource["capacity"] for value in daily.values()):
            raise ValueError("排程结果资源容量校验失败。")
        load.append({"id": resource["id"], "name": resource["name"], "capacity": resource["capacity"],
                     "peak": max(daily.values(), default=0),
                     "days": [{"date": dates[day], "demand": demand} for day, demand in sorted(daily.items()) if demand]})
    children = {}
    for task in plan["tasks"]:
        if task["parent_id"]:
            children.setdefault(task["parent_id"], []).append(task["id"])

    def span(ident):
        if ident not in offsets:
            check()
            ranges = [span(child) for child in children[ident]]
            offsets[ident] = (min(r[0] for r in ranges), max(r[1] for r in ranges))
        return offsets[ident]

    for row in result["tasks"]:
        check()
        start, finish = span(row["id"])
        row.update(cpm_start=row["start"], cpm_end=row["end"],
                   cpm_critical=row["critical"], cpm_total_float=row["total_float"],
                   resource_delay_workdays=start - row["start_offset"])
        for name in ("early_start", "early_finish", "late_start", "late_finish"):
            row["cpm_" + name] = row[name]
            row["cpm_" + name + "_offset"] = row[name + "_offset"]
            row[name] = row[name + "_offset"] = None
        row.update(start_offset=start, finish_offset=finish, duration=finish-start, start=dates[start],
                   end=_end(dates, start, finish-start))
        # CPM float and criticality do not describe a resource-constrained schedule.
        row.update(critical=False, total_float=None)
    # A final zero-day milestone is displayed on the following boundary date,
    # so summary display dates must be derived from descendants, not finish-1.
    for row in result["tasks"]:
        if row["is_summary"]:
            members = [rows[ident] for ident in row["descendant_ids"]]
            row.update(start=min(member["start"] for member in members),
                       end=max(member["end"] for member in members))
    duration = solver.value(makespan)
    result.update(kind="resource", engine={"name": "OR-Tools CP-SAT", "version": version("ortools")},
                  solver_status=solver.status_name(status), proven_optimal=status == cp_model.OPTIMAL,
                  lower_bound_workdays=solver.best_objective_bound, cpm_duration_workdays=result["duration_workdays"],
                  duration_workdays=duration, finish_date=max(row["end"] for row in result["tasks"]),
                  critical_task_ids=[], resource_conflicts=[], resource_load=load, resource_feasible=True,
                  resource_optimized=True, resources=[{"id": r["id"], "name": r["name"], "capacity": r["capacity"],
                      "peak_demand": r["peak"], "overallocated": False} for r in load],
                  critical_basis="资源排程不计算 CPM 时差；cpm_* 保留未受资源约束的比较值。")
    result["warnings"] = [message for message in result["warnings"]
                          if not message.startswith("当前 CPM 计划存在资源超配") and "本次 CPM" not in message]
    result["warnings"] += ["资源方案使用统一工作日历、整工作日和不可中断工序；没有假设额外班组或延长班次。",
                          "实际日期仅作记录，未锁定已开工任务；该方案不是剩余工期预测。",
                          "已证明本次约束下最优。" if status == cp_model.OPTIMAL else "已找到可行方案，尚未证明最优。"]
    result["assumptions"] = [
        "所有工序使用明确的同一工作日历；工期与依赖时距均为整数工作日，工序不可中断。",
        "FS/SS/FF/SF 按工作日边界计算；允许负时距，但任务不早于工程起点。",
        "最小化所有叶子任务完成边界的最大值；资源只采用输入中的需求与容量，不增配、不编造班次。",
        "offset 采用 [start_offset, finish_offset)；正工期 end 为最后占用工作日，里程碑为其日期开始时点。",
        "WBS 汇总范围由子任务派生；汇总结束日期包含末尾里程碑，不独立计算时差。",
        "当前资源方案不计算 CPM 时差与关键任务；cpm_* 字段仅供与未受资源约束的原 CPM 比较。",
        "日期限定在工程起点后 10 年内且不晚于 2100-12-31；实际日期仅作记录，未锁定已开工任务。",
    ]
    check()
    return {"plan": plan, "result": result}
