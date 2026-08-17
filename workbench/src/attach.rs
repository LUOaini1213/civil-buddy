//! Session uploads: save bytes, extract text, let experts read them.

use crate::config::Paths;
use flate2::read::ZlibDecoder;
use regex::Regex;
use serde_json::{json, Value};
use std::fs;
use std::io::{Cursor, Read};
use std::path::{Path, PathBuf};
use uuid::Uuid;

pub const MAX_BYTES: usize = 20 * 1024 * 1024;
pub const MAX_TEXT_CHARS: usize = 200_000;
pub const MAX_FILES: usize = 12;
pub const INJECT_CHARS: usize = 60_000;

const ALLOWED_EXT: &[&str] = &["pdf", "docx", "txt", "md", "csv", "json", "log"];

pub fn session_dir(paths: &Paths, session: &str) -> Result<PathBuf, String> {
    let sid = sanitize_session(session)?;
    let dir = paths.data_dir.join("uploads").join(sid);
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    Ok(dir)
}

fn sanitize_session(session: &str) -> Result<String, String> {
    let s: String = session
        .chars()
        .filter(|c| c.is_ascii_alphanumeric() || *c == '-' || *c == '_')
        .take(32)
        .collect();
    if s.len() < 4 {
        return Err("session_id 无效".into());
    }
    Ok(s)
}

fn ext_of(name: &str) -> String {
    Path::new(name)
        .extension()
        .and_then(|s| s.to_str())
        .unwrap_or("")
        .to_ascii_lowercase()
}

pub fn safe_filename(name: &str) -> String {
    let raw = Path::new(name)
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or("upload.bin");
    let cleaned: String = raw
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || matches!(c, '.' | '-' | '_' | '（' | '）') || ('\u{4e00}'..='\u{9fff}').contains(&c)
            {
                c
            } else {
                '_'
            }
        })
        .collect();
    if cleaned.is_empty() {
        "upload.bin".into()
    } else {
        cleaned.chars().take(80).collect()
    }
}

pub fn extract_text(filename: &str, bytes: &[u8]) -> Result<(String, String), String> {
    let (kind, text, _) = extract_upload(filename, bytes)?;
    Ok((kind, text))
}

pub fn extract_upload(filename: &str, bytes: &[u8]) -> Result<(String, String, String), String> {
    if bytes.len() > MAX_BYTES {
        return Err(format!("单文件不能超过 {} MB", MAX_BYTES / 1024 / 1024));
    }
    let ext = ext_of(filename);
    if !ALLOWED_EXT.contains(&ext.as_str()) {
        return Err("只接受 pdf / docx / txt / md / csv / json".into());
    }
    let builtin = match ext.as_str() {
        "pdf" => extract_pdf(bytes),
        "docx" => extract_docx(bytes),
        _ => Ok(String::from_utf8_lossy(bytes).into_owned()),
    };
    let got = crate::parse::extract_rich(filename, &ext, bytes, builtin)?;
    let text = collapse_ws(&got.text);
    if text.chars().count() < 8 {
        return Err("抽不出可用文字。扫描件 PDF 需要先 OCR（安装 MinerU 或另存为 Word/文本）。".into());
    }
    let cut: String = text.chars().take(MAX_TEXT_CHARS).collect();
    Ok((ext, cut, got.engine))
}

fn collapse_ws(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut prev_nl = false;
    for line in s.lines() {
        let t = line.trim();
        if t.is_empty() {
            if !prev_nl && !out.is_empty() {
                out.push('\n');
                prev_nl = true;
            }
            continue;
        }
        out.push_str(t);
        out.push('\n');
        prev_nl = false;
    }
    out
}

fn extract_docx(bytes: &[u8]) -> Result<String, String> {
    let mut zip = zip::ZipArchive::new(Cursor::new(bytes)).map_err(|e| format!("docx 不是有效压缩包：{e}"))?;
    let mut file = zip
        .by_name("word/document.xml")
        .map_err(|_| "docx 缺少 word/document.xml".to_string())?;
    let mut xml = String::new();
    file.read_to_string(&mut xml).map_err(|e| e.to_string())?;
    let re = Regex::new(r"<w:t[^>]*>([^<]*)</w:t>").unwrap();
    let mut out = String::new();
    for cap in re.captures_iter(&xml) {
        if let Some(t) = cap.get(1) {
            let piece = decode_xml(t.as_str());
            if !piece.is_empty() {
                if !out.is_empty() {
                    out.push(' ');
                }
                out.push_str(&piece);
            }
        }
    }
    Ok(out)
}

fn decode_xml(s: &str) -> String {
    s.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", "\"")
        .replace("&apos;", "'")
}

