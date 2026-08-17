use crate::config::Paths;
use regex::Regex;
use serde::Serialize;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::OnceLock;

pub const MAX_FILE_BYTES: usize = 512 * 1024;
pub const ALLOWED_SUFFIX: &[&str] = &[".md", ".txt"];

fn id_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"^[a-z][a-z0-9-]{1,31}$").unwrap())
}

fn file_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(r"^[A-Za-z0-9_\u{4e00}-\u{9fff}][A-Za-z0-9_\u{4e00}-\u{9fff}.\-]{0,80}$")
            .unwrap()
    })
}

pub fn ensure_kb_root(paths: &Paths) {
    let _ = fs::create_dir_all(&paths.kb_root);
    let company = paths.kb_root.join("company");
    let _ = fs::create_dir_all(&company);
    let dest = company.join("hard-rules.md");
    if !dest.exists() && paths.skill_hard_rules.is_file() {
        if let Ok(text) = fs::read_to_string(&paths.skill_hard_rules) {
            let _ = fs::write(dest, text);
        }
    }
}

pub fn valid_id(value: &str) -> bool {
    id_re().is_match(value) && !matches!(value, "company" | "static" | "api" | "_shared")
}

pub fn valid_filename(name: &str) -> bool {
    let name = Path::new(name)
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or("");
    if !file_re().is_match(name) {
        return false;
    }
    suffix_ok(name)
}

fn suffix_ok(name: &str) -> bool {
    Path::new(name)
        .extension()
        .and_then(|s| s.to_str())
        .map(|ext| matches!(ext.to_ascii_lowercase().as_str(), "md" | "txt"))
        .unwrap_or(false)
}

pub fn resolve_rel(paths: &Paths, rel: &str) -> Option<PathBuf> {
    let rel = rel.replace('\\', "/");
    let rel = rel.trim_start_matches('/');
    if rel.is_empty() {
        return None;
    }
    let parts: Vec<&str> = rel.split('/').collect();
    if parts.iter().any(|p| *p == ".." || *p == "." || p.is_empty()) {
        return None;
    }
    let target = paths.kb_root.join(rel.replace('/', std::path::MAIN_SEPARATOR_STR));
    let target = target.canonicalize().ok().or_else(|| {
        // parent may exist for a not-yet-created file
        let parent = target.parent()?;
        if parent.exists() {
            Some(target)
        } else if !target.exists() {
            // allow create if the first existing ancestor stays under kb_root
            Some(target)
        } else {
            None
        }
    })?;
    let kb = paths.kb_root.canonicalize().ok()?;
    if target.exists() {
        target.strip_prefix(&kb).ok()?;
        Some(target)
    } else {
        let mut walk = target.as_path();
        while !walk.exists() {
            walk = walk.parent()?;
        }
        let walk = walk.canonicalize().ok()?;
        walk.strip_prefix(&kb).ok()?;
        Some(target)
    }
}

pub fn iter_text_files(root: &Path) -> Vec<PathBuf> {
    if !root.is_dir() {
        return vec![];
    }
    let mut out = Vec::new();
    fn walk(dir: &Path, out: &mut Vec<PathBuf>) {
        let Ok(rd) = fs::read_dir(dir) else { return };
        for ent in rd.flatten() {
            let p = ent.path();
            if p.is_dir() {
                walk(&p, out);
            } else if p.is_file() {
                let ok = p
                    .extension()
                    .and_then(|s| s.to_str())
                    .map(|e| matches!(e.to_ascii_lowercase().as_str(), "md" | "txt"))
                    .unwrap_or(false);
                if ok {
                    out.push(p);
                }
            }
        }
    }
    walk(root, &mut out);
    out.sort();
    out
}

pub fn layer_label(layer: &str) -> &'static str {
    match layer {
        "expert" => "本岗知识",
        "category" => "大类共享",
        _ => "公司规则",
    }
}

