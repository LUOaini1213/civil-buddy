//! ux(round19)：项目 / 会话索引（左栏「项目 > 会话」两级列表的数据面）。
//!
//! # 为什么是 JSON 三件套，而不是 SQLite
//!
//! 发布包（`scripts/package-workbench-release.ps1:45-52`）只拷 exe + demo/kb +
//! demo/static + skills，**没有 `packing_assistant/`、没有 `data/civilbuddy.db`**。
//! 所以「`projects` 表 + `sessions.project_id`」对「评委下载的 exe 上真能用」这个
//! 硬指标贡献为零。此处由 Rust 自持三份 JSON，零依赖：
//!
//! - `<out_root>/_index/projects.v1.json` —— 项目注册表，**唯一可写真源**
//! - `<out_root>/<session_id>/session.meta.json` —— 每会话侧车（title / project_id）
//! - `<out_root>/<session_id>/transcript.jsonl` —— 对话正文（点会话可续聊）
//!
//! # 为什么不复用 session.summary.json 的 project 槽
//!
//! 实测 2554 个该文件里 **2551 个 `project="UNSPECIFIED"`**，只有 3 个是真名；
//! 且 Rust 侧从不写它（写它的只有 :8000 与 threads 路径的 Python）。靠它自动归类
//! 等于全仓一个「未归类」桶。另外 `memory.py:36-49` 的 `save_summary()` 是**整体
//! 覆写**固定 5 键，往里塞 project_id 会被下一次 `assemble_context()` 抹掉。
//!
//! # 为什么不拿 trace.json 的 project 字段自动建项目
//!
//! 实测高频值是 `"问"`（99 条，前端从输入框前 40 字现搓的产物）、`H-worker-brief`
//! （78 条，eval fixture）。自动建档会造出几十个垃圾项目，比「全部未归类」更糟。
//! 因此：**归类是自动的，建档是人的动作。**
//!
//! # 扫盘成本
//!
//! `demo/out` 实测 3250 个目录 / 9365 文件。分级读取：`read_dir` 一层 → 跳过 `_`
//! 前缀（`_threads` 实证存在）与不过白名单的名字 → 优先读几百字节的 meta →
//! 没有 meta 的降级为「目录名 + mtime」行，**绝不打开 trace.json** → 按 mtime
//! 降序截断到 `CIVIL_SESSION_INDEX_MAX`（默认 500）。

use crate::config::Paths;
use serde_json::{json, Value};
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};

pub const SCHEMA_PROJECTS: &str = "civil.projects.v1";
pub const SCHEMA_SESSIONS: &str = "civil.sessions.v1";
pub const SCHEMA_SESSION_DETAIL: &str = "civil.session.detail.v1";
pub const INBOX_ID: &str = "p-inbox";
pub const INBOX_NAME: &str = "未归类";

const DEFAULT_LIMIT: usize = 50;
const MAX_LIMIT: usize = 100;
const NAME_MAX_CHARS: usize = 60;
const TITLE_MAX_CHARS: usize = 40;
const TRANSCRIPT_TAIL: usize = 200;
const TEXT_MAX_BYTES: usize = 8000;

fn index_max() -> usize {
    std::env::var("CIVIL_SESSION_INDEX_MAX")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(500)
}

/// 写锁：注册表与 meta 的所有写入串行化（抄 `store.rs:11-14` 的 catalog_lock 范式）。
fn projects_lock() -> &'static Mutex<()> {
    static LOCK: Mutex<()> = Mutex::new(());
    &LOCK
}

/// session id 白名单。合并 `attach.rs:26 sanitize_session` 的语义，另加两条：
/// 拒 `_` 前缀（`demo/out/_threads` 是真实存在的非会话目录）、拒空。
pub fn safe_session_id(s: &str) -> Result<String, String> {
    if s.starts_with('_') {
        return Err("session_id 无效".into());
    }
    let out: String = s
        .chars()
        .filter(|c| c.is_ascii_alphanumeric() || *c == '-' || *c == '_')
        .take(32)
        .collect();
    if out.len() < 4 || out.starts_with('_') {
        return Err("session_id 无效".into());
    }
    Ok(out)
}

fn safe_project_id(s: &str) -> Result<String, String> {
    if s == INBOX_ID {
        return Ok(s.to_string());
    }
    let ok = s.len() == 10
        && s.starts_with("p-")
        && s[2..].chars().all(|c| c.is_ascii_lowercase() || c.is_ascii_digit());
    if ok {
        Ok(s.to_string())
    } else {
        Err("project_id 无效".into())
    }
}