fn extract_pdf(bytes: &[u8]) -> Result<String, String> {
    let raw = String::from_utf8_lossy(bytes);
    let mut chunks = Vec::new();
    // uncompressed operators in the file body
    collect_pdf_strings(&raw, &mut chunks);
    // flate streams
    let data = bytes;
    let marker = b"stream";
    let end_marker = b"endstream";
    let mut i = 0;
    while i + marker.len() < data.len() {
        if let Some(rel) = find_sub(data, marker, i) {
            let mut start = rel + marker.len();
            if start < data.len() && data[start] == b'\r' {
                start += 1;
            }
            if start < data.len() && data[start] == b'\n' {
                start += 1;
            }
            if let Some(end) = find_sub(data, end_marker, start) {
                let slice = &data[start..end];
                if let Ok(plain) = inflate(slice) {
                    collect_pdf_strings(&plain, &mut chunks);
                }
                i = end + end_marker.len();
                continue;
            }
        }
        break;
    }
    let text = chunks.join(" ");
    if text.trim().is_empty() {
        return Err("这个 PDF 没有可抽取的文字层".into());
    }
    Ok(text)
}

fn inflate(slice: &[u8]) -> Result<String, ()> {
    let mut dec = ZlibDecoder::new(slice);
    let mut buf = Vec::new();
    dec.read_to_end(&mut buf).map_err(|_| ())?;
    Ok(String::from_utf8_lossy(&buf).into_owned())
}

fn find_sub(hay: &[u8], needle: &[u8], from: usize) -> Option<usize> {
    hay[from..]
        .windows(needle.len())
        .position(|w| w == needle)
        .map(|p| from + p)
}

fn collect_pdf_strings(src: &str, out: &mut Vec<String>) {
    let mut chars = src.chars().peekable();
    while let Some(c) = chars.next() {
        if c == '(' {
            let mut buf = String::new();
            let mut depth = 1;
            while let Some(ch) = chars.next() {
                if ch == '\\' {
                    if let Some(n) = chars.next() {
                        buf.push(match n {
                            'n' => '\n',
                            'r' => '\n',
                            't' => '\t',
                            _ => n,
                        });
                    }
                    continue;
                }
                if ch == '(' {
                    depth += 1;
                    buf.push(ch);
                    continue;
                }
                if ch == ')' {
                    depth -= 1;
                    if depth == 0 {
                        break;
                    }
                    buf.push(ch);
                    continue;
                }
                buf.push(ch);
            }
            let t = buf.trim();
            if t.chars().count() >= 2 {
                out.push(t.to_string());
            }
        }
    }
}

pub fn save_upload(paths: &Paths, session: &str, filename: &str, bytes: &[u8]) -> Result<Value, String> {
    let dir = session_dir(paths, session)?;
    let existing = list_uploads(paths, session);
    if existing.len() >= MAX_FILES {
        return Err(format!("同一会话最多 {MAX_FILES} 个附件"));
    }
    let (kind, text, engine) = extract_upload(filename, bytes)?;
    let id = Uuid::new_v4().simple().to_string()[..12].to_string();
    let name = safe_filename(filename);
    fs::write(dir.join(format!("{id}.bin")), bytes).map_err(|e| e.to_string())?;
    fs::write(dir.join(format!("{id}.txt")), &text).map_err(|e| e.to_string())?;
    let meta = json!({
        "id": id,
        "name": name,
        "kind": kind,
        "bytes": bytes.len(),
        "chars": text.chars().count(),
        "parse": engine,
    });
    fs::write(dir.join(format!("{id}.json")), meta.to_string()).map_err(|e| e.to_string())?;
    Ok(meta)
}

pub fn list_uploads(paths: &Paths, session: &str) -> Vec<Value> {
    let Ok(dir) = session_dir(paths, session) else {
        return vec![];
    };
    let Ok(rd) = fs::read_dir(&dir) else {
        return vec![];
    };
    let mut out = Vec::new();
    for ent in rd.flatten() {
        let p = ent.path();
        if p.extension().and_then(|s| s.to_str()) != Some("json") {
            continue;
        }
        if let Ok(raw) = fs::read_to_string(&p) {
            if let Ok(v) = serde_json::from_str::<Value>(&raw) {
                out.push(v);
            }
        }
    }
    out.sort_by(|a, b| a["name"].as_str().cmp(&b["name"].as_str()));
    out
}