pub fn known_kb_title(filename: &str) -> Option<&'static str> {
    let key = Path::new(filename)
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or(filename)
        .to_ascii_lowercase();
    Some(match key.as_str() {
        "web-knowledge.md" => "联网核对要点",
        "web-portals.md" => "官方门户与现行口径",
        "faq.md" => "常见问答",
        "outline.md" => "成稿大纲",
        "readme.md" => "本库说明",
        "hard-rules.md" => "硬规则",
        "hard-rules-short.md" => "硬规则（摘要）",
        "disclaimer.md" => "免责声明",
        "ask-anyone.md" => "谁都可以问",
        "ask-from-others.md" => "跨岗怎么问",
        "parse-checklist.md" => "招标摘录清单",
        "reject-traps.md" => "废标与否决雷区",
        "tender-workflow.md" => "投标工序",
        "scheme-11.md" => "专项方案十一章",
        "judge-card.md" => "危大判定卡",
        "hazard-triggers.md" => "危大触发",
        "order-37-points.md" => "37号令要点（仅中国）",
        "calc-outline.md" => "计算书提纲",
        "principles.md" => "设计原则",
        "discipline-split.md" => "专业拆分",
        "jurisdiction-codes.md" => "辖区规范族",
        "model-rules.md" => "模型规则",
        "plan-levels.md" => "计划层级",
        "brief-rules.md" => "交底口径",
        "tech-brief.md" => "技术交底骨架",
        "no-fake-price.md" => "禁止编造单价",
        "no-price.md" => "采购不编价格",
        "takeoff.md" => "工程量拆分口径",
        "lab-rules.md" => "试验室纪律",
        "finance-rules.md" => "财务口径",
        "legal-tone.md" => "劳动人事用语",
        "no-secrets.md" => "不写密钥",
        "plant-rules.md" => "物机纪律",
        "seal.md" => "用印",
        "closing.md" => "资料闭合",
        "archive.md" => "归档目录",
        "script.md" => "工友口播稿骨架",
        "worker-tone.md" => "工友白话语气",
        "experiment.md" => "交通试验口径",
        _ => return None,
    })
}

pub fn first_heading(text: &str) -> Option<String> {
    for line in text.lines().take(12) {
        let t = line.trim();
        if t.starts_with("##") {
            continue;
        }
        let Some(rest) = t.strip_prefix("# ").or_else(|| t.strip_prefix('#')) else {
            continue;
        };
        let s = rest.trim();
        if !s.is_empty() && s.chars().count() <= 48 {
            return Some(s.to_string());
        }
    }
    None
}

pub fn display_title(filename: &str, text: &str) -> String {
    if let Some(t) = known_kb_title(filename) {
        return t.to_string();
    }
    if let Some(h) = first_heading(text) {
        return h;
    }
    Path::new(filename)
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or(filename)
        .to_string()
}

#[derive(Debug, Clone, Serialize)]
pub struct FileStat {
    pub path: String,
    pub title: String,
    pub display: String,
    pub layer: String,
    pub layer_label: String,
    pub bytes: u64,
    pub chars: usize,
    pub lines: usize,
}