/// 项目名：去首尾空白、拒纯空白与控制字符、按**字符数**（不是字节）截断，中文名不炸。
fn clean_name(s: &str) -> Result<String, String> {
    let t = s.trim();
    if t.is_empty() {
        return Err("项目名不能为空".into());
    }
    if t.chars().any(|c| c.is_control()) {
        return Err("项目名含控制字符".into());
    }
    Ok(t.chars().take(NAME_MAX_CHARS).collect())
}

fn now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

fn mtime_secs(p: &Path) -> u64 {
    fs::metadata(p)
        .and_then(|m| m.modified())
        .ok()
        .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

fn index_dir(paths: &Paths) -> PathBuf {
    paths.out_root.join("_index")
}

fn registry_path(paths: &Paths) -> PathBuf {
    index_dir(paths).join("projects.v1.json")
}

fn meta_path(paths: &Paths, sid: &str) -> PathBuf {
    paths.out_root.join(sid).join("session.meta.json")
}

fn transcript_path(paths: &Paths, sid: &str) -> PathBuf {
    paths.out_root.join(sid).join("transcript.jsonl")
}

/// 原子写：先写 `.tmp` 再 rename。注册表比 catalog 值钱，不用 `store.rs` 的裸 `fs::write`。
fn write_atomic(path: &Path, text: &str) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let tmp = path.with_extension("tmp");
    fs::write(&tmp, text).map_err(|e| e.to_string())?;
    fs::rename(&tmp, path).map_err(|e| e.to_string())
}

// ---------------------------------------------------------------- 注册表

fn empty_registry() -> Value {
    json!({"schema": SCHEMA_PROJECTS, "version": 1, "projects": []})
}

pub fn load_registry(paths: &Paths) -> Value {
    let p = registry_path(paths);
    if !p.is_file() {
        return empty_registry();
    }
    fs::read_to_string(&p)
        .ok()
        .and_then(|raw| serde_json::from_str::<Value>(&raw).ok())
        .filter(|v| v.get("projects").map(|x| x.is_array()).unwrap_or(false))
        .unwrap_or_else(empty_registry)
}

fn save_registry(paths: &Paths, reg: &Value) -> Result<(), String> {
    let text = serde_json::to_string_pretty(reg).map_err(|e| e.to_string())?;
    write_atomic(&registry_path(paths), &text)
}

fn projects_of(reg: &Value) -> Vec<Value> {
    reg.get("projects")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default()
}

fn is_tombstone(p: &Value) -> bool {
    p.get("merged_into").and_then(|v| v.as_str()).is_some()
}

fn is_active(p: &Value) -> bool {
    !is_tombstone(p) && !p.get("archived").and_then(|v| v.as_bool()).unwrap_or(false)
}

/// 解析 project_id：跟随墓碑 `merged_into` **一跳**（限一跳，防环）。
/// 空 / 不存在 / 已归档 三种情况一律归 `p-inbox` —— 注册表被手工改坏也不会有会话消失。
fn resolve_pid(reg: &Value, pid: &str) -> String {
    if pid.is_empty() {
        return INBOX_ID.to_string();
    }
    let list = projects_of(reg);
    let Some(found) = list.iter().find(|p| p.get("id").and_then(|v| v.as_str()) == Some(pid)) else {
        return INBOX_ID.to_string();
    };
    if let Some(into) = found.get("merged_into").and_then(|v| v.as_str()) {
        let hop = list
            .iter()
            .find(|p| p.get("id").and_then(|v| v.as_str()) == Some(into));
        return match hop {
            Some(h) if is_active(h) => into.to_string(),
            _ => INBOX_ID.to_string(),
        };
    }
    if is_active(found) {
        pid.to_string()
    } else {
        INBOX_ID.to_string()
    }
}

fn gen_pid(reg: &Value) -> String {
    // 不用随机数：以「当前秒 + 已有条数」派生，冲突则线性探测。测试可复现。
    let list = projects_of(reg);
    let mut seed = now_secs().wrapping_mul(31).wrapping_add(list.len() as u64);
    loop {
        let id = format!("p-{:08x}", (seed & 0xffff_ffff) as u32);
        if !list
            .iter()
            .any(|p| p.get("id").and_then(|v| v.as_str()) == Some(id.as_str()))
        {
            return id;
        }
        seed = seed.wrapping_add(1);
    }
}

