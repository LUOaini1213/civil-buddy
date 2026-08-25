"""Civil Codex host config. Same knobs as Codex: sandbox + approval.

Not a kernel jail. danger-full-access is intentionally absent: secrets and
generic spawn stay denied in packing_assistant.sandbox.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

_ROOT = Path(__file__).resolve().parents[2]
CONFIRM = "我明白，将由持证人员签认"

SANDBOX_MODES = ("read-only", "workspace-write")
APPROVAL_MODES = ("untrusted", "on-request", "never")


@dataclass
class CivilConfig:
    sandbox: str = "workspace-write"
    approval: str = "on-request"
    max_steps: int = 8
    max_parallel: int = 4
    model: str = ""
    job_root: str = ""

    def allow_write(self) -> bool:
        return self.sandbox == "workspace-write"

    def auto_confirm(self) -> bool:
        return self.approval == "never"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["confirm_sentence"] = CONFIRM
        d["sandbox_modes"] = list(SANDBOX_MODES)
        d["approval_modes"] = list(APPROVAL_MODES)
        return d


def _strip_mode(value: str, allowed: tuple[str, ...], default: str) -> str:
    v = (value or "").strip().lower().replace("_", "-")
    aliases = {
        "readonly": "read-only",
        "ro": "read-only",
        "write": "workspace-write",
        "ws": "workspace-write",
        "agent": "workspace-write",
        "full-auto": "never",
        "yolo": "never",
        "trusted": "on-request",
        "ask": "on-request",
        "onrequest": "on-request",
    }
    v = aliases.get(v, v)
    return v if v in allowed else default


def _parse_toml_lite(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    section = ""
    for raw in (text or "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        key = k.strip()
        if section and section not in {"civil", "workspace", ""}:
            key = f"{section}.{key}"
        val = v.strip().strip('"').strip("'")
        out[key] = val
    return out


def _apply_map(cfg: CivilConfig, kv: Dict[str, str]) -> None:
    if "sandbox" in kv:
        cfg.sandbox = _strip_mode(kv["sandbox"], SANDBOX_MODES, cfg.sandbox)
    if "approval" in kv:
        cfg.approval = _strip_mode(kv["approval"], APPROVAL_MODES, cfg.approval)
    if "max_steps" in kv:
        try:
            cfg.max_steps = max(1, min(32, int(kv["max_steps"])))
        except ValueError:
            pass
    if "max_parallel" in kv:
        try:
            cfg.max_parallel = max(1, min(8, int(kv["max_parallel"])))
        except ValueError:
            pass
    if "model" in kv:
        cfg.model = kv["model"]
    if kv.get("job_root"):
        cfg.job_root = kv["job_root"]
    if kv.get("workspace.job_root"):
        cfg.job_root = kv["workspace.job_root"]


def config_paths() -> list[Path]:
    cwd = Path.cwd()
    home = Path.home() / ".civil-buddy" / "config.toml"
    return [
        _ROOT / "civil.toml",
        cwd / "civil.toml",
        cwd / ".civil-buddy" / "config.toml",
        home,
    ]


def load_config() -> CivilConfig:
    cfg = CivilConfig()
    for path in config_paths():
        if not path.is_file():
            continue
        try:
            _apply_map(cfg, _parse_toml_lite(path.read_text(encoding="utf-8")))
        except OSError:
            continue
    env_s = os.environ.get("CIVIL_SANDBOX") or ""
    env_a = os.environ.get("CIVIL_APPROVAL") or ""
    if env_s:
        cfg.sandbox = _strip_mode(env_s, SANDBOX_MODES, cfg.sandbox)
    if env_a:
        cfg.approval = _strip_mode(env_a, APPROVAL_MODES, cfg.approval)
    if os.environ.get("CIVIL_JOB_ROOT"):
        cfg.job_root = os.environ["CIVIL_JOB_ROOT"]
    return cfg


def decide_gate(
    *,
    intent: str,
    risk: str,
    confirmed: bool,
    cfg: Optional[CivilConfig] = None,
) -> str:
    """Return go | hitl | read_only."""
    c = cfg or load_config()
    if intent == "chat":
        return "go"
    if not c.allow_write():
        return "read_only"
    if c.auto_confirm() or confirmed:
        return "go"
    if c.approval == "untrusted":
        return "hitl"
    if (risk or "low") == "high":
        return "hitl"
    return "go"