pub fn file_stat(path: &Path, rel: &str, layer: &str) -> FileStat {
    let raw = fs::read(path).unwrap_or_default();
    let text = String::from_utf8_lossy(&raw);
    let lines = if text.is_empty() {
        0
    } else {
        text.matches('\n').count() + usize::from(!text.ends_with('\n'))
    };
    let name = path
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or("");
    FileStat {
        path: rel.replace('\\', "/"),
        title: path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("")
            .to_string(),
        display: display_title(name, &text),
        layer: layer.to_string(),
        layer_label: layer_label(layer).to_string(),
        bytes: raw.len() as u64,
        chars: text.chars().count(),
        lines,
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct FolderStats {
    pub bytes: u64,
    pub files: Vec<FileStat>,
    pub count: usize,
}

pub fn folder_stats(paths: &Paths, root: &Path, _prefix: &str, layer: &str) -> FolderStats {
    let mut files = Vec::new();
    let mut total = 0u64;
    let kb = paths.kb_root.canonicalize().unwrap_or_else(|_| paths.kb_root.clone());
    for path in iter_text_files(root) {
        let rel = path
            .strip_prefix(&kb)
            .or_else(|_| path.strip_prefix(&paths.kb_root))
            .map(|p| p.to_string_lossy().replace('\\', "/"))
            .unwrap_or_else(|_| path.to_string_lossy().replace('\\', "/"));
        let st = file_stat(&path, &rel, layer);
        total += st.bytes;
        files.push(st);
    }
    FolderStats {
        count: files.len(),
        bytes: total,
        files,
    }
}

pub fn read_text(paths: &Paths, rel: &str) -> Option<(String, FileStat)> {
    let path = resolve_rel(paths, rel)?;
    if !path.is_file() {
        return None;
    }
    if !suffix_ok(path.to_string_lossy().as_ref()) {
        return None;
    }
    let text = fs::read_to_string(&path).ok()?;
    let st = file_stat(&path, &rel.replace('\\', "/"), "");
    Some((text, st))
}

pub fn write_text(paths: &Paths, rel: &str, content: &str) -> Result<FileStat, String> {
    if content.len() > MAX_FILE_BYTES {
        return Err(format!("单文件不能超过 {MAX_FILE_BYTES} 字节"));
    }
    let path = resolve_rel(paths, rel).ok_or_else(|| "非法路径".to_string())?;
    if !suffix_ok(&path.to_string_lossy()) {
        return Err("只允许 .md / .txt".into());
    }
    let name = path
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or("");
    if !valid_filename(name) {
        return Err("文件名只能用中文、字母、数字、_ -".into());
    }
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    fs::write(&path, content).map_err(|e| e.to_string())?;
    let rel = path
        .strip_prefix(paths.kb_root.canonicalize().unwrap_or_else(|_| paths.kb_root.clone()))
        .or_else(|_| path.strip_prefix(&paths.kb_root))
        .map(|p| p.to_string_lossy().replace('\\', "/"))
        .unwrap_or_else(|_| rel.replace('\\', "/"));
    Ok(file_stat(&path, &rel, ""))
}

pub fn create_file(paths: &Paths, rel: &str) -> Result<FileStat, String> {
    let path = resolve_rel(paths, rel).ok_or_else(|| "非法路径".to_string())?;
    if path.exists() {
        return Err("文件已存在".into());
    }
    let stem = path
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("note");
    write_text(paths, rel, &format!("# {stem}\n\n"))
}

pub fn delete_file(paths: &Paths, rel: &str) -> Result<(), String> {
    let path = resolve_rel(paths, rel).ok_or_else(|| "文件不存在".to_string())?;
    if !path.is_file() {
        return Err("文件不存在".into());
    }
    fs::remove_file(path).map_err(|e| e.to_string())
}

pub fn ensure_expert_kb(paths: &Paths, category: &str, expert_id: &str, name: &str) {
    let shared = paths.kb_root.join(category).join("_shared");
    let _ = fs::create_dir_all(&shared);
    let marker = shared.join("README.md");
    if !marker.exists() {
        let _ = fs::write(
            marker,
            format!("# {category} 大类共享库\n\n本大类专家都能检索到这里的文件。\n"),
        );
    }
    let private = paths.kb_root.join(category).join(expert_id);
    let _ = fs::create_dir_all(&private);
    let readme = private.join("README.md");
    if !readme.exists() {
        let _ = fs::write(
            readme,
            format!("# {name} 私库\n\n只有本专家默认优先检索。同类专家不读这里。\n"),
        );
    }
}

pub fn remove_expert_kb(paths: &Paths, category: &str, expert_id: &str) {
    let private = paths.kb_root.join(category).join(expert_id);
    if private.is_dir() {
        let _ = fs::remove_dir_all(private);
    }
}

pub fn format_bytes(n: u64) -> String {
    if n < 1024 {
        format!("{n} B")
    } else if n < 1024 * 1024 {
        format!("{:.1} KB", n as f64 / 1024.0)
            .trim()
            .to_string()
    } else {
        format!("{:.2} MB", n as f64 / (1024.0 * 1024.0))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn known_files_use_zh_names() {
        assert_eq!(known_kb_title("web-knowledge.md"), Some("联网核对要点"));
        assert_eq!(known_kb_title("README.md"), Some("本库说明"));
        assert_eq!(
            display_title("web-knowledge.md", "# ignored heading\n"),
            "联网核对要点"
        );
        assert_eq!(
            display_title("notes.md", "# 现场取样口令\n正文"),
            "现场取样口令"
        );
        assert_eq!(display_title("notes.md", "no heading"), "notes");
        assert_eq!(layer_label("expert"), "本岗知识");
        assert_eq!(layer_label("category"), "大类共享");
        assert_eq!(layer_label("company"), "公司规则");
    }
}