/// 建档幂等：按 casefold 精确比对已有 name + aliases，命中直接返回那条。
pub fn create_project(paths: &Paths, name: &str) -> Result<(Value, bool), String> {
    let name = clean_name(name)?;
    let _g = projects_lock().lock().map_err(|_| "lock".to_string())?;
    let mut reg = load_registry(paths);
    let fold = name.to_lowercase();
    for p in projects_of(&reg) {
        if !is_active(&p) {
            continue;
        }
        let mut names = vec![p.get("name").and_then(|v| v.as_str()).unwrap_or("").to_string()];
        if let Some(a) = p.get("aliases").and_then(|v| v.as_array()) {
            names.extend(a.iter().filter_map(|x| x.as_str()).map(|s| s.to_string()));
        }
        if names.iter().any(|n| n.to_lowercase() == fold) {
            return Ok((p, true));
        }
    }
    let id = gen_pid(&reg);
    let now = now_secs();
    let item = json!({
        "id": id, "name": name, "aliases": [],
        "created_at": now, "updated_at": now, "archived": false
    });
    if let Some(arr) = reg.get_mut("projects").and_then(|v| v.as_array_mut()) {
        arr.push(item.clone());
    }
    save_registry(paths, &reg)?;
    Ok((item, false))
}

pub fn patch_project(paths: &Paths, pid: &str, name: Option<&str>, archived: Option<bool>) -> Result<Value, String> {
    let pid = safe_project_id(pid)?;
    if pid == INBOX_ID {
        return Err("未归类是内置项目，不能改名或归档".into());
    }
    let _g = projects_lock().lock().map_err(|_| "lock".to_string())?;
    let mut reg = load_registry(paths);
    let mut out = None;
    if let Some(arr) = reg.get_mut("projects").and_then(|v| v.as_array_mut()) {
        for p in arr.iter_mut() {
            if p.get("id").and_then(|v| v.as_str()) != Some(pid.as_str()) {
                continue;
            }
            if let Some(n) = name {
                let n = clean_name(n)?;
                // 旧名进 aliases，自动归类仍能按旧名命中
                let old = p.get("name").and_then(|v| v.as_str()).unwrap_or("").to_string();
                if !old.is_empty() && old != n {
                    let mut al: Vec<Value> = p
                        .get("aliases")
                        .and_then(|v| v.as_array())
                        .cloned()
                        .unwrap_or_default();
                    if !al.iter().any(|x| x.as_str() == Some(old.as_str())) {
                        al.push(json!(old));
                    }
                    p["aliases"] = json!(al);
                }
                p["name"] = json!(n);
            }
            if let Some(a) = archived {
                p["archived"] = json!(a);
            }
            p["updated_at"] = json!(now_secs());
            out = Some(p.clone());
            break;
        }
    }
    let Some(item) = out else {
        return Err("项目不存在".into());
    };
    save_registry(paths, &reg)?;
    Ok(item)
}

/// 合并：把 from 改写成墓碑（**保留在数组里不删**），name+aliases 追加进 into。
/// 已写进 N 个 session.meta.json 的旧 id 因此不需要回写。
pub fn merge_project(paths: &Paths, from: &str, into: &str) -> Result<Value, String> {
    let from = safe_project_id(from)?;
    let into = safe_project_id(into)?;
    if from == into {
        return Err("不能合并到自身".into());
    }
    if from == INBOX_ID || into == INBOX_ID {
        return Err("未归类是内置项目，不参与合并".into());
    }
    let _g = projects_lock().lock().map_err(|_| "lock".to_string())?;
    let mut reg = load_registry(paths);
    let list = projects_of(&reg);
    let src = list
        .iter()
        .find(|p| p.get("id").and_then(|v| v.as_str()) == Some(from.as_str()))
        .cloned()
        .ok_or_else(|| "源项目不存在".to_string())?;
    if !list
        .iter()
        .any(|p| p.get("id").and_then(|v| v.as_str()) == Some(into.as_str()) && is_active(p))
    {
        return Err("目标项目不存在或已归档".into());
    }
    let mut carry: Vec<String> = vec![src.get("name").and_then(|v| v.as_str()).unwrap_or("").to_string()];
    if let Some(a) = src.get("aliases").and_then(|v| v.as_array()) {
        carry.extend(a.iter().filter_map(|x| x.as_str()).map(|s| s.to_string()));
    }
    let mut merged = None;
    if let Some(arr) = reg.get_mut("projects").and_then(|v| v.as_array_mut()) {
        for p in arr.iter_mut() {
            match p.get("id").and_then(|v| v.as_str()) {
                Some(id) if id == from => {
                    *p = json!({"id": from, "merged_into": into});
                }
                Some(id) if id == into => {
                    let mut al: Vec<String> = p
                        .get("aliases")
                        .and_then(|v| v.as_array())
                        .map(|a| a.iter().filter_map(|x| x.as_str()).map(|s| s.to_string()).collect())
                        .unwrap_or_default();
                    for c in &carry {
                        if !c.is_empty() && !al.contains(c) {
                            al.push(c.clone());
                        }
                    }
                    p["aliases"] = json!(al);
                    p["updated_at"] = json!(now_secs());
                    merged = Some(p.clone());
                }
                _ => {}
            }
        }
    }
    save_registry(paths, &reg)?;
    merged.ok_or_else(|| "合并失败".to_string())
}

