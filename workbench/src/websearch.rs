//! Live web search + page fetch for summoned experts. Official portals only as evidence.

use regex::Regex;
use reqwest::Url;
use serde_json::{json, Value};
use std::io::Read as _;

const UA: &str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 CivilBuddy/0.1";

pub fn run_blocking<F, T>(f: F) -> T
where
    F: FnOnce() -> T,
{
    match tokio::runtime::Handle::try_current() {
        Ok(_) => tokio::task::block_in_place(f),
        Err(_) => f(),
    }
}

pub fn search(query: &str) -> String {
    let q = query.trim();
    if q.chars().count() < 2 {
        return "请提供检索词，例如：BCA CORENET X 2026 或 标准施工招标文件 56号令".into();
    }
    match search_ddg(q) {
        Ok(hits) if !hits.is_empty() => {
            let body = serde_json::to_string_pretty(&hits).unwrap_or_else(|_| "[]".into());
            format!(
                "网上检索（DuckDuckGo，非法定原文）。条款号没打开官网核对就标 unverified。优先点 .gov.sg / bca / mom / scdf / pub / lta / iras / gebiz / sso.agc / ndrc / mohurd。\n{body}"
            )
        }
        Ok(_) => format!("没有搜到结果。可把官方页 URL 交给 web_open，或收窄词：{q}"),
        Err(e) => format!("联网检索失败：{e}。把官方 URL 交给 web_open，或先读本岗 web-knowledge。"),
    }
}

pub fn open_url(url: &str) -> String {
    let url = url.trim();
    if let Err(e) = check_url(url) {
        return e;
    }
    match fetch_text(url) {
        Ok(text) => {
            let cut: String = text.chars().take(24_000).collect();
            format!(
                "【网页摘录 · 非正式全文 · 条款未核对标 unverified】\nURL: {url}\n\n{cut}"
            )
        }
        Err(e) => format!("打开失败：{e}"),
    }
}

fn search_ddg(query: &str) -> Result<Vec<Value>, String> {
    let client = client()?;
    let resp = client
        .post("https://html.duckduckgo.com/html/")
        .header("User-Agent", UA)
        .form(&[("q", query)])
        .send()
        .map_err(|e| e.to_string())?;
    if !resp.status().is_success() {
        return Err(format!("DuckDuckGo HTTP {}", resp.status()));
    }
    let html = resp.text().map_err(|e| e.to_string())?;
    Ok(parse_ddg(&html))
}

