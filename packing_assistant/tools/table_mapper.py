"""通用材料表 → MaterialTableIR / materials[]。

任意 Excel/CSV/字典行：中英列名同义词 + 单位归一 → 标准 materials 字段。
行业无关；钢材仅为 profile 提示之一。
"""

from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

PathLike = Union[str, Path]

# 标准字段 → 同义词（小写匹配）
COLUMN_SYNONYMS: Dict[str, Tuple[str, ...]] = {
    "id": ("id", "编号", "行号", "line_id", "row_id", "line_no", "no", "序号"),
    "name": (
        "name",
        "名称",
        "品名",
        "货物名称",
        "货名",
        "item",
        "item description",
        "product",
        "description",
        "desc",
        "sku_name",
        "物料名称",
        "品名规格",
        "article",
        "article_name",
        "货品名称",
        "商品名称",
    ),
    "quantity": (
        "quantity",
        "数量",
        "件数",
        "箱数",
        "qty",
        "qty.",
        "q'ty",
        "count",
        "pcs",
        "pc",
        "件",
        "装箱数",
    ),
    "length_mm": (
        "length_mm",
        "length",
        "len",
        "l",
        "长",
        "长度",
        "外长",
        "length_cm",
        "length_m",
        "length(m)",
        "length (m)",
        "l_mm",
        "l_cm",
        "l_m",
        "长度_m",
        "长度_mm",
        "长(mm)",
        "长(m)",
        "长mm",
        "长m",
    ),
    "width_mm": (
        "width_mm",
        "width",
        "w",
        "宽",
        "宽度",
        "外宽",
        "width_cm",
        "width_m",
        "width(cm)",
        "width (cm)",
        "w_mm",
        "w_cm",
        "宽度_mm",
        "宽(mm)",
        "宽mm",
    ),
    "height_mm": (
        "height_mm",
        "height",
        "h",
        "高",
        "高度",
        "外高",
        "height_cm",
        "height_m",
        "height(mm)",
        "height (mm)",
        "h_mm",
        "h_cm",
        "高度_mm",
        "高(mm)",
        "高mm",
        "厚",
        "厚度",
    ),
    "weight_kg": (
        "weight_kg",
        "weight",
        "单重",
        "重量",
        "毛重",
        "净重",
        "gross_weight",
        "gross_kg",
        "net_weight",
        "net weight(kg)",
        "net weight (kg)",
        "kg",
        "unit_weight",
        "单重kg",
        "单重(kg)",
        "weight_t",
        "单重t",
        "吨",
    ),
    "total_weight_kg": (
        "total_weight_kg",
        "total_weight",
        "总重",
        "合计重量",
        "total_kg",
        "gross_total",
        "总重kg",
        "总重(kg)",
        "total_t",
    ),
    "part_no": (
        "part_no",
        "part",
        "件号",
        "料号",
        "图号",
        "sku",
        "sku code",
        "item_no",
        "item_code",
        "drawing_no",
        "物料编码",
    ),
    "category": ("category", "类别", "类型", "品类", "type", "class", "分类"),
    "spec": ("spec", "规格", "型号", "model", "规格型号"),
    "note": ("note", "备注", "说明", "remark", "comments", "comment"),
}

CATEGORY_ALIASES: Dict[str, str] = {
    "carton": "carton",
    "纸箱": "carton",
    "纸盒": "carton",
    "box": "carton",
    "crate": "crate",
    "木箱": "crate",
    "铁架": "crate",
    "铁笼": "crate",
    "long_item": "long_item",
    "超长件": "long_item",
    "长材": "long_item",
    "管材": "long_item",
    "型材": "long_item",
    "pallet": "pallet",
    "托盘": "pallet",
    "bulk_bag": "bulk_bag",
    "吨袋": "bulk_bag",
    "集装袋": "bulk_bag",
    "fragile": "fragile",
    "易碎": "fragile",
    "玻璃": "fragile",
    "liquid_unit": "liquid_unit",
    "液体": "liquid_unit",
    "generic": "generic",
    "普通件": "generic",
    "重件": "generic",
}


def _norm_header(h: Any) -> str:
    s = str(h or "").strip().lower()
    s = s.replace("（", "(").replace("）", ")")
    s = re.sub(r"\s+", "", s)
    return s


