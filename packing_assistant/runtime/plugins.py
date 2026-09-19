"""Plugins: a company's own posts, as a folder or a zip — SOP, form template, knowledge. No code.

Codex plugins bundle skills with MCP servers, which is to say with programs. A plugin here is
declarative on purpose: nothing in it is ever executed, so installing one cannot run anything.

    <plugin>/plugin.json                 {"schema": "civil.plugin.v1", "name", "version", "title", "description", "publisher"}
    <plugin>/skills/<id>/SKILL.md        Agent Skills format; frontmatter: name, description, title, delivers, risk, aliases
    <plugin>/skills/<id>/template.md     optional — the deliverable, with {{key}} slots
    <plugin>/skills/<id>/form.json       optional — {"fields": [{"key", "label", "aliases": [], "required": bool}]}
    <plugin>/skills/<id>/knowledge.md    optional — what search_kb and the chat explanation read

Found in ``~/.civil-buddy/plugins/<name>`` and ``<job>/.civil-buddy/plugins/<name>`` (a plugin that
travels with a job folder). Once found, its skills are ordinary skills: in the catalog, routable by
``$id`` / name, loadable by the model, drafted through the same pipeline and the same guards.

What keeps a plugin from being a way in:
    no shadowing   a skill id that a built-in post (or an earlier plugin) already has is rejected
    risk           an untrusted plugin's skills are all high-risk — every write needs the confirm
                   sentence — whatever its SKILL.md says. ``civil plugin trust <name>`` makes its own
                   labels count. Trust lives in the USER's ~/.civil-buddy/plugins.json, keyed by the
                   plugin's content hash: a job folder cannot trust itself, and editing a trusted
                   plugin un-trusts it.
    templates      only fill slots from what the user wrote (label: value) — no expressions, no includes.
                   A template that states a verdict (可以开工 …) is rejected; quantities baked into a
                   template are reported at install and listed at the foot of every draft it produces.
    files          only .md and .json are read or copied; everything else is ignored and named.
                   Zip entries that climb out of the archive are rejected.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import zipfile
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCHEMA = "civil.plugin.v1"
NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
ALLOWED_SUFFIXES = (".md", ".json")
MAX_SKILLS, MAX_FILE_BYTES, MAX_KNOWLEDGE_BYTES = 50, 64 * 1024, 512 * 1024
_SLOT = re.compile(r"\{\{\s*([a-z][a-z0-9_]{0,40})\s*\}\}")
_VALUE_END = re.compile(r"[，,；;。\n]")


class PluginError(ValueError):
    pass


@dataclass(frozen=True)
class PluginSkill:
    id: str
    plugin: str
    folder: Path
    name: str
    description: str
    title: str
    delivers: str
    declared_risk: str
    aliases: Tuple[str, ...]
    fields: Tuple[Dict[str, Any], ...] = ()

    @property
    def template(self) -> Optional[Path]:
        path = self.folder / "template.md"
        return path if path.is_file() else None

    @property
    def knowledge(self) -> Optional[Path]:
        path = self.folder / "knowledge.md"
        return path if path.is_file() else None


@dataclass
class Plugin:
    name: str
    folder: Path
    scope: str                      # "user" | "job"
    manifest: Dict[str, Any]
    skills: List[PluginSkill] = field(default_factory=list)
    digest: str = ""
    trusted: bool = False
    warnings: List[str] = field(default_factory=list)
    ignored: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# where things live
# ---------------------------------------------------------------------------

def user_dir() -> Path:
    return Path.home() / ".civil-buddy" / "plugins"


def _state_file() -> Path:
    return Path.home() / ".civil-buddy" / "plugins.json"


def _job_dir() -> Optional[Path]:
    from packing_assistant.runtime.workspace import active

    job = active()
    return job / ".civil-buddy" / "plugins" if job else None


def _state() -> Dict[str, Any]:
    try:
        data = json.loads(_state_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"trusted": {}}
    return data if isinstance(data, dict) and isinstance(data.get("trusted"), dict) else {"trusted": {}}


def _save_state(state: Dict[str, Any]) -> None:
    path = _state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# reading one plugin
# ---------------------------------------------------------------------------

def _digest(folder: Path) -> Tuple[str, List[str]]:
    sha, ignored = hashlib.sha256(), []
    for path in sorted(p for p in folder.rglob("*") if p.is_file()):
        relative = path.relative_to(folder).as_posix()
        if path.suffix.lower() not in ALLOWED_SUFFIXES:
            ignored.append(relative)
            continue
        sha.update(relative.encode("utf-8") + b"\0" + path.read_bytes() + b"\0")
    return sha.hexdigest(), ignored


def _read(path: Path, limit: int) -> str:
    if path.stat().st_size > limit:
        raise PluginError(f"{path.name} 超过 {limit // 1024} KiB")
    return path.read_text(encoding="utf-8-sig")


def _skill(folder: Path, plugin: str) -> Tuple[PluginSkill, List[str]]:
    from packing_assistant.runtime.expert_skills import split_frontmatter
    from packing_assistant.tools.number_provenance import quantities
    from packing_assistant.tools.verdict_guard import stated_verdicts

    skill_id, warnings = folder.name, []
    if not NAME_RE.match(skill_id) or "--" in skill_id:
        raise PluginError(f"技能目录名无效：{skill_id}（小写字母、数字、连字符）")
    meta, body = split_frontmatter(_read(folder / "SKILL.md", MAX_FILE_BYTES))
    if not (meta.get("description") or "").strip() or not body.strip():
        raise PluginError(f"{skill_id}/SKILL.md 需要 frontmatter 里的 description 和正文 SOP")
    if (meta.get("name") or skill_id).strip() != skill_id:
        raise PluginError(f"{skill_id}/SKILL.md 的 name 必须等于目录名（显示名写在 title 里）")
    risk = (meta.get("risk") or "high").strip().lower()
    if risk not in {"low", "high"}:
        raise PluginError(f"{skill_id}: risk 只能是 low 或 high")
    fields: List[Dict[str, Any]] = []
    form = folder / "form.json"
    if form.is_file():
        try:
            declared = json.loads(_read(form, MAX_FILE_BYTES)).get("fields")
        except (ValueError, AttributeError) as exc:
            raise PluginError(f"{skill_id}/form.json 不是有效的 JSON 对象") from exc
        for row in declared or []:
            key, label = str((row or {}).get("key") or ""), str((row or {}).get("label") or "").strip()
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,40}", key) or not label:
                raise PluginError(f"{skill_id}/form.json: 每个字段要有 key（小写标识符）和 label")
            fields.append({"key": key, "label": label, "aliases": [str(a) for a in row.get("aliases") or [] if str(a).strip()],
                           "required": row.get("required") is True})
    template = folder / "template.md"
    if template.is_file():
        text = _read(template, MAX_FILE_BYTES)
        verdicts = stated_verdicts(text)
        if verdicts:
            raise PluginError(f"{skill_id}/template.md 下了不该由文稿下的结论：" + "、".join(v["text"] for v in verdicts))
        unknown = sorted(set(_SLOT.findall(text)) - {f["key"] for f in fields} - _BUILTIN_SLOTS)
        if unknown:
            raise PluginError(f"{skill_id}/template.md 用了 form.json 里没有的字段：" + "、".join(unknown))
        baked = [q.text for q in quantities(_SLOT.sub("", text))]
        if baked:
            warnings.append(f"{skill_id}: 模板自带数字（不是用户给的，成稿里会逐个注明）：" + "、".join(dict.fromkeys(baked)))
    knowledge = folder / "knowledge.md"
    if knowledge.is_file():
        _read(knowledge, MAX_KNOWLEDGE_BYTES)
    aliases = tuple(a.strip() for a in re.split(r"[,，、]", meta.get("aliases") or "") if a.strip())
    name = (meta.get("title") or skill_id).strip()
    return PluginSkill(id=skill_id, plugin=plugin, folder=folder, name=name, description=meta["description"].strip(),
                       title=(meta.get("title") or name).strip(), delivers=(meta.get("delivers") or "内部讨论草稿").strip(),
                       declared_risk=risk, aliases=aliases, fields=tuple(fields)), warnings


_BUILTIN_SLOTS = {"project", "jurisdiction", "user_text"}


def read_plugin(folder: Path, scope: str = "user") -> Plugin:
    """Parse and check one plugin folder. Raises PluginError with a sentence a person can act on."""
    folder = Path(folder)
    try:
        manifest = json.loads(_read(folder / "plugin.json", MAX_FILE_BYTES))
    except OSError as exc:
        raise PluginError("缺少 plugin.json") from exc
    except ValueError as exc:
        raise PluginError("plugin.json 不是有效的 JSON") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise PluginError(f'plugin.json 的 schema 必须是 "{SCHEMA}"')
    name = str(manifest.get("name") or "")
    if not NAME_RE.match(name) or "--" in name:
        raise PluginError("plugin.json 的 name 只能用小写字母、数字、连字符")
    skill_dirs = sorted(p for p in (folder / "skills").iterdir() if p.is_dir()) if (folder / "skills").is_dir() else []
    if not skill_dirs:
        raise PluginError("插件里没有技能：skills/<id>/SKILL.md")
    if len(skill_dirs) > MAX_SKILLS:
        raise PluginError(f"一个插件最多 {MAX_SKILLS} 个技能")
    plugin = Plugin(name=name, folder=folder, scope=scope, manifest=manifest)
    for skill_dir in skill_dirs:
        if not (skill_dir / "SKILL.md").is_file():
            raise PluginError(f"skills/{skill_dir.name} 里没有 SKILL.md")
        skill, warnings = _skill(skill_dir, name)
        plugin.skills.append(skill)
        plugin.warnings += warnings
    plugin.digest, plugin.ignored = _digest(folder)
    plugin.trusted = _state()["trusted"].get(name) == plugin.digest
    if plugin.ignored:
        plugin.warnings.append("这些文件不是 .md / .json，不会被读取也不会被安装：" + "、".join(plugin.ignored[:8]))
    return plugin


# ---------------------------------------------------------------------------
# what is installed
# ---------------------------------------------------------------------------

def _builtin_ids() -> set:
    from packing_assistant.runtime.expert_skills import SKILLS_DIR

    return {p.name for p in SKILLS_DIR.iterdir() if p.is_dir()} if SKILLS_DIR.is_dir() else set()


@lru_cache(maxsize=1)
def _discover(user: str, job: str) -> Tuple[Tuple[Plugin, ...], Tuple[str, ...]]:
    taken, found, problems = _builtin_ids(), [], []
    for scope, base in (("user", Path(user)), ("job", Path(job) if job else None)):
        if base is None or not base.is_dir():
            continue
        for folder in sorted(p for p in base.iterdir() if p.is_dir() and not p.name.startswith(".")):
            try:
                plugin = read_plugin(folder, scope)
                clash = sorted(s.id for s in plugin.skills if s.id in taken)
                if clash:
                    raise PluginError("技能 id 已被内置岗位或其他插件占用：" + "、".join(clash))
            except PluginError as exc:
                problems.append(f"{folder.name}（{scope}）：{exc}")
                continue
            taken |= {s.id for s in plugin.skills}
            found.append(plugin)
    return tuple(found), tuple(problems)


def installed() -> List[Plugin]:
    job = _job_dir()
    return list(_discover(str(user_dir()), str(job) if job else "")[0])


def problems() -> List[str]:
    job = _job_dir()
    return list(_discover(str(user_dir()), str(job) if job else "")[1])


def reload() -> None:
    """Forget what was discovered — after install / remove / trust, and when the job folder changes."""
    from packing_assistant import expert_roster

    _discover.cache_clear()
    expert_roster._load.cache_clear()


def skill(skill_id: str) -> Optional[PluginSkill]:
    for plugin in installed():
        for item in plugin.skills:
            if item.id == skill_id:
                return item
    return None


def effective_risk(item: PluginSkill) -> str:
    owner = next((p for p in installed() if p.name == item.plugin), None)
    return item.declared_risk if owner is not None and owner.trusted else "high"


# ---------------------------------------------------------------------------
# install / remove / trust
# ---------------------------------------------------------------------------

def _unpack(archive: Path, into: Path) -> Path:
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            target = (into / info.filename).resolve()
            if not str(target).startswith(str(into.resolve())) or info.filename.startswith(("/", "\\")):
                raise PluginError(f"压缩包里的路径越界：{info.filename}")
            if info.file_size > MAX_KNOWLEDGE_BYTES:
                raise PluginError(f"压缩包里的文件过大：{info.filename}")
        bundle.extractall(into)
    roots = [p for p in into.iterdir() if p.is_dir()]
    return into if (into / "plugin.json").is_file() else roots[0] if len(roots) == 1 else into


def install(source: Path, *, scope: str = "user") -> Plugin:
    """Copy a checked plugin (folder or .zip) into place. Only .md / .json files are copied."""
    import tempfile

    source = Path(source)
    base = user_dir() if scope == "user" else _job_dir()
    if base is None:
        raise PluginError("--job 需要先进入作业文件夹（civil init 或 -C）")
    with tempfile.TemporaryDirectory(prefix="civil-plugin-") as scratch:
        folder = _unpack(source, Path(scratch)) if source.is_file() and source.suffix.lower() == ".zip" else source
        if not folder.is_dir():
            raise PluginError(f"找不到插件：{source}")
        plugin = read_plugin(folder, scope)
        others = {s.id for p in installed() if p.name != plugin.name for s in p.skills} | _builtin_ids()
        clash = sorted(s.id for s in plugin.skills if s.id in others)
        if clash:
            raise PluginError("技能 id 已被内置岗位或其他插件占用：" + "、".join(clash))
        target = base / plugin.name
        if target.exists():
            shutil.rmtree(target)
        for path in sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in ALLOWED_SUFFIXES):
            copy = target / path.relative_to(folder)
            copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, copy)
    reload()
    return next(p for p in installed() if p.name == plugin.name)


def remove(name: str) -> bool:
    for plugin in installed():
        if plugin.name == name:
            shutil.rmtree(plugin.folder)
            state = _state()
            state["trusted"].pop(name, None)
            _save_state(state)
            reload()
            return True
    return False


def set_trust(name: str, trusted: bool) -> Plugin:
    plugin = next((p for p in installed() if p.name == name), None)
    if plugin is None:
        raise PluginError(f"没有安装插件 {name}")
    state = _state()
    if trusted:
        state["trusted"][name] = plugin.digest
    else:
        state["trusted"].pop(name, None)
    _save_state(state)
    reload()
    return next(p for p in installed() if p.name == name)


# ---------------------------------------------------------------------------
# drafting from a template
# ---------------------------------------------------------------------------

def field_values(item: PluginSkill, text: str) -> Dict[str, str]:
    """``label: value`` as the user wrote it, up to the next delimiter. Nothing is inferred."""
    values: Dict[str, str] = {}
    for spec in item.fields:
        for label in (spec["label"], *spec["aliases"]):
            match = re.search(re.escape(label) + r"\s*[:：]\s*", text or "")
            if match:
                rest = (text or "")[match.end():]
                end = _VALUE_END.search(rest)
                value = (rest[: end.start()] if end else rest).strip()
                if value:
                    values[spec["key"]] = value
                    break
    return values


def render_draft(item: PluginSkill, text: str, *, project: str = "", jurisdiction: str = "") -> Optional[str]:
    """The plugin's template with the user's values in it — None when the skill has no template."""
    from packing_assistant.tools.number_provenance import quantities

    if item.template is None:
        return None
    template = item.template.read_text(encoding="utf-8-sig")
    values = field_values(item, text)
    missing = [spec["label"] for spec in item.fields if spec["required"] and spec["key"] not in values]
    builtin = {"project": project or "UNSPECIFIED", "jurisdiction": jurisdiction or "UNSPECIFIED", "user_text": (text or "").strip() or "（未提供）"}
    body = _SLOT.sub(lambda m: values.get(m.group(1)) or builtin.get(m.group(1)) or "待填", template)
    baked = list(dict.fromkeys(q.text for q in quantities(_SLOT.sub("", template))))
    lines = [f"# {item.name}（插件 {item.plugin} · AI 草稿 · 内部讨论）", "",
             "本文件由 Civil Buddy 按插件模板生成，只填入用户原话里写明的内容；未写明的栏为「待填」。不是签认件，不作为投标、开工或验收依据。", ""]
    if missing:
        lines += ["必填而用户未给的栏：" + "、".join(missing), ""]
    lines += [body.rstrip(), "", "## 用户原文", "", builtin["user_text"], ""]
    if baked:
        lines += [f"模板自带的数字（出自插件 {item.plugin} 的模板，不是本轮资料）：" + "、".join(baked), ""]
    return "\n".join(lines)