// ---------------------------------------------------------------- 会话侧车

fn load_meta(paths: &Paths, sid: &str) -> Option<Value> {
    fs::read_to_string(meta_path(paths, sid))
        .ok()
        .and_then(|raw| serde_json::from_str::<Value>(&raw).ok())
}

fn truncate_chars(s: &str, n: usize) -> String {
    s.chars().take(n).collect()
}

/// 每轮对话收尾时调用。**只做归类，不建档**（见模块头注释）。
/// 失败一律吞掉：绝不因为索引写不动而阻断 SSE。
pub fn touch_session(paths: &Paths, session: &str, user_text: &str, project_hint: &str) {
    let Ok(sid) = safe_session_id(session) else {
        return;
    };
    let _g = match projects_lock().lock() {
        Ok(g) => g,
        Err(_) => return,
    };
    let reg = load_registry(paths);
    let mut meta = load_meta(paths, &sid).unwrap_or_else(|| {
        json!({
            "schema": "civil.session.meta.v1",
            "session_id": sid,
            "title": "",
            "title_source": "auto",
            "project_id": "",
            "project_source": "auto",
            "created_at": now_secs(),
            "turns": 0
        })
    });

    // 标题：首轮定标题，之后不覆盖（手动改过的更不覆盖）
    let has_title = meta.get("title").and_then(|v| v.as_str()).unwrap_or("").is_empty();
    if has_title && !user_text.trim().is_empty() {
        let first = user_text.lines().next().unwrap_or("").trim();
        meta["title"] = json!(truncate_chars(first, TITLE_MAX_CHARS));
    }

    // 归类：显式 hint 优先（manual）；否则按已有项目的 name+aliases 子串匹配（auto）
    let manual = meta.get("project_source").and_then(|v| v.as_str()) == Some("manual");
    if !manual {
        if !project_hint.is_empty() {
            if let Ok(p) = safe_project_id(project_hint) {
                meta["project_id"] = json!(resolve_pid(&reg, &p));
                meta["project_source"] = json!("manual");
            }
        } else if meta.get("project_id").and_then(|v| v.as_str()).unwrap_or("").is_empty() {
            if let Some(pid) = match_project(&reg, user_text) {
                meta["project_id"] = json!(pid);
                meta["project_source"] = json!("auto");
            }
        }
    }

    meta["turns"] = json!(meta.get("turns").and_then(|v| v.as_u64()).unwrap_or(0) + 1);
    meta["updated_at"] = json!(now_secs());
    if !user_text.trim().is_empty() {
        meta["last_user"] = json!(truncate_chars(user_text.trim(), 120));
    }
    if let Ok(text) = serde_json::to_string_pretty(&meta) {
        let _ = write_atomic(&meta_path(paths, &sid), &text);
    }
}

/// 自动归类的匹配面：对活跃项目的 name + aliases 做**大小写不敏感子串包含 +
/// 最长优先首命中**。语义与 `contract/intents.v1.json` 的 strong_match 同构。
/// **永不新建项目** —— 建档是人的动作。
fn match_project(reg: &Value, text: &str) -> Option<String> {
    let hay = text.to_lowercase();
    if hay.trim().is_empty() {
        return None;
    }
    let mut best: Option<(usize, String)> = None;
    for p in projects_of(reg) {
        if !is_active(&p) {
            continue;
        }
        let id = p.get("id").and_then(|v| v.as_str()).unwrap_or("").to_string();
        if id.is_empty() {
            continue;
        }
        let mut names = vec![p.get("name").and_then(|v| v.as_str()).unwrap_or("").to_string()];
        if let Some(a) = p.get("aliases").and_then(|v| v.as_array()) {
            names.extend(a.iter().filter_map(|x| x.as_str()).map(|s| s.to_string()));
        }
        for n in names {
            if n.is_empty() {
                continue;
            }
            if hay.contains(&n.to_lowercase()) {
                let len = n.chars().count();
                if best.as_ref().map(|(l, _)| len > *l).unwrap_or(true) {
                    best = Some((len, id.clone()));
                }
            }
        }
    }
    best.map(|(_, id)| id)
}

