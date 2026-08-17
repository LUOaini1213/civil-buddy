"""Application-level sandbox: path + spawn policy.

Not a kernel jail (Windows has no Landlock/Seatbelt here). Writes and
agent-initiated opens stay inside allowed roots; .env / secret / key paths
are denied; generic spawn stays blocked.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

GENERIC_SPAWN_KINDS = frozenset({"generic", "shell", "spawn", "arbitrary", "cmd"})
GENERIC_SPAWN_STEMS = frozenset(
    {
        "cmd",
        "cmd.exe",
        "powershell",
        "powershell.exe",
        "pwsh",
        "pwsh.exe",
        "bash",
        "sh",
        "zsh",
        "wscript",
        "wscript.exe",
        "cscript",
        "cscript.exe",
    }
)
ALLOWED_HELPER_STEMS = frozenset(
    {"mineru", "docling", "marker", "marker_single", "python", "python.exe", "py", "py.exe"}
)
ALLOWED_SCRIPT_NAMES = frozenset(
    {
        "run_packing_sidecar.py",
        "scan_forbidden_inventions.py",
        "validate.py",
    }
)
SECRET_NAMES = frozenset({".env", ".env.local", ".env.production", ".env.development"})
SECRET_SUBSTR = ("secret", "api_key", "apikey", "private_key")
SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx")


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    path: str = ""
    action: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "ok": self.allowed,
            "reason": self.reason,
            "path": self.path,
            "action": self.action,
        }


@dataclass
class SandboxProfile:
    allowed_write_roots: List[Path] = field(default_factory=list)
    deny_names: Iterable[str] = field(default_factory=lambda: SECRET_NAMES)
    deny_substrings: Iterable[str] = field(default_factory=lambda: SECRET_SUBSTR)
    deny_suffixes: Iterable[str] = field(default_factory=lambda: SECRET_SUFFIXES)

    def resolved_roots(self) -> List[Path]:
        out: List[Path] = []
        for r in self.allowed_write_roots:
            try:
                out.append(Path(r).expanduser().resolve())
            except OSError:
                out.append(Path(r).expanduser())
        return out


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_profile() -> SandboxProfile:
    root = repo_root()
    roots = [
        root / "output",
        root / "demo" / "out",
        root / "demo" / "kb",
        root / "demo" / "data",
        root / "workbench" / "out",
    ]
    extra = (os.getenv("CIVIL_SANDBOX_ROOTS") or os.getenv("CIVIL_SANDBOX_ROOT") or "").strip()
    if extra:
        for part in extra.split(os.pathsep):
            if part.strip():
                roots.append(Path(part.strip()))
    out_dir = (os.getenv("PACKING_OUTPUT_DIR") or "").strip()
    if out_dir:
        roots.append(Path(out_dir))
    return SandboxProfile(allowed_write_roots=roots)


def _norm(path: Union[str, Path]) -> Path:
    p = Path(path)
    try:
        return p.expanduser().resolve()
    except OSError:
        return p.expanduser()


def _is_secret(path: Path, profile: SandboxProfile) -> Optional[str]:
    name = path.name.lower()
    hay = str(path).replace("\\", "/").lower()
    deny_names = {str(n).lower() for n in profile.deny_names}
    if name in deny_names or path.name in set(profile.deny_names):
        return f"secret path denied: {path.name}"
    for sub in profile.deny_substrings:
        if sub.lower() in hay:
            return f"secret path denied: contains {sub}"
    for suf in profile.deny_suffixes:
        if name.endswith(str(suf).lower()):
            return f"secret path denied: suffix {suf}"
    return None


def _inside_roots(path: Path, roots: Sequence[Path]) -> bool:
    for root in roots:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def check_write(path: Union[str, Path], *, profile: Optional[SandboxProfile] = None) -> Decision:
    prof = profile or default_profile()
    target = _norm(path)
    secret = _is_secret(target, prof)
    if secret:
        return Decision(False, secret, str(target), "write")
    roots = prof.resolved_roots()
    if not roots:
        return Decision(False, "sandbox has no allowed write roots", str(target), "write")
    if not _inside_roots(target, roots):
        return Decision(False, "write outside allowed root", str(target), "write")
    return Decision(True, "ok", str(target), "write")


def check_open(path: Union[str, Path], *, profile: Optional[SandboxProfile] = None) -> Decision:
    prof = profile or default_profile()
    target = _norm(path)
    secret = _is_secret(target, prof)
    if secret:
        return Decision(False, secret, str(target), "open")
    roots = prof.resolved_roots()
    if not roots:
        return Decision(False, "sandbox has no allowed roots", str(target), "open")
    if not _inside_roots(target, roots):
        return Decision(False, "open outside allowed root", str(target), "open")
    return Decision(True, "ok", str(target), "open")


def check_spawn(
    command: Union[str, Sequence[str], None] = None,
    *,
    kind: Optional[str] = None,
    profile: Optional[SandboxProfile] = None,
) -> Decision:
    _ = profile
    k = (kind or "").strip().lower()
    if k in GENERIC_SPAWN_KINDS:
        return Decision(False, "generic spawn blocked", action="spawn")
    argv: List[str]
    if command is None:
        argv = []
    elif isinstance(command, (list, tuple)):
        argv = [str(x) for x in command]
    else:
        argv = str(command).split()
    if not argv:
        return Decision(False, "generic spawn blocked", action="spawn")
    stem = Path(argv[0]).name.lower()
    if stem in GENERIC_SPAWN_STEMS:
        return Decision(False, "generic spawn blocked", action="spawn")
    if stem in ALLOWED_HELPER_STEMS:
        # python/py only for allowlisted helper scripts
        if stem.startswith("py"):
            script = next((Path(a).name.lower() for a in argv[1:] if a.endswith(".py")), "")
            if script and script not in {s.lower() for s in ALLOWED_SCRIPT_NAMES}:
                return Decision(False, "generic spawn blocked", action="spawn")
        return Decision(True, "allowlisted helper", action="spawn")
    return Decision(False, "generic spawn blocked", action="spawn")


def assert_write(path: Union[str, Path], *, profile: Optional[SandboxProfile] = None) -> Path:
    d = check_write(path, profile=profile)
    if not d.allowed:
        raise PermissionError(d.reason)
    return _norm(path)


def assert_open(path: Union[str, Path], *, profile: Optional[SandboxProfile] = None) -> Path:
    d = check_open(path, profile=profile)
    if not d.allowed:
        raise PermissionError(d.reason)
    return _norm(path)


def request_spawn(
    command: Union[str, Sequence[str], None] = None,
    *,
    kind: Optional[str] = None,
    profile: Optional[SandboxProfile] = None,
) -> Decision:
    """Real spawn entry: every agent spawn goes through here."""
    return check_spawn(command, kind=kind, profile=profile)


def guarded_write_text(
    path: Union[str, Path],
    text: str,
    *,
    profile: Optional[SandboxProfile] = None,
    encoding: str = "utf-8",
) -> Path:
    target = assert_write(path, profile=profile)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding=encoding)
    return target


def guarded_open_read(
    path: Union[str, Path],
    *,
    profile: Optional[SandboxProfile] = None,
    encoding: str = "utf-8",
) -> str:
    target = assert_open(path, profile=profile)
    return target.read_text(encoding=encoding)