pub fn read_upload(paths: &Paths, session: &str, id: &str, offset: usize, limit: usize) -> Result<String, String> {
    let sid = id
        .chars()
        .filter(|c| c.is_ascii_alphanumeric())
        .take(16)
        .collect::<String>();
    if sid.is_empty() {
        return Err("附件 id 无效".into());
    }
    let dir = session_dir(paths, session)?;
    let text = fs::read_to_string(dir.join(format!("{sid}.txt"))).map_err(|_| "附件不存在".to_string())?;
    let take = if limit == 0 { 8000 } else { limit.min(20_000) };
    let skipped: String = text.chars().skip(offset).take(take).collect();
    let more = text.chars().count().saturating_sub(offset + skipped.chars().count());
    let meta = fs::read_to_string(dir.join(format!("{sid}.json"))).unwrap_or_default();
    let name = serde_json::from_str::<Value>(&meta)
        .ok()
        .and_then(|v| v.get("name").and_then(|x| x.as_str()).map(|s| s.to_string()))
        .unwrap_or_else(|| sid.clone());
    Ok(format!(
        "【用户上传：{name}】offset={offset} 本段{}字 剩余约{more}字\n\n{skipped}",
        skipped.chars().count()
    ))
}

pub fn import_local(paths: &Paths, session: &str, raw: &str) -> Result<Vec<Value>, String> {
    let target = allow_local_path(paths, raw)?;
    if target.is_dir() {
        let mut files: Vec<PathBuf> = fs::read_dir(&target)
            .map_err(|e| e.to_string())?
            .flatten()
            .map(|e| e.path())
            .filter(|p| p.is_file() && ALLOWED_EXT.contains(&ext_of(&p.to_string_lossy()).as_str()))
            .collect();
        files.sort();
        files.truncate(8);
        if files.is_empty() {
            return Err("这个文件夹里没有可抽文字的 pdf/docx/txt/md/csv".into());
        }
        let mut out = Vec::new();
        for f in files {
            let name = f
                .file_name()
                .and_then(|s| s.to_str())
                .unwrap_or("file");
            let bytes = fs::read(&f).map_err(|e| format!("{}: {e}", f.display()))?;
            out.push(save_upload(paths, session, name, &bytes)?);
        }
        return Ok(out);
    }
    if !target.is_file() {
        return Err("路径不是文件或文件夹".into());
    }
    let name = target
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or("file");
    let bytes = fs::read(&target).map_err(|e| e.to_string())?;
    Ok(vec![save_upload(paths, session, name, &bytes)?])
}

pub fn allow_local_path(_paths: &Paths, raw: &str) -> Result<PathBuf, String> {
    let trimmed = raw.trim().trim_matches('"').trim();
    if trimmed.is_empty() {
        return Err("请给出本机完整路径，例如桌面上的招标文件。禁止把 D:\\layout 当缺省作业根。".into());
    }
    let p = PathBuf::from(trimmed);
    let canon = if p.exists() {
        p.canonicalize().unwrap_or(p)
    } else {
        return Err(format!("找不到文件：{trimmed}"));
    };
    let display = canon.to_string_lossy();
    let lower = display.to_ascii_lowercase().replace('/', "\\");
    if lower.contains("d:\\layout") {
        return Err("禁止把 D:\\layout 当作业根。请改成本项目招标文件的完整路径。".into());
    }
    if lower.contains("\\windows\\")
        || lower.contains("\\program files")
        || lower.contains("\\$recycle.bin")
    {
        return Err("拒绝读取系统目录".into());
    }
    Ok(canon)
}

pub fn bundle_for_prompt(paths: &Paths, session: &str, ids: &[String], user_msg: &str) -> String {
    if ids.is_empty() {
        return user_msg.to_string();
    }
    let mut parts = Vec::new();
    let mut used = 0usize;
    for id in ids {
        match read_upload(paths, session, id, 0, 20_000) {
            Ok(t) => {
                let room = INJECT_CHARS.saturating_sub(used);
                if room < 80 {
                    parts.push(format!("（还有附件 {id} 未贴全文，请用 read_attachment）"));
                    continue;
                }
                let cut: String = t.chars().take(room).collect();
                used += cut.chars().count();
                parts.push(cut);
            }
            Err(e) => parts.push(format!("附件 {id}：{e}")),
        }
    }
    format!(
        "{}\n\n---\n用户说：\n{}",
        parts.join("\n\n"),
        user_msg
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn extracts_plain_text() {
        let (kind, text) = extract_text("招标.txt", "评分点 技术标 40 分\n必须编制临边专项".as_bytes()).unwrap();
        assert_eq!(kind, "txt");
        assert!(text.contains("技术标"));
    }

    #[test]
    fn rejects_exe() {
        assert!(extract_text("x.exe", b"MZ").is_err());
    }
}