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
    空间利用率: str = "0%"
    重量利用率: str = "0%"
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


def validate_packing_result(
    result: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    warnings: List[str] = []
    try:
        model = PackingResultModel.model_validate(result or {})
        data = model.model_dump()
        # 业务规则
        ids = [b["箱号"] for b in data["箱子列表"]]
        if len(ids) != len(set(ids)):
            warnings.append("箱子列表存在重复箱号")
        for b in data["箱子列表"]:
            dims = b.get("外尺寸_mm") or {}
            if float(dims.get("长") or 0) <= 0:
                warnings.append(f"{b.get('箱号')} 长度无效")
            if float(b.get("毛重_kg") or 0) < 0:
                warnings.append(f"{b.get('箱号')} 毛重为负")
            sc = b.get("结构计算") or {}
            if not sc:
                warnings.append(f"{b.get('箱号')} 缺少结构计算")
            elif sc.get("结论") == "不通过":
                warnings.append(f"{b.get('箱号')} 结构计算不通过: {sc.get('风险点')}")
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
