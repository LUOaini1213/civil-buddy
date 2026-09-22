//! Live web search + page fetch for summoned experts. Official portals only as evidence.

use regex::Regex;
use reqwest::Url;
use serde_json::{json, Value};

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
    let re = Regex::new(r#"(?is)<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>"#)
        .unwrap();
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
    while i < bytes.len() {
        if bytes[i] == b'%' && i + 2 < bytes.len() {
            let hex = &s[i + 1..i + 3];
            if let Ok(v) = u8::from_str_radix(hex, 16) {
                out.push(v);
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
    let re = Regex::new(r"<[^>]+>").unwrap();
    collapse(re.replace_all(s, "").as_ref())
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
    let html = resp.text().map_err(|e| e.to_string())?;
    Ok(html_to_text(&html))
}

pub fn html_to_text(html: &str) -> String {
    let mut s = html.to_string();
    for tag in ["script", "style", "noscript"] {
        let re = Regex::new(&format!(r"(?is)<{tag}[^>]*>.*?</{tag}>")).unwrap();
        s = re.replace_all(&s, " ").into_owned();
    }
    let re = Regex::new(r"(?is)<[^>]+>").unwrap();
    let text = decode_xml_lite(&re.replace_all(&s, " "));
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

/// Largest document taken from the web; the same cap an uploaded file has (attach::MAX_BYTES).
pub const MAX_DOCUMENT_BYTES: u64 = 20 * 1024 * 1024;

/// An address a fetch may go to: not this machine, not the local network, not a link-local or multicast range.
/// `check_url` looks at what the URL SAYS; a name that resolves to 10.0.0.5 says nothing of the kind.
pub fn public_ip(ip: &std::net::IpAddr) -> bool {
    match ip {
        std::net::IpAddr::V4(v4) => {
            let o = v4.octets();
            !(v4.is_loopback() || v4.is_private() || v4.is_link_local() || v4.is_unspecified() || v4.is_broadcast()
                || v4.is_multicast() || o[0] == 0 || (o[0] == 100 && (64..=127).contains(&o[1])) || (o[0] == 198 && (o[1] == 18 || o[1] == 19)))
        }
        std::net::IpAddr::V6(v6) => {
            if let Some(v4) = v6.to_ipv4_mapped() {
                return public_ip(&std::net::IpAddr::V4(v4));
            }
            let s = v6.segments();
            !(v6.is_loopback() || v6.is_unspecified() || v6.is_multicast() || (s[0] & 0xfe00) == 0xfc00 || (s[0] & 0xffc0) == 0xfe80)
        }
    }
}

/// `check_url`, and every address the host resolves to is a public one.
pub fn check_public(url: &str) -> Result<(), String> {
    check_url(url)?;
    let parsed = Url::parse(url).map_err(|_| "URL 无效".to_string())?;
    let host = parsed.host_str().unwrap_or("").to_string();
    let port = parsed.port_or_known_default().unwrap_or(443);
    let addrs: Vec<std::net::SocketAddr> = std::net::ToSocketAddrs::to_socket_addrs(&(host.as_str(), port))
        .map_err(|_| "域名解析失败".to_string())?
        .collect();
    if addrs.is_empty() || addrs.iter().any(|a| !public_ip(&a.ip())) {
        return Err("拒绝访问本机或内网地址".into());
    }
    Ok(())
}

/// The file name a fetched document goes by: what the server calls it, else the last segment of the URL, with the
/// extension its content type stands for when it has none.
pub fn document_name(url: &str, disposition: &str, content_type: &str) -> String {
    let from_header = Regex::new(r#"(?i)filename\*?=(?:UTF-8''|")?([^";]+)"#)
        .ok()
        .and_then(|re| re.captures(disposition).map(|c| urlencoding_decode(c[1].trim())));
    let from_url = Url::parse(url)
        .ok()
        .and_then(|u| u.path_segments().and_then(|s| s.last().map(|x| urlencoding_decode(x))))
        .unwrap_or_default();
    let mut name = from_header.filter(|n| !n.trim().is_empty()).unwrap_or(from_url);
    name = name.rsplit(['/', '\\']).next().unwrap_or("").trim().to_string();
    let known = ["pdf", "docx", "xlsx", "txt", "md", "csv", "json", "log"];
    let has_ext = name.rsplit_once('.').map(|(_, e)| known.contains(&e.to_ascii_lowercase().as_str())).unwrap_or(false);
    if !has_ext {
        let ct = content_type.to_ascii_lowercase();
        let ext = if ct.contains("pdf") {
            "pdf"
        } else if ct.contains("wordprocessingml") {
            "docx"
        } else if ct.contains("spreadsheetml") {
            "xlsx"
        } else {
            "txt" // a page: its text is what is kept
        };
        let stem = if name.is_empty() { "网页".to_string() } else { name.rsplit_once('.').map(|(s, _)| s.to_string()).unwrap_or(name) };
        name = format!("{stem}.{ext}");
    }
    name
}

/// A document from the web as (file name, bytes): public addresses only - also after every redirect -, http(s) only,
/// no more than MAX_DOCUMENT_BYTES, nothing executed. A web PAGE comes back as its text (招标公告 are pages).
pub fn fetch_document(url: &str) -> Result<(String, Vec<u8>), String> {
    check_public(url)?;
    let client = reqwest::blocking::Client::builder()
        .timeout(std::time::Duration::from_secs(60))
        .redirect(reqwest::redirect::Policy::custom(|attempt| {
            if attempt.previous().len() >= 4 {
                return attempt.error("重定向太多");
            }
            match check_public(attempt.url().as_str()) {
                Ok(()) => attempt.follow(),
                Err(e) => attempt.error(e),
            }
        }))
        .http1_only()
        .build()
        .map_err(|e| e.to_string())?;
    let res = client.get(url).header("User-Agent", UA).send().map_err(|e| format!("取不到：{e}"))?;
    if !res.status().is_success() {
        return Err(format!("对方返回 {}", res.status().as_u16()));
    }
    if res.content_length().map(|n| n > MAX_DOCUMENT_BYTES).unwrap_or(false) {
        return Err("文件超过 20 MB".into());
    }
    let header = |name: &str| res.headers().get(name).and_then(|v| v.to_str().ok()).unwrap_or("").to_string();
    let (disposition, content_type) = (header("content-disposition"), header("content-type"));
    let name = document_name(res.url().as_str(), &disposition, &content_type);
    let mut bytes = Vec::new();
    std::io::Read::read_to_end(&mut std::io::Read::take(res, MAX_DOCUMENT_BYTES + 1), &mut bytes).map_err(|e| format!("读取中断：{e}"))?;
    if bytes.len() as u64 > MAX_DOCUMENT_BYTES {
        return Err("文件超过 20 MB".into());
    }
    if name.ends_with(".txt") && content_type.to_ascii_lowercase().contains("html") {
        let text = html_to_text(&String::from_utf8_lossy(&bytes));
        return Ok((name, text.into_bytes()));
    }
    Ok((name, bytes))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_name_that_resolves_inward_is_refused() {
        assert!(!public_ip(&"10.1.2.3".parse().unwrap()));
        assert!(!public_ip(&"100.64.0.1".parse().unwrap()));
        assert!(!public_ip(&"169.254.169.254".parse().unwrap()));
        assert!(!public_ip(&"::1".parse().unwrap()));
        assert!(!public_ip(&"fd00::1".parse().unwrap()));
        assert!(!public_ip(&"::ffff:192.168.1.1".parse().unwrap()));
        assert!(public_ip(&"1.1.1.1".parse().unwrap()));
        assert!(check_public("http://localhost/招标文件.pdf").is_err());
        assert!(check_public("ftp://example.org/a.pdf").is_err());
    }

    #[test]
    fn a_fetched_document_is_named_by_the_server_then_the_url_then_its_type() {
        assert_eq!(document_name("https://x.example/a/b/P0202.pdf", "", "application/pdf"), "P0202.pdf");
        assert_eq!(document_name("https://x.example/download?id=7", "attachment; filename=\"招标文件.docx\"", ""), "招标文件.docx");
        assert_eq!(document_name("https://x.example/d", "attachment; filename*=UTF-8''%E6%8B%9B%E6%A0%87.pdf", ""), "招标.pdf");
        assert_eq!(document_name("https://x.example/notice/123", "", "text/html; charset=utf-8"), "123.txt");
        assert_eq!(document_name("https://x.example/get", "", "application/pdf"), "get.pdf");
    }

    #[test]
    fn blocks_localhost() {
        assert!(check_url("http://127.0.0.1/x").is_err());
        assert!(check_url("https://www.bca.gov.sg/").is_ok());
    }

    #[test]
    fn parses_ddg_anchor() {
        let html = r#"<a class="result__a" href="https://www.bca.gov.sg/corenet">CORENET X</a>"#;
        let hits = parse_ddg(html);
        assert_eq!(hits.len(), 1);
        assert_eq!(hits[0]["url"], "https://www.bca.gov.sg/corenet");
    }
}