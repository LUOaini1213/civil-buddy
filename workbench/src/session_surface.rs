//! Task memory and deliverable zip for the Rust host. Reads the session
//! transcript, upload text, and run records already on disk.

use crate::config::Paths;
use serde_json::{json, Value};
use std::fs;
use std::path::{Path, PathBuf};

pub fn memory_text(paths: &Paths, sid: &str) -> String {
    let mut lines = Vec::new();
    if let Ok(detail) = crate::projects::session_detail(paths, sid) {
        if let Some(turns) = detail.get("transcript").and_then(|v| v.as_array()) {
            for turn in turns {
                let role = turn.get("role").and_then(|v| v.as_str()).unwrap_or("user");
                let text = turn.get("text").and_then(|v| v.as_str()).unwrap_or("").trim();
                if text.is_empty() {
                    continue;
                }
                let who = if role == "assistant" { "助手" } else { "用户" };
                lines.push(format!("{who}：{text}"));
            }
        }
    }
    for file in crate::attach::list_uploads(paths, sid) {
        let id = file.get("id").and_then(|v| v.as_str()).unwrap_or("");
        let name = file.get("name").and_then(|v| v.as_str()).unwrap_or(id);
        if id.is_empty() {
            continue;
        }
        match crate::attach::read_upload(paths, sid, id, 0, 1500) {
            Ok(text) => lines.push(format!("附件 {name}：{text}")),
            Err(_) if !name.is_empty() => lines.push(format!("附件 {name}")),
            Err(_) => {}
        }
    }
    if lines.is_empty() {
        "尚无规则记忆，可发送消息或重新整理记忆。".into()
    } else {
        lines.join("\n")
    }
}

pub fn search_citations(paths: &Paths, sid: &str, query: &str) -> Vec<Value> {
    let query = query.trim();
    if query.is_empty() {
        return Vec::new();
    }
    let hay = memory_text(paths, sid);
    let lower_hay = hay.to_lowercase();
    let lower_q = query.to_lowercase();
    let Some(at) = lower_hay.find(&lower_q) else {
        return Vec::new();
    };
    let start = char_floor(&hay, at.saturating_sub(40));
    let end = char_ceil(&hay, (at + query.len() + 80).min(hay.len()));
    let snippet: String = hay[start..end].chars().take(240).collect();
    vec![json!({
        "title": "本会话原文",
        "display": "本会话原文",
        "snippet": snippet,
        "layer": "history",
        "path": format!("sessions/{sid}/transcript.jsonl"),
        "source_id": "history",
        "start": start,
        "end": end,
        "url": format!("/api/context/source?session_id={sid}&source_id=history"),
    })]
}

pub fn source_text(paths: &Paths, sid: &str, source_id: &str) -> String {
    if source_id.is_empty() || source_id == "history" {
        return memory_text(paths, sid);
    }
    crate::attach::read_upload(paths, sid, source_id, 0, 8000).unwrap_or_default()
}

fn char_floor(s: &str, byte: usize) -> usize {
    let mut i = byte.min(s.len());
    while i > 0 && !s.is_char_boundary(i) {
        i -= 1;
    }
    i
}

fn char_ceil(s: &str, byte: usize) -> usize {
    let mut i = byte.min(s.len());
    while i < s.len() && !s.is_char_boundary(i) {
        i += 1;
    }
    i
}

fn under_root(root: &Path, file: &Path) -> bool {
    let Ok(root) = root.canonicalize() else {
        return false;
    };
    let Ok(file) = file.canonicalize() else {
        return false;
    };
    file.is_file() && file.starts_with(root)
}

fn zip_name(raw: &str, used: &mut Vec<String>) -> String {
    let base = Path::new(raw)
        .file_name()
        .and_then(|s| s.to_str())
        .filter(|s| !s.is_empty() && !s.contains(".."))
        .unwrap_or("file.bin");
    let mut name = base.to_string();
    let mut n = 2;
    while used.iter().any(|s| s == &name) {
        name = format!("{n}-{base}");
        n += 1;
    }
    used.push(name.clone());
    name
}

fn push_files(root: &Path, run_filter: &str, record_run: &str, items: &Value, out: &mut Vec<(String, PathBuf)>, used: &mut Vec<String>) {
    if !run_filter.is_empty() && !record_run.is_empty() && record_run != run_filter {
        return;
    }
    let Some(arr) = items.as_array() else {
        return;
    };
    for item in arr {
        let Some(path) = item.get("path").and_then(|v| v.as_str()) else {
            continue;
        };
        let path = PathBuf::from(path);
        if !under_root(root, &path) {
            continue;
        }
        if out.iter().any(|(_, have)| have == &path) {
            continue;
        }
        let shown = item.get("name").and_then(|v| v.as_str()).unwrap_or("file.bin");
        out.push((zip_name(shown, used), path));
    }
}

pub fn deliverable_files(paths: &Paths, sid: &str, run_id: &str) -> Vec<(String, PathBuf)> {
    let root = &paths.out_root;
    let mut out = Vec::new();
    let mut used = Vec::new();
    let runs = root.join(sid).join("runs");
    let Ok(rd) = fs::read_dir(&runs) else {
        return out;
    };
    for ent in rd.flatten() {
        let dir = ent.path();
        if !dir.is_dir() {
            continue;
        }
        let dir_name = dir.file_name().and_then(|s| s.to_str()).unwrap_or("");
        for fname in ["workbench.json", "trace.json"] {
            let raw = fs::read_to_string(dir.join(fname)).unwrap_or_default();
            let Ok(value) = serde_json::from_str::<Value>(&raw) else {
                continue;
            };
            let record_run = value.get("run_id").and_then(|v| v.as_str()).unwrap_or(dir_name);
            if let Some(items) = value.get("deliverables") {
                push_files(root, run_id, record_run, items, &mut out, &mut used);
            }
            if let Some(items) = value.get("files") {
                push_files(root, run_id, record_run, items, &mut out, &mut used);
            }
        }
    }
    out
}

pub fn record_run(paths: &Paths, sid: &str, run_id: &str, files: &[Value]) {
    if files.is_empty() || crate::projects::safe_session_id(sid).is_err() {
        return;
    }
    let rid: String = run_id
        .chars()
        .filter(|c| c.is_ascii_alphanumeric() || *c == '-' || *c == '_')
        .take(64)
        .collect();
    if rid.is_empty() {
        return;
    }
    let dir = paths.out_root.join(sid).join("runs").join(&rid);
    if fs::create_dir_all(&dir).is_err() {
        return;
    }
    let payload = json!({
        "schema": "civil.workbench.run.v1",
        "run_id": rid,
        "deliverables": files,
    });
    let _ = fs::write(dir.join("workbench.json"), payload.to_string());
}