# 模糊匹配规则：(子串, 标准字段, 分数)，按顺序命中第一条。
# 分数用来解决一张表里多个表头抢同一个字段的情况——出口装箱单常同时有
# N.W. 与 G.W.，装柜看的是毛重，所以毛重必须赢，而不是看谁排在前面。
_FUZZY_RULES: Tuple[Tuple[str, str, int], ...] = (
    # 合并尺寸列要排在长/宽/高之前，否则「尺寸(长x宽x高)」会被当成长度列
    ("lxwxh", "__dims__", 95),
    ("l*w*h", "__dims__", 95),
    ("l/w/h", "__dims__", 95),
    ("l×w×h", "__dims__", 95),
    # 「长宽高(mm)」此前命中下面的「长」规则，整格 "1200*400*300" 被 _to_float 抹掉
    # 分隔符读成长度 1200400300 mm——不是缺数，是一个看起来像数的错数。
    ("长宽高", "__dims__", 95),
    ("长x宽x高", "__dims__", 95),
    ("长*宽*高", "__dims__", 95),
    ("长/宽/高", "__dims__", 95),
    ("长×宽×高", "__dims__", 95),
    ("dimension", "__dims__", 90),
    ("尺寸", "__dims__", 90),
    ("measurement", "__dims__", 88),
    ("size", "__dims__", 84),
    ("g.w", "weight_kg", 88),
    ("gross", "weight_kg", 86),
    ("毛重", "weight_kg", 86),
    ("n.w", "weight_kg", 82),
    ("net", "weight_kg", 80),
    ("净重", "weight_kg", 80),
    ("description", "name", 85),
    ("品名", "name", 85),
    ("goods", "name", 84),
    ("commodity", "name", 84),
    ("货物", "name", 84),
    ("名称", "name", 83),
    ("length", "length_mm", 80),
    ("width", "width_mm", 80),
    ("height", "height_mm", 80),
    ("weight", "weight_kg", 78),
    ("qty", "quantity", 80),
    ("数量", "quantity", 80),
    ("长", "length_mm", 75),
    ("宽", "width_mm", 75),
    ("高", "height_mm", 75),
)


# 出口装箱单最常见的尺寸表头其实是单字母加单位：「L (mm)」「W(cm)」「H/mm」「Len.」。
# 同义词表只收了裸的 l / w / h 和 l_mm 这类下划线写法，模糊规则又按子串匹配
# length / width / height，于是这几种写法一个都对不上——三列尺寸全丢，行以
# 0×0×0 进引擎。单字母不能放进子串规则（任何表头都含字母 l），所以用整词正则。
_SHORT_DIM_RE = re.compile(
    r"^(l|w|h|len|wid|ht|hgt)\.?"
    r"(?:[(\[/_\-]?(?:mm|cm|m|毫米|厘米|米)|[(\[/_\-](?:in|inch|inches|ft|feet|英寸|英尺)|[\"″”])?"
    r"[)\]]?\.?$"
)
# 「Meas. (CBM)」「体积(m3)」是体积列，「Unit of Measurement」是计量单位列，都不是长宽高。
_VOLUME_HEADER_RE = re.compile(r"cbm|m3|m³|volume|体积|立方|unitof|uom|单位")
_SHORT_DIM_FIELDS = {
    "l": "length_mm", "len": "length_mm",
    "w": "width_mm", "wid": "width_mm",
    "h": "height_mm", "ht": "height_mm", "hgt": "height_mm",
}


def _weight_pref(key: str) -> int:
    """同为 weight_kg 候选时的偏好：毛重 > 未标明 > 净重。"""
    if "g.w" in key or "gross" in key or "毛重" in key:
        return 6
    if "n.w" in key or "net" in key or "净重" in key:
        return -4
    return 0


def build_column_map(headers: Sequence[Any]) -> Dict[str, str]:
    """原表头 → 标准字段。同名字段按分数取优，平手时取靠前的表头。"""
    inv: Dict[str, str] = {}
    for std, syns in COLUMN_SYNONYMS.items():
        for s in syns:
            inv[_norm_header(s)] = std

    best: Dict[str, Tuple[int, int, str]] = {}  # std -> (score, order, raw)
    for order, h in enumerate(headers):
        raw = str(h or "").strip()
        if not raw:
            continue
        key = _norm_header(raw)
        std = inv.get(key)
        score = 100 if std else 0
        if not std:
            short = _SHORT_DIM_RE.match(key)
            if short:
                std, score = _SHORT_DIM_FIELDS[short.group(1)], 92
        if not std:
            for cand, field, sc in _FUZZY_RULES:
                if cand in key:
                    if field == "__dims__" and _VOLUME_HEADER_RE.search(key):
                        continue
                    std, score = field, sc
                    break
        if not std:
            continue
        if std == "weight_kg":
            score += _weight_pref(key)
        cur = best.get(std)
        if cur is None or score > cur[0]:
            best[std] = (score, order, raw)
    ordered = sorted(best.items(), key=lambda kv: kv[1][1])
    return {raw: std for std, (_score, _order, raw) in ordered}


_CELL_UNIT = r"(?:mm|cm|m|inches|inch|in|ft|毫米|厘米|米|英寸|英尺|[\"″”]|['′])"
_DIM_TRIPLE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*" + _CELL_UNIT + r"?\s*[x×*✕/]\s*"
    r"(\d+(?:\.\d+)?)\s*" + _CELL_UNIT + r"?\s*[x×*✕/]\s*"
    r"(\d+(?:\.\d+)?)",
    re.I,
)
_CELL_UNIT_RE = re.compile(r"\d\s*(" + _CELL_UNIT[3:-1] + r")", re.I)
_UNIT_TO_MM = {
    "mm": 1.0, "毫米": 1.0, "cm": 10.0, "厘米": 10.0, "m": 1000.0, "米": 1000.0,
    "in": 25.4, "inch": 25.4, "inches": 25.4, "英寸": 25.4, '"': 25.4, "″": 25.4, "”": 25.4,
    "ft": 304.8, "英尺": 304.8, "'": 304.8, "′": 304.8,
}