pub fn set_session_meta(paths: &Paths, session: &str, project_id: Option<&str>, title: Option<&str>) -> Result<Value, String> {
    let sid = safe_session_id(session)?;
    let _g = projects_lock().lock().map_err(|_| "lock".to_string())?;
    let reg = load_registry(paths);
    let mut meta = load_meta(paths, &sid).unwrap_or_else(|| {
        json!({
            "schema": "civil.session.meta.v1", "session_id": sid,
            "title": "", "title_source": "auto",
            "project_id": "", "project_source": "auto",
            "created_at": now_secs(), "turns": 0
        })
    });
    if let Some(p) = project_id {
        let pid = if p.is_empty() { INBOX_ID.to_string() } else { safe_project_id(p)? };
        meta["project_id"] = json!(resolve_pid(&reg, &pid));
        meta["project_source"] = json!("manual");
    }
    if let Some(t) = title {
        let t = t.trim();
        if t.is_empty() {
            return Err("标题不能为空".into());
        }
        meta["title"] = json!(truncate_chars(t, TITLE_MAX_CHARS));
        meta["title_source"] = json!("manual");
    }
    meta["updated_at"] = json!(now_secs());
    let text = serde_json::to_string_pretty(&meta).map_err(|e| e.to_string())?;
    write_atomic(&meta_path(paths, &sid), &text)?;
    Ok(meta)
}

// ---------------------------------------------------------------- 会话索引

#[derive(Clone)]
struct Row {
    sid: String,
    title: String,
    pid: String,
    updated: u64,
    turns: u64,
}

fn row_json(r: &Row) -> Value {
    json!({
        "session_id": r.sid, "title": r.title, "project_id": r.pid,
        "updated_at": r.updated, "turns": r.turns
    })
}

/// 分级扫描。**绝不打开 trace.json**：没有 meta 的目录降级为「目录名 + mtime」行。
fn scan_rows(paths: &Paths) -> Vec<Row> {
    let reg = load_registry(paths);
    let Ok(rd) = fs::read_dir(&paths.out_root) else {
        return Vec::new();
    };
    let mut rows: Vec<Row> = Vec::new();
    for ent in rd.flatten() {
        if !ent.file_type().map(|t| t.is_dir()).unwrap_or(false) {
            continue;
        }
        let name = ent.file_name().to_string_lossy().to_string();
        let Ok(sid) = safe_session_id(&name) else {
            continue; // `_index` / `_threads` 等非会话目录在此被挡掉
        };
        if sid != name {
            continue; // 名字被白名单改写过 = 不是合法会话目录
        }
        let dir = ent.path();
        match load_meta(paths, &sid) {
            Some(m) => rows.push(Row {
                title: {
                    let t = m.get("title").and_then(|v| v.as_str()).unwrap_or("").to_string();
                    if t.is_empty() { sid.clone() } else { t }
                },
                pid: resolve_pid(&reg, m.get("project_id").and_then(|v| v.as_str()).unwrap_or("")),
                updated: m.get("updated_at").and_then(|v| v.as_u64()).unwrap_or_else(|| mtime_secs(&dir)),
                turns: m.get("turns").and_then(|v| v.as_u64()).unwrap_or(0),
                sid,
            }),
            None => rows.push(Row {
                title: sid.clone(),
                pid: INBOX_ID.to_string(),
                updated: mtime_secs(&dir),
                turns: 0,
                sid,
            }),
        }
    }
    rows.sort_by(|a, b| b.updated.cmp(&a.updated));
    rows.truncate(index_max());
    rows
}

pub fn list_sessions(paths: &Paths, project_id: &str, q: &str, limit: usize, offset: usize) -> Value {
    let lim = limit.clamp(1, MAX_LIMIT);
    let rows = scan_rows(paths);
    let ql = q.trim().to_lowercase();
    let filtered: Vec<&Row> = rows
        .iter()
        .filter(|r| project_id.is_empty() || r.pid == project_id)
        .filter(|r| ql.is_empty() || r.title.to_lowercase().contains(&ql) || r.sid.to_lowercase().contains(&ql))
        .collect();
    let total = filtered.len();
    let page: Vec<Value> = filtered.iter().skip(offset).take(lim).map(|r| row_json(r)).collect();
    json!({
        "ok": true, "schema": SCHEMA_SESSIONS,
        "total": total, "limit": lim, "offset": offset,
        "sessions": page
    })
}

