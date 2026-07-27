"""
Pydantic Schema：工具 I/O 与关键状态字段的运行时校验。

TypedDict 负责图内传递；Pydantic 负责边界校验与规范化。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class DimensionMMModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    长: float = 0
    宽: float = 0
    高: float = 0


class MaterialModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    序号: Optional[str] = None
    名称: str = ""
    规格: str = ""
    数量: int = 1
    单重_kg: float = 0
    外尺寸_mm: DimensionMMModel = Field(default_factory=DimensionMMModel)
    备注: str = ""

    @field_validator("数量", mode="before")
    @classmethod
    def _qty(cls, v: Any) -> int:
        try:
            return max(int(float(v or 1)), 1)
        except (TypeError, ValueError):
            return 1

    @field_validator("单重_kg", mode="before")
    @classmethod
    def _w(cls, v: Any) -> float:
        try:
            return float(v or 0)
        except (TypeError, ValueError):
            return 0.0


class CargoItemModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    名称: str = ""
    数量: int = 1
    单重_kg: float = 0
    备注: str = ""


class BoxModel(BaseModel):
    """
    成箱模型。体积字段（订柜/展示）：
    - content_m3 / crate_fill_ratio / outer_m3 / booking_volume_m3
    中英文键均可（extra=allow）；校验时尽量归一。
    """

    model_config = ConfigDict(extra="allow")

    箱号: str
    箱型: str
    外尺寸_mm: DimensionMMModel
    毛重_kg: float = 0
    净重_kg: float = 0
    箱自重_kg: float = 0
    装载内容: List[CargoItemModel] = Field(default_factory=list)
    特殊属性: List[str] = Field(default_factory=list)
    结构计算: Dict[str, Any] = Field(default_factory=dict)
    结构结论: str = ""
    # —— 体积分层（与 packing / adapters 对齐）——
    content_m3: Optional[float] = Field(
        default=None, description="箱内货件体积 m³（订柜分子用）"
    )
    crate_fill_ratio: Optional[float] = Field(
        default=None, description="箱内填充率 content/inner 或 content/outer"
    )
    fill_ratio: Optional[float] = Field(
        default=None, description="crate_fill_ratio 别名"
    )
    outer_m3: Optional[float] = Field(
        default=None, description="箱外廓 AABB 体积 m³（仅 3D/展示）"
    )
    booking_volume_m3: Optional[float] = Field(
        default=None, description="订柜贡献体积 min(outer, content×k)"
    )

    @field_validator(
        "content_m3",
        "crate_fill_ratio",
        "fill_ratio",
        "outer_m3",
        "booking_volume_m3",
        mode="before",
    )
    @classmethod
    def _opt_float(cls, v: Any) -> Optional[float]:
        if v is None or v == "":
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None


class PackingResultModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    箱子列表: List[BoxModel] = Field(default_factory=list)


class LayoutItemModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    箱号: str
    起始位置_m: float = 0
    长度_m: float = 0
    层级: int = 1
    颜色: str = "blue"


class ContainerPlanModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    柜型: str
    结论: str = ""
    空间利用率: str = "0%"  # 兼容：外廓摆柜率（非订柜）
    重量利用率: str = "0%"
    # API/英文路径双率（可选）
    outer_space_utilization: Optional[float] = None
    booking_volume_utilization: Optional[float] = None
    weight_utilization: Optional[float] = None
    布局: List[LayoutItemModel] = Field(default_factory=list)
    详情: Dict[str, Any] = Field(default_factory=dict)


def _fmt_errors(err: ValidationError) -> List[str]:
    return [f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in err.errors()]


def validate_materials(
    materials: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    out: List[Dict[str, Any]] = []
    for i, raw in enumerate(materials or []):
        try:
            m = MaterialModel.model_validate(raw or {})
            out.append(m.model_dump())
        except ValidationError as e:
            warnings.append(f"materials[{i}] 校验失败: {'; '.join(_fmt_errors(e))}")
            if isinstance(raw, dict):
                out.append(raw)
    return out, warnings


def _box_volume_fields(b: Dict[str, Any]) -> Dict[str, Any]:
    """从中/英键读取体积字段（与 adapters 透传一致）。"""
    content = b.get("content_m3")
    if content is None:
        content = b.get("content_volume_m3")
    fill = b.get("crate_fill_ratio")
    if fill is None:
        fill = b.get("fill_ratio")
    outer = b.get("outer_m3")
    booking = b.get("booking_volume_m3")
    return {
        "content_m3": content,
        "crate_fill_ratio": fill,
        "outer_m3": outer,
        "booking_volume_m3": booking,
    }


def validate_packing_result(
    result: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    warnings: List[str] = []
    try:
        # 归一：API boxes 可能只有 box_id；尽量并入中文键后再校验
        raw_in = dict(result or {})
        boxes_in = list(raw_in.get("箱子列表") or raw_in.get("boxes") or [])
        norm_boxes: List[Dict[str, Any]] = []
        for b in boxes_in:
            if not isinstance(b, dict):
                continue
            nb = dict(b)
            if "箱号" not in nb and nb.get("box_id"):
                nb["箱号"] = nb.get("box_id")
            if "箱型" not in nb and nb.get("box_type") is not None:
                nb["箱型"] = nb.get("box_type") or ""
            if "外尺寸_mm" not in nb and nb.get("outer_size_mm"):
                o = nb.get("outer_size_mm") or {}
                nb["外尺寸_mm"] = {
                    "长": o.get("length") or o.get("长") or 0,
                    "宽": o.get("width") or o.get("宽") or 0,
                    "高": o.get("height") or o.get("高") or 0,
                }
            # 体积字段别名归一
            vf = _box_volume_fields(nb)
            if vf["content_m3"] is not None:
                nb["content_m3"] = vf["content_m3"]
            if vf["crate_fill_ratio"] is not None:
                nb["crate_fill_ratio"] = vf["crate_fill_ratio"]
                nb.setdefault("fill_ratio", vf["crate_fill_ratio"])
            if vf["outer_m3"] is not None:
                nb["outer_m3"] = vf["outer_m3"]
            if vf["booking_volume_m3"] is not None:
                nb["booking_volume_m3"] = vf["booking_volume_m3"]
            norm_boxes.append(nb)
        raw_in["箱子列表"] = norm_boxes

        model = PackingResultModel.model_validate(raw_in)
        data = model.model_dump()
        # 业务规则
        ids = [b["箱号"] for b in data["箱子列表"]]
        if len(ids) != len(set(ids)):
            warnings.append("箱子列表存在重复箱号")
        for b in data["箱子列表"]:
            dims = b.get("外尺寸_mm") or {}
            bid = b.get("箱号") or "?"
            if float(dims.get("长") or 0) <= 0:
                warnings.append(f"{bid} 长度无效")
            if float(b.get("毛重_kg") or 0) < 0:
                warnings.append(f"{bid} 毛重为负")
            sc = b.get("结构计算") or {}
            if not sc:
                warnings.append(f"{bid} 缺少结构计算")
            elif sc.get("结论") == "不通过":
                warnings.append(f"{bid} 结构计算不通过: {sc.get('风险点')}")
            # 体积字段缺失 WARN（不阻断）
            vf = _box_volume_fields(b)
            missing = [k for k, v in vf.items() if v is None]
            if missing:
                warnings.append(
                    f"{bid} 缺少体积字段 {','.join(missing)} "
                    f"（订柜依赖 content_m3/crate_fill_ratio/booking_volume_m3；outer_m3 仅 3D）"
                )
            # dump 时保留体积键
            for k, v in vf.items():
                if v is not None:
                    b[k] = v
            if b.get("crate_fill_ratio") is not None and b.get("fill_ratio") is None:
                b["fill_ratio"] = b["crate_fill_ratio"]
        return data, warnings
    except ValidationError as e:
        warnings.extend(_fmt_errors(e))
        return result or {"箱子列表": []}, warnings


def validate_container_plan(
    plan: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    warnings: List[str] = []
    try:
        model = ContainerPlanModel.model_validate(plan or {})
        data = model.model_dump()
        for key in ("空间利用率", "重量利用率"):
            val = str(data.get(key) or "")
            if not val.endswith("%"):
                warnings.append(f"{key} 格式应为百分数字符串，当前: {val!r}")
        return data, warnings
    except ValidationError as e:
        warnings.extend(_fmt_errors(e))
        return plan or {}, warnings


def parse_util_pct(text: str | None) -> Optional[float]:
    if text is None:
        return None
    try:
        return float(str(text).replace("%", "").strip())
    except ValueError:
        return None