def _cells_length_scale(values: Sequence[Any]) -> Optional[float]:
    """单元格自己写了单位（48" / 120cm）且全列一致时，返回乘到 mm 的系数；否则 None。"""
    found = set()
    for v in values:
        m = _CELL_UNIT_RE.search(str(v)) if v is not None else None
        if m:
            found.add(_UNIT_TO_MM[m.group(1).lower()])
    return found.pop() if len(found) == 1 else None


def _parse_dim_triple(v: Any) -> Optional[Tuple[float, float, float]]:
    """从「1200 x 400 x 300」这类合并尺寸单元格里取出三个数。"""
    if v is None:
        return None
    m = _DIM_TRIPLE_RE.search(str(v))
    if not m:
        return None
    try:
        return (float(m.group(1)), float(m.group(2)), float(m.group(3)))
    except ValueError:
        return None


def _to_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "")
    s = re.sub(r"[^\d.\-eE]", "", s)
    if not s or s in ("-", "."):
        return None
    try:
        return float(s)
    except ValueError:
        return None


#: 一个件数，可带尾随单位词："8" / "8件" / "10 pcs" / "3 EA" / "1,200"。逗号只认千分位；
#: "1,5"、"10/12"、"2-3"、"约5" 这类读不出唯一件数的写法一律不匹配。
_QTY_TEXT = re.compile(
    r"([+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE]\+?\d+)?)\s*[A-Za-z一-鿿.]{0,12}"
)


def _quantity_cell(v: Any) -> Tuple[str, int]:
    """数量格 → (状态, 件数)。只有 ok / missing 的件数可用。

    missing  没写 → 1 件（逐箱列行的装箱单通行写法）
    ok       正整数
    zero     明写 0：这一行本次不发，调用方跳过并计数——照字面读，不是猜
    invalid  负数 / 小数 / 非数值 / 布尔 / NaN / inf：没有哪种读法是表上写的意思，不猜

    此前走 _to_float + max(1, int(x or 1))：2.7 装成 2 件，"abc" 装成 1 件，"3 EA" 因为
    正则留下了字母 E 解析失败也装成 1 件，-3 的行整行消失，NaN / inf 直接抛异常。
    """
    if v is None:
        return "missing", 1
    if isinstance(v, bool):
        return "invalid", 0
    if isinstance(v, (int, float)):
        number = float(v)
    else:
        s = str(v).strip().strip("　")
        if not s:
            return "missing", 1
        m = _QTY_TEXT.fullmatch(s)
        if not m:
            return "invalid", 0
        number = float(m.group(1).replace(",", ""))
    if not math.isfinite(number):
        return "invalid", 0
    if number == 0:
        return "zero", 0
    if number < 0 or number != int(number):
        return "invalid", 0
    return "ok", int(number)


def _header_has_length_unit(header: str) -> bool:
    """表头是否明写了长度单位。明写的听表头的，没写才看单元格和量级。"""
    h = _norm_header(header)
    return bool(
        "mm" in h or "cm" in h or h.endswith("_m") or "(m)" in h or "英寸" in h or "英尺" in h
        or h.endswith(('"', "″", "”"))
        or re.search(r"(?:^|[(\[_/).\-])(?:in|inch|inches|ft|feet|foot)(?:$|[)\].])", h)
    )