pub fn list_projects(paths: &Paths) -> Value {
    let reg = load_registry(paths);
    let rows = scan_rows(paths);
    let mut out: Vec<Value> = Vec::new();
    for p in projects_of(&reg) {
        if !is_active(&p) {
            continue;
        }
        let id = p.get("id").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let n = rows.iter().filter(|r| r.pid == id).count();
        out.push(json!({
            "id": id,
            "name": p.get("name").and_then(|v| v.as_str()).unwrap_or(""),
            "aliases": p.get("aliases").cloned().unwrap_or_else(|| json!([])),
            "n_sessions": n,
            "updated_at": p.get("updated_at").and_then(|v| v.as_u64()).unwrap_or(0),
            "archived": false
        }));
    }
    out.sort_by(|a, b| {
        b.get("updated_at").and_then(|v| v.as_u64()).unwrap_or(0)
            .cmp(&a.get("updated_at").and_then(|v| v.as_u64()).unwrap_or(0))
    });
    let inbox_n = rows.iter().filter(|r| r.pid == INBOX_ID).count();
    json!({
        "ok": true, "schema": SCHEMA_PROJECTS,
        "projects": out,
        "inbox": {"id": INBOX_ID, "name": INBOX_NAME, "n_sessions": inbox_n, "builtin": true}
    })
}

// ---------------------------------------------------------------- 对话正文

/// 追加一轮对话。服务端此前从不落盘正文（history 全由浏览器提供，刷新即丢），
/// 「点会话回到那次对话」没有免费方案，这是最小落盘面。
pub fn append_turn(paths: &Paths, session: &str, role: &str, text: &str) {
    let Ok(sid) = safe_session_id(session) else {
        return;
    };
    let mut t = text.to_string();
    if t.len() > TEXT_MAX_BYTES {
        // 按字符边界截断，避免切碎多字节
        t = t.chars().take(TEXT_MAX_BYTES / 3).collect();
    }
    let line = json!({"ts": now_secs(), "role": role, "text": t});
    let Ok(mut s) = serde_json::to_string(&line) else {
        return;
    };
    s.push('\n');
    let path = transcript_path(paths, &sid);
    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    use std::io::Write;
    if let Ok(mut f) = fs::OpenOptions::new().create(true).append(true).open(&path) {
        let _ = f.write_all(s.as_bytes());
    }
}

pub fn session_detail(paths: &Paths, session: &str) -> Result<Value, String> {
    let sid = safe_session_id(session)?;
    let reg = load_registry(paths);
    let meta = load_meta(paths, &sid);
    let dir = paths.out_root.join(&sid);
    let title = meta
        .as_ref()
        .and_then(|m| m.get("title").and_then(|v| v.as_str()))
        .filter(|s| !s.is_empty())
        .unwrap_or(&sid)
        .to_string();
    let pid = resolve_pid(
        &reg,
        meta.as_ref()
            .and_then(|m| m.get("project_id").and_then(|v| v.as_str()))
            .unwrap_or(""),
    );
    let mut turns: Vec<Value> = Vec::new();
    let mut truncated = false;
    if let Ok(raw) = fs::read_to_string(transcript_path(paths, &sid)) {
        let all: Vec<&str> = raw.lines().filter(|l| !l.trim().is_empty()).collect();
        if all.len() > TRANSCRIPT_TAIL {
            truncated = true;
        }
        for l in all.iter().rev().take(TRANSCRIPT_TAIL).rev() {
            if let Ok(v) = serde_json::from_str::<Value>(l) {
                turns.push(v);
            }
        }
    }
    Ok(json!({
        "ok": true, "schema": SCHEMA_SESSION_DETAIL,
        "session_id": sid, "title": title, "project_id": pid,
        "updated_at": meta.as_ref().and_then(|m| m.get("updated_at").and_then(|v| v.as_u64()))
            .unwrap_or_else(|| mtime_secs(&dir)),
        "turns": meta.as_ref().and_then(|m| m.get("turns").and_then(|v| v.as_u64())).unwrap_or(0),
        "transcript": turns,
        "truncated": truncated
    }))
}

pub fn default_limit() -> usize {
    DEFAULT_LIMIT
}