pub fn parse_ddg(html: &str) -> Vec<Value> {
    static RE: std::sync::LazyLock<Regex> = std::sync::LazyLock::new(|| {
        Regex::new(r#"(?is)<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>"#)
            .expect("ddg re")
    });
    let re = &*RE;
    let mut out = Vec::new();
    let mut seen = std::collections::HashSet::new();
    for cap in re.captures_iter(html) {
        let href = cap.get(1).map(|m| m.as_str()).unwrap_or("");
        let title = strip_tags(cap.get(2).map(|m| m.as_str()).unwrap_or(""));
        let url = decode_ddg_href(href);
        if url.is_empty() || !seen.insert(url.clone()) {
            continue;
        }
        if check_url(&url).is_err() {
            continue;
        }
        out.push(json!({
            "title": title.chars().take(140).collect::<String>(),
            "url": url,
        }));
        if out.len() >= 8 {
            break;
        }
    }
    out
}

fn decode_ddg_href(href: &str) -> String {
    if href.starts_with("http://") || href.starts_with("https://") {
        return href.to_string();
    }
    if let Some(idx) = href.find("uddg=") {
        let rest = &href[idx + 5..];
        let enc = rest.split('&').next().unwrap_or(rest);
        return urlencoding_decode(enc);
    }
    String::new()
}

fn urlencoding_decode(s: &str) -> String {
    let bytes = s.as_bytes();
    let mut out = Vec::new();
    let mut i = 0;
    // Work on bytes only: slicing `&s[i+1..i+3]` panicked when a multi-byte
    // character followed the '%' (non-char-boundary slice).
    let hex_val = |b: u8| -> Option<u8> {
        match b {
            b'0'..=b'9' => Some(b - b'0'),
            b'a'..=b'f' => Some(b - b'a' + 10),
            b'A'..=b'F' => Some(b - b'A' + 10),
            _ => None,
        }
    };
    while i < bytes.len() {
        if bytes[i] == b'%' && i + 2 < bytes.len() {
            if let (Some(h), Some(l)) = (hex_val(bytes[i + 1]), hex_val(bytes[i + 2])) {
                out.push(h * 16 + l);
                i += 3;
                continue;
            }
        }
        if bytes[i] == b'+' {
            out.push(b' ');
        } else {
            out.push(bytes[i]);
        }
        i += 1;
    }
    String::from_utf8_lossy(&out).into_owned()
}

fn strip_tags(s: &str) -> String {
    static RE: std::sync::LazyLock<Regex> =
        std::sync::LazyLock::new(|| Regex::new(r"<[^>]+>").expect("tag re"));
    collapse(RE.replace_all(s, "").as_ref())
}

fn collapse(s: &str) -> String {
    s.split_whitespace().collect::<Vec<_>>().join(" ")
}

fn fetch_text(url: &str) -> Result<String, String> {
    let client = client()?;
    let resp = client
        .get(url)
        .header("User-Agent", UA)
        .send()
        .map_err(|e| e.to_string())?;
    if !resp.status().is_success() {
        return Err(format!("HTTP {}", resp.status()));
    }
    let ctype = resp
        .headers()
        .get(reqwest::header::CONTENT_TYPE)
        .and_then(|v| v.to_str().ok())
        .unwrap_or("")
        .to_ascii_lowercase();
    if ctype.contains("pdf") {
        return Err("这是 PDF。请下载后点「上传文件」，不要用 web_open 直接拆 PDF。".into());
    }
    // Cap the body read: an arbitrary page must not be able to exhaust memory.
    const MAX_FETCH_BYTES: u64 = 8 * 1024 * 1024;
    let mut raw = Vec::new();
    std::io::Read::take(resp, MAX_FETCH_BYTES)
        .read_to_end(&mut raw)
        .map_err(|e| e.to_string())?;
    let html = String::from_utf8_lossy(&raw);
    Ok(html_to_text(&html))
}

pub fn html_to_text(html: &str) -> String {
    static DROP_RES: std::sync::LazyLock<Vec<Regex>> = std::sync::LazyLock::new(|| {
        ["script", "style", "noscript"]
            .iter()
            .map(|tag| Regex::new(&format!(r"(?is)<{tag}[^>]*>.*?</{tag}>")).expect("drop re"))
            .collect()
    });
    static TAG_RE: std::sync::LazyLock<Regex> =
        std::sync::LazyLock::new(|| Regex::new(r"(?is)<[^>]+>").expect("tag re"));
    let mut s = html.to_string();
    for re in DROP_RES.iter() {
        s = re.replace_all(&s, " ").into_owned();
    }
    let text = decode_xml_lite(&TAG_RE.replace_all(&s, " "));
    collapse(&text)
}

fn decode_xml_lite(s: &str) -> String {
    s.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&#39;", "'")
        .replace("&quot;", "\"")
}

fn client() -> Result<reqwest::blocking::Client, String> {
    reqwest::blocking::Client::builder()
        .timeout(std::time::Duration::from_secs(25))
        .redirect(reqwest::redirect::Policy::limited(4))
        .http1_only()
        .build()
        .map_err(|e| e.to_string())
}

pub fn check_url(url: &str) -> Result<(), String> {
    let parsed = Url::parse(url).map_err(|_| "URL 无效".to_string())?;
    if !matches!(parsed.scheme(), "http" | "https") {
        return Err("只允许 http/https".into());
    }
    let host = parsed.host_str().unwrap_or("").to_ascii_lowercase();
    if host.is_empty()
        || host == "localhost"
        || host.ends_with(".localhost")
        || host == "0.0.0.0"
        || host.starts_with("127.")
        || host.starts_with("10.")
        || host.starts_with("192.168.")
        || host.starts_with("169.254.")
        || host == "::1"
    {
        return Err("拒绝访问本机或内网地址".into());
    }
    if let Some(rest) = host.strip_prefix("172.") {
        if let Some((a, _)) = rest.split_once('.') {
            if let Ok(n) = a.parse::<u8>() {
                if (16..=31).contains(&n) {
                    return Err("拒绝访问本机或内网地址".into());
                }
            }
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn blocks_localhost() {
        assert!(check_url("http://127.0.0.1/x").is_err());
        assert!(check_url("https://www.bca.gov.sg/").is_ok());
    }

    #[test]
    fn percent_decode_survives_multibyte_neighbors() {
        // Used to panic: "%" followed by a multi-byte char sliced mid-boundary.
        assert_eq!(urlencoding_decode("%中文"), "%中文");
        assert_eq!(urlencoding_decode("%41%42+c"), "AB c");
        assert_eq!(urlencoding_decode("https%3A%2F%2Fbca.gov.sg"), "https://bca.gov.sg");
    }

    #[test]
    fn parses_ddg_anchor() {
        let html = r#"<a class="result__a" href="https://www.bca.gov.sg/corenet">CORENET X</a>"#;
        let hits = parse_ddg(html);
        assert_eq!(hits.len(), 1);
        assert_eq!(hits[0]["url"], "https://www.bca.gov.sg/corenet");
    }
}