"""
出口装箱单 PDF 解析 → materials[]（可跑装箱/拼柜）。

说明：正式装箱单常无单件 L×W×H，本模块按品名+单重+包装类型做工程估算尺寸。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def extract_pdf_text(path: str | Path) -> str:
    import fitz

    doc = fitz.open(str(path))
    return "\n".join(page.get_text() for page in doc)


def _estimate_dims(name: str, unit_kg: float, package: str) -> Tuple[float, float, float]:
    n = (name + " " + package).lower()
    if "卷" in package or ("卷材" in name) or ("gasket" in n and "setting" in n and "block" not in name):
        return 600.0, 600.0, 400.0
    if any(k in name for k in ("螺钉", "螺栓", "锁", "执手", "滑撑", "连接件", "垫块", "垫片", "扣", "角片", "调节")):
        if unit_kg < 0.05:
            return 150.0, 100.0, 50.0
        if unit_kg < 1:
            return 350.0, 250.0, 150.0
        return 600.0, 400.0, 300.0
    if "预埋" in name or "铁框" in package:
        if unit_kg >= 20:
            return 1000.0, 400.0, 300.0
        if unit_kg >= 8:
            return 700.0, 350.0, 250.0
        return 500.0, 300.0, 200.0
    if "支架" in name or "bracket" in n:
        return 2500.0, 800.0, 600.0
    if any(k in name for k in ("钢通", "铁通", "钢构", "支撑钢", "structural steel", "空心铁")):
        if unit_kg >= 80:
            return 5800.0, 200.0, 200.0
        if unit_kg >= 40:
            return 4200.0, 180.0, 180.0
        if unit_kg >= 15:
            return 3000.0, 150.0, 150.0
        return 2000.0, 120.0, 120.0
    if any(k in name for k in ("幕墙板", "玻璃墙", "百叶", "curtain wall", "louver")):
        if unit_kg >= 80:
            return 2800.0, 1400.0, 250.0
        if unit_kg >= 30:
            return 2200.0, 1100.0, 200.0
        return 1500.0, 900.0, 150.0
    if any(k in name for k in ("异型材", "铝条", "extrusion", "折件")):
        if unit_kg >= 15:
            return 5800.0, 120.0, 80.0
        if unit_kg >= 3:
            return 4000.0, 80.0, 60.0
        return 2000.0, 50.0, 40.0
    if "铁架" in package:
        return (4000.0, 1100.0, 900.0) if unit_kg >= 40 else (2500.0, 1100.0, 700.0)
    if "木箱" in package:
        return (2200.0, 1100.0, 1000.0) if unit_kg >= 30 else (1600.0, 1000.0, 800.0)
    if unit_kg >= 100:
        return 3500.0, 500.0, 400.0
    if unit_kg >= 10:
        return 1500.0, 400.0, 300.0
    return 800.0, 400.0, 300.0


def _category(L: float, unit_kg: float) -> str:
    if L >= 4000:
        return "超长件"
    if unit_kg >= 200:
        return "重件"
    return "普通件"


def _is_ctn(s: str) -> bool:
    s = s.replace(" ", "")
    return bool(re.match(r"^[A-Z]{4}\d{6,7}$", s))


def _parse_weight(s: str) -> Optional[float]:
    s = s.replace(",", "").strip()
    if re.match(r"^\d+\.\d+$", s):
        return float(s)
    if re.match(r"^\d+$", s) and len(s) >= 3:
        # 整数千克也可能
        return float(s)
    return None


def _parse_qty(s: str) -> Optional[Tuple[int, str]]:
    m = re.match(r"^(\d+)\s*(件|卷|米|扎)?$", s.strip())
    if not m:
        return None
    return int(m.group(1)), (m.group(2) or "件")


def parse_packing_list_text(text: str, source_file: str = "") -> Dict[str, Any]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    contract = ""
    for ln in lines:
        m = re.search(r"(FEZH[-A-Z0-9/()]+)", ln)
        if m and "FEZH" in m.group(1):
            contract = m.group(1)

    package_note = next((ln for ln in lines if ln.startswith("注：") or ("包装" in ln and "注" in ln)), "")
    default_pkg = "包装"
    if "铁架" in package_note:
        default_pkg = "铁架"
    elif "铁框" in package_note:
        default_pkg = "铁框"
    elif "木箱" in package_note:
        default_pkg = "木箱"
    elif "纸箱" in package_note:
        default_pkg = "纸箱"
    elif "裸装" in package_note:
        default_pkg = "裸装"

    # 仅处理装箱单段落（可能多段）
    segments: List[List[str]] = []
    cur: List[str] = []
    in_pl = False
    def _is_pl_header(ln: str) -> bool:
        s = ln.replace(" ", "")
        return "PACKINGLIST" in s.replace(" ", "") or s == "装箱单" or "PACKING LIST" in ln

    def _is_pl_end(ln: str) -> bool:
        s = ln.replace(" ", "")
        # 勿把「合同编号」当结束
        if s in ("合同", "CONTRACT", "发票", "INVOICE"):
            return True
        if ln == "CONTRACT" or "INVOICE" in ln:
            return True
        # 「合    同」标题
        if re.fullmatch(r"合\s*同", ln):
            return True
        return False

    for ln in lines:
        if _is_pl_header(ln):
            if cur and in_pl:
                segments.append(cur)
            # 合并连续中英文标题
            if in_pl and cur and _is_pl_header(cur[0]):
                cur.append(ln)
            else:
                cur = [ln]
            in_pl = True
            continue
        if in_pl and _is_pl_end(ln):
            if cur:
                segments.append(cur)
            cur = []
            in_pl = False
            continue
        if in_pl:
            cur.append(ln)
    if cur:
        segments.append(cur)

    # 过滤过短无效段
    segments = [s for s in segments if len(s) >= 8]
    if not segments:
        # 退化：全文（仍可能抽到装箱信息）
        segments = [lines]

    materials: List[Dict[str, Any]] = []
    containers: List[str] = []
    mid = 0

    name_keys = (
        "铝", "钢", "铁", "幕墙", "垫", "螺", "胶", "通", "构", "板", "玻璃", "百叶",
        "预埋", "折", "锁", "撑", "件", "支架", "异型", "条", "槽", "Aluminium",
        "Aluminum", "Structural", "steel", "Gasket", "Bolt", "Screw", "EXTRUSION",
        "Setting", "Handle", "Friction", "Connector", "bracket", "Steel", "block",
        "Windproof", "Locking", "Lifting", "Corner", "Friction", "Adjustment",
        "bent", "ironmongery", "Self", "tapping", "T-", "EPDM",
    )

    for seg in segments:
        current_ctn = ""
        current_pkg = default_pkg
        i = 0
        while i < len(seg):
            ln = seg[i]
            if _is_ctn(ln):
                current_ctn = ln.replace(" ", "")
                if current_ctn not in containers:
                    containers.append(current_ctn)
                i += 1
                continue
            if ln in ("木箱", "铁架", "铁框", "纸箱", "扎", "卷", "裸装"):
                current_pkg = ln
                i += 1
                continue
            m_case = re.match(r"^(\d+)\s*(木箱|铁架|铁框|纸箱|扎)$", ln)
            if m_case:
                current_pkg = m_case.group(2)
                i += 1
                continue

            # 品名
            if len(ln) < 2 or not any(k in ln for k in name_keys):
                i += 1
                continue
            # 排除数量行被当成品名
            if re.match(r"^\d+\s*(件|卷|米|扎|箱)?$", ln):
                i += 1
                continue
            if any(
                x in ln
                for x in (
                    "货物名称", "Description", "Quantity", "Total", "总计",
                    "中国", "网址", "电话", "邮政", "客户", "合同编号", "集装箱",
                    "包装总箱", "总毛重", "总净重", "Cases", "GW.", "NW.",
                )
            ):
                i += 1
                continue

            name_parts = [ln]
            j = i + 1
            while j < len(seg):
                t = seg[j]
                if _is_ctn(t):
                    break
                if t in ("木箱", "铁架", "铁框", "纸箱", "扎", "卷"):
                    break
                if _parse_qty(t) or _parse_weight(t):
                    break
                if re.match(r"^\d+\s*(木箱|铁架|铁框|纸箱)", t):
                    break
                # 英文续行 / 规格
                if (
                    t.startswith("/")
                    or (re.match(r"^[A-Za-z(\-]", t) and "CNY" not in t and len(t) < 70)
                    or (len(t) < 40 and not any(k in t for k in name_keys) and re.search(r"[A-Za-z0-9]", t))
                ):
                    name_parts.append(t)
                    j += 1
                    continue
                break

            name = re.sub(r"\s+", " ", " ".join(name_parts)).strip()[:100]

            # 收集后续 token
            qty, unit, nw, gw = 0, "件", 0.0, 0.0
            qty_with_unit = 0
            k = j
            weight_vals: List[float] = []
            while k < min(j + 15, len(seg)):
                t = seg[k]
                if _is_ctn(t):
                    break
                if t in ("木箱", "铁架", "铁框", "纸箱", "扎", "卷"):
                    current_pkg = t
                    k += 1
                    continue
                m_case2 = re.match(r"^(\d+)\s*(木箱|铁架|铁框|纸箱|扎)$", t)
                if m_case2:
                    current_pkg = m_case2.group(2)
                    k += 1
                    continue
                # 下一项品名
                if (
                    k > j
                    and any(key in t for key in name_keys)
                    and not _parse_qty(t)
                    and not _parse_weight(t)
                    and not re.match(r"^\d+\s*(件|卷)", t)
                ):
                    if not t.startswith("/") and len(t) >= 4:
                        break
                pq = _parse_qty(t)
                if pq:
                    q, u = pq
                    # 优先带「件/卷」的数量
                    if u in ("件", "卷", "米", "扎"):
                        if q >= qty_with_unit:
                            qty_with_unit = q
                            qty, unit = q, u
                    elif qty_with_unit == 0 and q > qty and q not in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 18, 19):
                        # 裸数字：更像件数（排除小包装箱数 1-19）
                        qty, unit = q, u
                    elif qty_with_unit == 0 and q > qty:
                        # 小数字可能是箱数，仅在尚无件数时暂记
                        if qty == 0:
                            qty, unit = q, u
                    k += 1
                    continue
                pw = _parse_weight(t)
                if pw is not None and ("." in t or pw >= 100):
                    weight_vals.append(pw)
                    k += 1
                    continue
                k += 1

            if weight_vals:
                if len(weight_vals) >= 2:
                    if weight_vals[0] >= weight_vals[1]:
                        gw, nw = weight_vals[0], weight_vals[1]
                    else:
                        nw, gw = weight_vals[0], weight_vals[1]
                else:
                    nw = weight_vals[0]
                    gw = nw

            if qty_with_unit > 0:
                qty = qty_with_unit
            if qty <= 0 and nw > 0:
                qty = 1
            if qty > 0 and nw > 0:
                mid += 1
                unit_kg = nw / max(qty, 1)
                L, W, H = _estimate_dims(name, unit_kg, current_pkg)
                materials.append(
                    {
                        "id": f"M{mid:03d}",
                        "name": name,
                        "spec": name,
                        "length_mm": L,
                        "width_mm": W,
                        "height_mm": H,
                        "weight_kg": round(unit_kg, 4),
                        "quantity": qty,
                        "total_weight_kg": round(nw, 3),
                        "category": _category(L, unit_kg),
                        "package": current_pkg,
                        "container_no": current_ctn,
                        "gross_weight_kg": round(gw if gw else nw, 3),
                        "source_file": source_file,
                        "dims_estimated": True,
                        "unit": unit,
                    }
                )
            i = max(i + 1, j)
            continue

    # 去重：同名+同净重+同柜 只保留一条
    materials = _dedupe_materials(materials)
    # 重编号
    for idx, m in enumerate(materials, 1):
        m["id"] = f"M{idx:03d}"

    return {
        "source_file": source_file,
        "contract_no": contract,
        "package_note": package_note,
        "containers": containers,
        "materials": materials,
        "material_count": len(materials),
        "total_net_kg": round(sum(m["total_weight_kg"] for m in materials), 2),
        "total_pieces": sum(int(m["quantity"]) for m in materials),
    }


def _dedupe_materials(materials: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for m in materials:
        # 归一化名
        key_name = re.sub(r"\s+", "", m.get("name") or "")[:40]
        key = (key_name, round(float(m.get("total_weight_kg") or 0), 1), m.get("container_no") or "")
        if key in seen:
            continue
        # 跳过纯数量伪品名
        if re.match(r"^\d+件", key_name):
            continue
        seen.add(key)
        out.append(m)
    return out


def parse_packing_list_pdf(path: str | Path) -> Dict[str, Any]:
    path = Path(path)
    text = extract_pdf_text(path)
    return parse_packing_list_text(text, source_file=path.name)


def parse_all_in_dir(dir_path: str | Path) -> List[Dict[str, Any]]:
    dir_path = Path(dir_path)
    seen = set()
    out: List[Dict[str, Any]] = []
    for p in sorted(dir_path.glob("*.pdf")):
        key = re.sub(r"\(\d+\)", "", p.stem)
        if key in seen:
            continue
        seen.add(key)
        try:
            out.append(parse_packing_list_pdf(p))
        except Exception as e:
            out.append(
                {
                    "source_file": p.name,
                    "error": str(e),
                    "materials": [],
                    "material_count": 0,
                    "containers": [],
                }
            )
    return out
