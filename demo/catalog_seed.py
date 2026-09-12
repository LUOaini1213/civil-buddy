from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import sys

# Uvicorn also loads this module with demo/ as its working directory. Keep
# catalog import independent of config (which may load environment files).
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


@dataclass(frozen=True)
class Expert:
    id: str
    name: str
    category: str
    category_name: str
    title: str
    delivers: str
    risk: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    pipeline: str = "理解任务 → 检索本库与大类库 → 提纲 → 独立成稿 → 自检"
    builtin: bool = True
    enabled: bool = True

    @staticmethod
    def default_pipeline() -> str:
        return "理解任务 → 检索本库与大类库 → 提纲 → 独立成稿 → 自检"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["aliases"] = list(self.aliases)
        return d


# Built-ins are consumed from the Rust/Python shared authority. Expert remains
# the public data class used by user-authored demo.store entries.
from packing_assistant.expert_capabilities import load_seed

_SEED = load_seed()
CATEGORIES = _SEED["categories"]
EXPERTS: list[Expert] = [
    Expert(**{key: tuple(row[key]) if key == "aliases" else row[key]
              for key in Expert.__dataclass_fields__ if key in row})
    for row in _SEED["experts"]
]