def _infer_length_scale(header: str, values: List[Optional[float]]) -> float:
    """返回乘到 mm 的系数。"""
    h = _norm_header(header)
    if "mm" in h or "(mm)" in h:
        return 1.0
    if h.endswith("_cm") or "cm" in h or "(cm)" in h:
        return 10.0
    # 英制。此前 "Dimensions (in)" 的 48 会落到下面的量级启发式，被当成 48 米。
    # 单位词必须有分隔符在前、结尾或括号在后，"min" / "origin" 这类词不算。
    if re.search(r"(?:^|[(\[_/).\-])(?:in|inch|inches)(?:$|[)\].])", h) or "英寸" in h or h.endswith(('"', "″", "”")):
        return 25.4
    if re.search(r"(?:^|[(\[_/).\-])(?:ft|feet|foot)(?:$|[)\].])", h) or "英尺" in h:
        return 304.8
    if h.endswith("_m") or "(m)" in h or h in ("length_m", "width_m", "height_m", "长m", "长(m)"):
        return 1000.0
    # 启发式：中位值 < 30 → 可能是 m；< 300 且字段叫 length → cm 少见，按 mm
    nums = [x for x in values if x is not None and x > 0]
    if not nums:
        return 1.0
    nums_sorted = sorted(nums)
    mid = nums_sorted[len(nums_sorted) // 2]
    if mid <= 25:
        return 1000.0  # meters
    if mid <= 300 and ("m" in h and "mm" not in h):
        return 1000.0
    return 1.0


def _infer_weight_scale(header: str, values: List[Optional[float]]) -> float:
    """返回乘到 kg 的系数。注意：不可用 `'t' in header`（weight 含字母 t）。"""
    h = _norm_header(header)
    raw = str(header or "")
    # 磅。英制表里尺寸是英寸、重量是磅；只换算尺寸不换算重量，会得到一个尺寸对、
    # 重量高估 2.2 倍的方案，和吨当公斤是同一类错。
    if "kg" not in h and (re.search(r"(?:^|[(\[_/).\-])(?:lb|lbs|pound|pounds)(?:$|[)\].])", h) or "磅" in raw):
        return 0.45359237
    # 明确吨：_t / (t) / 吨 / weight_t / 单重t
    # 只排除 kg。上面的正则已要求 t 是独立词元（^t / _t / 结尾 t / "(t)"），
    # "weight" 里的字母 t 不满足该条件，无需再排除；排除它会让 "Gross Weight (t)"
    # 规范化后的 "grossweight(t)" 落回 1.0，把吨当公斤，1000 倍少报。
    if "吨" in raw:
        return 1000.0
    if re.search(r"(^|_)(t)($|[^a-z])", h) or h.endswith("_t") or "(t)" in h:
        if "kg" not in h:
            return 1000.0
    if (
        h in ("weight_t", "total_t", "单重t", "总重t", "吨")
        or h.endswith("weight_t")
        or (h.endswith("_t") and "weight" in h)
    ):
        return 1000.0
    # 克（非 kg）— 避免 "kg" 被误判
    if "kg" not in h and (h.endswith("_g") or h.endswith("(g)") or "(g)" in h):
        return 0.001
    nums = [x for x in values if x is not None and x > 0]
    if nums:
        mid = sorted(nums)[len(nums) // 2]
        if mid > 50000:
            return 0.001
    return 1.0


def normalize_category(raw: Any) -> str:
    s = str(raw or "").strip()
    if not s:
        return "generic"
    key = s.lower()
    if key in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[key]
    if s in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[s]
    for k, v in CATEGORY_ALIASES.items():
        if k in s or k in key:
            return v
    return s  # keep free text; caller may still use as-is


# 最近一次 rows_to_ir 清洗统计（parse_table_* 读取，避免改动返回类型）
_LAST_CLEAN_STATS: Dict[str, Any] = {}


def last_clean_stats() -> Dict[str, Any]:
    """返回最近一次 rows_to_ir 的清洗计数。"""
    return dict(_LAST_CLEAN_STATS)


def rows_to_ir(
    rows: Sequence[Dict[str, Any]],
    *,
    headers: Optional[Sequence[Any]] = None,
    source: str = "dict",
    source_path: str = "",
    profile_hint: str = "generic_table",
) -> List[Dict[str, Any]]:
    """字典行列表 → MaterialTableIR（同时兼容现有 materials API）。"""
    global _LAST_CLEAN_STATS
    clean_stats: Dict[str, int] = {
        "n_input_rows": 0,
        "n_kept": 0,
        "n_skip_empty_name": 0,
        "n_skip_noise_name": 0,
        "n_skip_zero_qty": 0,
        "n_skip_zero_placeholder": 0,
        "n_skip_summary_row": 0,
        "n_missing_weight": 0,
        "n_invalid_quantity": 0,
    }
    if not rows:
        _LAST_CLEAN_STATS = {**clean_stats, "n_skipped_total": 0}
        return []

    if headers is None:
        # 保留首次出现顺序
        seen: List[str] = []
        for r in rows:
            for k in r.keys():
                if k not in seen:
                    seen.append(str(k))
        headers = seen

    colmap = build_column_map(list(headers))
    # reverse: std -> original header
    std_to_raw = {std: raw for raw, std in colmap.items()}

    # collect raw numeric series for unit inference
    def series(std: str) -> List[Optional[float]]:
        raw_h = std_to_raw.get(std)
        if not raw_h:
            return []
        return [_to_float(r.get(raw_h)) for r in rows]

    def raw_cells(std: str) -> List[Any]:
        raw_h = std_to_raw.get(std)
        return [r.get(raw_h) for r in rows] if raw_h else []

    def length_scale(std: str, numbers: List[Optional[float]], cells: Sequence[Any]) -> float:
        header = std_to_raw.get(std, std)
        if _header_has_length_unit(header):
            return _infer_length_scale(header, numbers)
        return _cells_length_scale(cells) or _infer_length_scale(header, numbers)

    len_scale = {std: length_scale(std, series(std), raw_cells(std))
                 for std in ("length_mm", "width_mm", "height_mm")}
    wt_scale = _infer_weight_scale(std_to_raw.get("weight_kg", "weight_kg"), series("weight_kg"))
    tw_scale = _infer_weight_scale(
        std_to_raw.get("total_weight_kg", "total_weight_kg"), series("total_weight_kg")
    )

    # 合并尺寸列：先整表解析一遍，用所有数字一起推单位，避免逐行各推各的
    dims_raw_h = std_to_raw.get("__dims__")
    dims_triples: List[Optional[Tuple[float, float, float]]] = (
        [_parse_dim_triple(r.get(dims_raw_h)) for r in rows] if dims_raw_h else []
    )
    dims_scale = 1.0
    if dims_raw_h:
        _flat = [x for tri in dims_triples if tri for x in tri]
        dims_scale = length_scale("__dims__", _flat, [r.get(dims_raw_h) for r in rows])

    out: List[Dict[str, Any]] = []
    # 汇总/小计行（整行品名，不误杀「合计架」类真货子串尾）
    _SUMMARY_EXACT = {
        "合计",
        "小计",
        "总计",
        "汇总",
        "总合计",
        "本页合计",
        "grand total",
        "subtotal",
        "total",
        "sum",
    }
    for i, r in enumerate(rows, 1):
        clean_stats["n_input_rows"] += 1
        got: Dict[str, Any] = {}
        for raw_h, std in colmap.items():
            got[std] = r.get(raw_h)

        name = got.get("name")
        if name is None or str(name).strip() == "" or str(name).strip("\u3000 \t") == "":
            clean_stats["n_skip_empty_name"] += 1
            continue
        name_s = str(name).strip().strip("\u3000")
        # 噪声行：整行注释/占位（禁止用「表头」「跳过」等子串误杀真货名）
        if name_s.startswith("#") or name_s.startswith("//"):
            clean_stats["n_skip_noise_name"] += 1
            continue
        low_name = name_s.lower().strip()
        if low_name in (
            "nan",
            "none",
            "null",
            "-",
            "—",
            "n/a",
            "na",
            "header",
            "headers",
            "# comment",
            "comment",
            "备注",
            "备注行",
            "说明",
            "placeholder",
        ):
            clean_stats["n_skip_noise_name"] += 1
            continue
        # 仅匹配整行或「注释:」类前缀，不匹配品名中含「表头/跳过」的真货
        if name_s in ("注释", "这是注释", "表头", "无效空行", "无效空行应跳过", "跳过"):
            clean_stats["n_skip_noise_name"] += 1
            continue
        if name_s.startswith("注释") and (
            len(name_s) <= 2 or name_s[2] in (":", "：", " ", "\t", "-")
        ):
            clean_stats["n_skip_noise_name"] += 1
            continue
        if name_s.startswith("这是注释"):
            clean_stats["n_skip_noise_name"] += 1
            continue
        if low_name in _SUMMARY_EXACT or name_s in _SUMMARY_EXACT:
            clean_stats["n_skip_summary_row"] += 1
            continue
        # 仅标点/空白品名
        if all(not ch.isalnum() and ord(ch) < 128 for ch in name_s.replace(" ", "")):
            # allow CJK product names (non-ascii alnum check fails for CJK)
            if not any("\u4e00" <= ch <= "\u9fff" for ch in name_s):
                clean_stats["n_skip_noise_name"] += 1
                continue

        qty_state, qty = _quantity_cell(got.get("quantity"))
        # 显式 0 数量：噪声，不升成 1
        if qty_state == "zero":
            clean_stats["n_skip_zero_qty"] += 1
            continue
        # 写了但读不出件数：行留下、如实标记，由闸门转人工（同 weight_missing）。
        # 既无尺寸又无重量的仍按下面的全零占位行丢弃——那是噪声，不是货。
        quantity_invalid = qty_state == "invalid"

        def dim(std: str) -> float:
            if _parse_dim_triple(got.get(std)):
                return 0.0  # "1200*400*300" 不是一个数；见下方按合并格处理
            v = _to_float(got.get(std))
            if v is None:
                return 0.0
            return round(v * len_scale[std], 3)

        L, W, H = dim("length_mm"), dim("width_mm"), dim("height_mm")
        _stray = _parse_dim_triple(got.get("length_mm"))
        if _stray and L <= 0 and W <= 0 and H <= 0:
            L, W, H = (round(x * len_scale["length_mm"], 3) for x in _stray)
        if dims_raw_h and (L <= 0 or W <= 0 or H <= 0):
            tri = dims_triples[i - 1] if i - 1 < len(dims_triples) else None
            if tri:
                cand = [round(x * dims_scale, 3) for x in tri]
                if L <= 0:
                    L = cand[0]
                if W <= 0:
                    W = cand[1]
                if H <= 0:
                    H = cand[2]
        dims_estimated = L <= 0 or W <= 0 or H <= 0

        unit_w = _to_float(got.get("weight_kg"))
        if unit_w is not None:
            unit_w = unit_w * wt_scale
        total_w = _to_float(got.get("total_weight_kg"))
        if total_w is not None:
            total_w = total_w * tw_scale
        # 件数不知道时不推另一格：单重 × ? 与 总重 ÷ ? 都是编出来的数，留 0（= 没写）
        if total_w is None and unit_w is not None and not quantity_invalid:
            total_w = unit_w * qty
        if unit_w is None and total_w is not None and not quantity_invalid:
            unit_w = total_w / qty
        unit_w = float(unit_w or 0.0)
        total_w = float(total_w or 0.0)
        # 全零占位行（无尺寸无重量）丢弃
        if L <= 0 and W <= 0 and H <= 0 and unit_w <= 0 and total_w <= 0:
            clean_stats["n_skip_zero_placeholder"] += 1
            continue

        cat_raw = got.get("category") or ""
        cat = normalize_category(cat_raw) if cat_raw else _guess_category(L, W, H, unit_w, name_s)

        # 整行没有任何重量：不是「0 公斤」，是不知道。照 0 装箱会算出一个
        # 建立在零质量上的方案，N0 按重、载重余量与 VGM 全部失真且无告警，
        # 所以这里如实标记，由入口（MCP ingest / 上传）拦下转人工。
        weight_missing = unit_w <= 0 and total_w <= 0
        if weight_missing:
            clean_stats["n_missing_weight"] += 1

        if quantity_invalid:
            clean_stats["n_invalid_quantity"] += 1

        conf = 0.95
        if dims_estimated:
            conf -= 0.35
        if weight_missing:
            conf -= 0.2
        if quantity_invalid:
            conf -= 0.2
        conf = max(0.1, min(1.0, conf))

        mid = str(got.get("id") or got.get("part_no") or f"M{i:03d}").strip()
        item = {
            "id": mid,
            "name": name_s,
            "spec": str(got.get("spec") or ""),
            "quantity": qty,
            "weight_kg": round(unit_w, 4),
            "total_weight_kg": round(total_w, 4),
            "length_mm": L,
            "width_mm": W,
            "height_mm": H,
            "part_no": str(got.get("part_no") or ""),
            "category": cat,
            "note": str(got.get("note") or ""),
            "meta": {
                "source": source,
                "source_path": source_path,
                "column_map": dict(colmap),
                "units_in": {
                    "length_scale_to_mm": len_scale,
                    "weight_scale_to_kg": {"weight_kg": wt_scale, "total_weight_kg": tw_scale},
                },
                "confidence": round(conf, 3),
                "dims_estimated": dims_estimated,
                "weight_missing": weight_missing,
                "profile_hint": profile_hint,
            },
        }
        if quantity_invalid:
            # quantity 留 0 而不是 1：meta 被下游丢掉时，数值本身仍过不了 rows_invalid_quantity
            item["meta"]["quantity_invalid"] = True
            item["meta"]["quantity_raw"] = str(got.get("quantity"))
        out.append(item)
        clean_stats["n_kept"] += 1
    clean_stats["n_skipped_total"] = int(clean_stats["n_input_rows"]) - int(
        clean_stats["n_kept"]
    )
    _LAST_CLEAN_STATS = dict(clean_stats)
    return out


def _guess_category(L: float, W: float, H: float, weight: float, name: str) -> str:
    n = name.lower()
    if any(k in name or k in n for k in ("玻璃", "fragile", "易碎")):
        return "fragile"
    if any(k in name or k in n for k in ("吨袋", "集装袋", "bulk")):
        return "bulk_bag"
    if any(k in name or k in n for k in ("托盘", "pallet")):
        return "pallet"
    if any(k in name or k in n for k in ("纸箱", "carton")):
        return "carton"
    if L >= 4000:
        return "long_item"
    if max(L, W, H) <= 800 and weight <= 50:
        return "carton"
    return "generic"


def load_csv(path: PathLike, encoding: str = "utf-8-sig") -> List[Dict[str, Any]]:
    path = Path(path)
    with path.open("r", encoding=encoding, newline="") as f:
        sample = f.read(8192)
        f.seek(0)
        # Prefer explicit delimiter counts (Sniffer often fails on short EU files)
        delim = ","
        for candidate in (";", "\t", ","):
            if sample.count(candidate) >= 2:
                # header line vote
                first = sample.splitlines()[0] if sample else ""
                if first.count(candidate) >= 2:
                    delim = candidate
                    break
        else:
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
                delim = dialect.delimiter
            except csv.Error:
                delim = ","
        reader = csv.DictReader(f, delimiter=delim)
        rows = [dict(r) for r in reader]
        headers = list(reader.fieldnames or [])
    return rows_to_ir(rows, headers=headers, source="csv", source_path=str(path))


def load_xlsx(path: PathLike, sheet: Optional[str] = None) -> List[Dict[str, Any]]:
    import openpyxl

    path = Path(path)
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    if sheet and sheet in wb.sheetnames:
        ws = wb[sheet]
    elif "materials" in wb.sheetnames:
        ws = wb["materials"]
    else:
        ws = wb.active
    data = list(ws.iter_rows(values_only=True))
    wb.close()
    if not data:
        return []
    headers = [str(c or "").strip() for c in data[0]]
    rows: List[Dict[str, Any]] = []
    for row in data[1:]:
        d = {headers[i]: (row[i] if i < len(row) else None) for i in range(len(headers))}
        # skip full_flow non-material
        rt = d.get("row_type")
        if rt and str(rt) not in ("material", "materials", ""):
            continue
        rows.append(d)
    return rows_to_ir(rows, headers=headers, source="xlsx", source_path=str(path))


def load_json(path: PathLike) -> List[Dict[str, Any]]:
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(data, dict):
        data = data.get("materials") or data.get("rows") or data.get("items") or []
    if not isinstance(data, list):
        raise ValueError("JSON must be list or {materials|rows|items: list}")
    # already IR?
    if data and isinstance(data[0], dict) and "length_mm" in data[0] and "name" in data[0]:
        out = []
        for i, m in enumerate(data, 1):
            item = dict(m)
            item.setdefault("id", f"M{i:03d}")
            item.setdefault("quantity", 1)
            meta = dict(item.get("meta") or {})
            meta.setdefault("source", "json")
            meta.setdefault("source_path", str(path))
            meta.setdefault("profile_hint", "generic_table")
            meta.setdefault("confidence", 0.99)
            meta.setdefault("dims_estimated", float(item.get("length_mm") or 0) <= 0)
            item["meta"] = meta
            out.append(item)
        return out
    return rows_to_ir(data, source="json", source_path=str(path))


def load_table(path: PathLike, **kwargs: Any) -> List[Dict[str, Any]]:
    path = Path(path)
    suf = path.suffix.lower()
    if suf in (".csv", ".tsv", ".txt"):
        return load_csv(path)
    if suf in (".xlsx", ".xlsm"):
        return load_xlsx(path, sheet=kwargs.get("sheet"))
    if suf == ".json":
        return load_json(path)
    if suf == ".pdf":
        return load_packing_list_pdf(path)
    raise ValueError(f"unsupported table type: {suf}")


def load_packing_list_pdf(path: PathLike) -> List[Dict[str, Any]]:
    """PDF 装箱单 → IR 行。

    正式装箱单常常没有单件 L×W×H，解析器按品名 + 单重 + 包装类型做工程估算。
    估算出来的尺寸一路会变成柜数，所以每行都带 dims_estimated=True 且把置信度
    压到 0.45，让上层把它和量出来的尺寸区分开。
    """
    from packing_assistant.tools.packing_list_parser import parse_packing_list_pdf

    parsed = parse_packing_list_pdf(path)
    rows: List[Dict[str, Any]] = []
    for m in parsed.get("materials") or []:
        estimated = bool(m.get("dims_estimated"))
        total_kg = float(m.get("total_weight_kg") or 0.0)
        rows.append(
            {
                "id": m.get("id") or "",
                "name": m.get("name") or "",
                "spec": m.get("spec") or "",
                "quantity": int(m.get("quantity") or 1),
                "weight_kg": float(m.get("weight_kg") or 0.0),
                "total_weight_kg": total_kg,
                "length_mm": float(m.get("length_mm") or 0.0),
                "width_mm": float(m.get("width_mm") or 0.0),
                "height_mm": float(m.get("height_mm") or 0.0),
                "part_no": "",
                "category": m.get("category") or "generic",
                "note": m.get("package") or "",
                "meta": {
                    "source": "pdf",
                    "source_path": str(path),
                    "column_map": {},
                    "units_in": {},
                    "confidence": 0.45 if estimated else 0.8,
                    "dims_estimated": estimated,
                    "weight_missing": total_kg <= 0,
                    "profile_hint": "packing_list_pdf",
                    "container_no": m.get("container_no") or "",
                },
            }
        )
    return rows


def ir_to_materials(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """IR → 现有 materials API（去掉 meta 也可保留）。"""
    mats = []
    for m in rows:
        # 数量读不出来的行保持 0，不在这里又升回 1 件
        unknown_qty = bool((m.get("meta") or {}).get("quantity_invalid"))
        mats.append(
            {
                "id": m.get("id"),
                "name": m.get("name"),
                "spec": m.get("spec") or "",
                "quantity": 0 if unknown_qty else int(m.get("quantity") or 1),
                "weight_kg": float(m.get("weight_kg") or 0),
                "total_weight_kg": float(m.get("total_weight_kg") or 0),
                "length_mm": float(m.get("length_mm") or 0),
                "width_mm": float(m.get("width_mm") or 0),
                "height_mm": float(m.get("height_mm") or 0),
                "part_no": m.get("part_no") or "",
                "category": m.get("category") or "generic",
                "note": m.get("note") or "",
                "meta": m.get("meta") or {},
            }
        )
    return mats


def _no_rows_reason(path: "Path") -> str:
    """一行都没解析出来时，说清楚下一步该做什么。"""
    if str(path).lower().endswith(".pdf"):
        return (
            "PDF 里没有识别出物料行：行版式解析是按某一类装箱单调的，"
            "换一种版式就认不出来。请把这份单子另存为 xlsx/csv 再上传，"
            "或提供一份该版式的样本以便补充规则。"
        )
    return "no material rows parsed"


def parse_table_file(path: PathLike, **kwargs: Any) -> Dict[str, Any]:
    """统一入口：文件 → {materials, ir, stats, column_map}。"""
    path = Path(path)
    ir = load_table(path, **kwargs)
    mats = ir_to_materials(ir)
    n_est = sum(1 for m in ir if (m.get("meta") or {}).get("dims_estimated"))
    confs = [(m.get("meta") or {}).get("confidence", 0) for m in ir]
    colmap = {}
    if ir:
        colmap = dict((ir[0].get("meta") or {}).get("column_map") or {})
    clean = last_clean_stats()
    return {
        "ok": bool(mats),
        "path": str(path),
        "materials": mats,
        "ir": ir,
        "column_map": colmap,
        "stats": {
            "n_rows": len(mats),
            "n_dims_estimated": n_est,
            "avg_confidence": round(sum(confs) / len(confs), 3) if confs else 0.0,
            "total_weight_kg": round(sum(float(m.get("total_weight_kg") or 0) for m in mats), 3),
            "n_input_rows": clean.get("n_input_rows"),
            "n_skipped_total": clean.get("n_skipped_total"),
            "n_skip_noise_name": clean.get("n_skip_noise_name"),
            "n_skip_summary_row": clean.get("n_skip_summary_row"),
            "n_skip_zero_qty": clean.get("n_skip_zero_qty"),
            "n_skip_zero_placeholder": clean.get("n_skip_zero_placeholder"),
            "n_invalid_quantity": clean.get("n_invalid_quantity"),
            "clean": clean,
        },
        "errors": [] if mats else [_no_rows_reason(path)],
    }


def parse_table_bytes(
    data: bytes,
    *,
    filename: str = "upload.csv",
    **kwargs: Any,
) -> Dict[str, Any]:
    """网关上传入口：bytes → 临时文件 → parse_table_file（与 CLI 同一路径）。"""
    import tempfile

    suf = Path(filename or "upload.csv").suffix.lower() or ".csv"
    if suf not in (".csv", ".tsv", ".txt", ".xlsx", ".xlsm", ".json", ".pdf"):
        suf = ".csv"
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(suffix=suf, prefix="tbl_")
        import os

        with os.fdopen(fd, "wb") as f:
            f.write(data)
        out = parse_table_file(tmp_path, **kwargs)
        out["path"] = filename or out.get("path")
        out["source"] = "upload"
        return out
    except Exception as e:
        return {
            "ok": False,
            "path": filename,
            "materials": [],
            "ir": [],
            "column_map": {},
            "stats": {"n_rows": 0},
            "errors": [f"{type(e).__name__}: {e}"],
        }
    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass


def parse_table_rows(
    rows: Sequence[Dict[str, Any]],
    *,
    headers: Optional[Sequence[Any]] = None,
    source: str = "api_rows",
) -> Dict[str, Any]:
    """已解析的字典行 → 与文件入口相同的返回形状。"""
    ir = rows_to_ir(list(rows), headers=headers, source=source)
    mats = ir_to_materials(ir)
    colmap = {}
    if ir:
        colmap = dict((ir[0].get("meta") or {}).get("column_map") or {})
    n_est = sum(1 for m in ir if (m.get("meta") or {}).get("dims_estimated"))
    clean = last_clean_stats()
    return {
        "ok": bool(mats),
        "path": "",
        "materials": mats,
        "ir": ir,
        "column_map": colmap,
        "stats": {
            "n_rows": len(mats),
            "n_dims_estimated": n_est,
            "total_weight_kg": round(sum(float(m.get("total_weight_kg") or 0) for m in mats), 3),
            "n_input_rows": clean.get("n_input_rows"),
            "n_skipped_total": clean.get("n_skipped_total"),
            "clean": clean,
        },
        "errors": [] if mats else ["no material rows"],
    }


# AUTONOMY_EXTRA_SYNONYMS_V2
for _std, _extra in {
    "name": ("货品名称", "中文品名", "商品名称", "material_name", "article"),
    "quantity": ("装箱数", "包装数量", "包装件数", "pcs"),
    "weight_kg": ("毛重kg", "毛重(kg)", "净重kg", "净重(kg)", "单件重量"),
    "part_no": ("商品编码", "条码", "barcode", "物料号"),
    "length_mm": ("外径", "总长", "全长"),
}.items():
    if _std in COLUMN_SYNONYMS:
        COLUMN_SYNONYMS[_std] = tuple(dict.fromkeys(list(COLUMN_SYNONYMS[_std]) + list(_extra)))
