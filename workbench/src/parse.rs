//! Optional heavy parsers: MinerU → Docling → Marker → builtin.
//! Default `CIVIL_PARSE=auto`: digital PDFs stay builtin; scans try installed CLIs.

use serde_json::{json, Value};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::thread;
use std::time::{Duration, Instant};

const HEAVY_EXTS: &[&str] = &["pdf", "docx", "pptx", "xlsx"];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Policy {
    Auto,
    Mineru,
    Docling,
    Marker,
    Builtin,
}

impl Policy {
    pub fn from_env() -> Self {
        match env::var("CIVIL_PARSE")
            .unwrap_or_default()
            .trim()
            .to_ascii_lowercase()
            .as_str()
        {
            "mineru" => Policy::Mineru,
            "docling" => Policy::Docling,
            "marker" => Policy::Marker,
            "builtin" | "off" | "0" => Policy::Builtin,
            _ => Policy::Auto,
        }
    }

    pub fn as_str(self) -> &'static str {
        match self {
            Policy::Auto => "auto",
            Policy::Mineru => "mineru",
            Policy::Docling => "docling",
            Policy::Marker => "marker",
            Policy::Builtin => "builtin",
        }
    }
}

#[derive(Clone, Debug)]
pub struct Extracted {
    pub kind: String,
    pub text: String,
    pub engine: String,
}

pub fn probe() -> Value {
    json!({
        "policy": Policy::from_env().as_str(),
        "mineru": bin_of("mineru", "CIVIL_MINERU_BIN").is_some(),
        "docling": bin_of("docling", "CIVIL_DOCLING_BIN").is_some(),
        "marker": bin_of("marker_single", "CIVIL_MARKER_BIN").is_some(),
        "note": "扫描件 PDF 优先 MinerU；未安装则 Docling / Marker；都没有走内置文字层。pip install \"mineru[all]\" 或 pip install docling",
    })
}

pub fn bin_of(name: &str, env_key: &str) -> Option<PathBuf> {
    if let Ok(p) = env::var(env_key) {
        let p = PathBuf::from(p.trim());
        if p.is_file() {
            return Some(p);
        }
    }
    if command_on_path(name) {
        return Some(PathBuf::from(name));
    }
    #[cfg(windows)]
    {
        let exe = format!("{name}.exe");
        if command_on_path(&exe) {
            return Some(PathBuf::from(exe));
        }
    }
    None
}

fn command_on_path(name: &str) -> bool {
    let mut cmd = Command::new(name);
    cmd.arg("--help")
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000);
    }
    match cmd.status() {
        Ok(st) => st.success() || st.code().is_some(),
        Err(_) => false,
    }
}

pub fn extract_rich(
    filename: &str,
    ext: &str,
    bytes: &[u8],
    builtin: Result<String, String>,
) -> Result<Extracted, String> {
    let policy = Policy::from_env();
    let builtin_ok = builtin
        .as_ref()
        .ok()
        .filter(|t| t.chars().count() >= 400);
    if policy == Policy::Builtin {
        return from_builtin(ext, builtin);
    }
    let want_heavy = policy != Policy::Auto || builtin_ok.is_none();
    if !want_heavy || !HEAVY_EXTS.contains(&ext) {
        return from_builtin(ext, builtin);
    }
    let order: &[&str] = match policy {
        Policy::Mineru => &["mineru"],
        Policy::Docling => &["docling"],
        Policy::Marker => &["marker"],
        Policy::Auto => &["mineru", "docling", "marker"],
        Policy::Builtin => &[],
    };
    for eng in order {
        if let Ok(text) = run_engine(eng, filename, ext, bytes) {
            if text.chars().count() >= 8 {
                return Ok(Extracted {
                    kind: ext.to_string(),
                    text,
                    engine: (*eng).into(),
                });
            }
        }
    }
    match from_builtin(ext, builtin) {
        Ok(got) => Ok(got),
        Err(e) => Err(format!(
            "{e}。扫描件可安装 MinerU：pip install \"mineru[all]\" 后设 CIVIL_PARSE=auto，或 CIVIL_MINERU_BIN=mineru 路径。"
        )),
    }
}

fn from_builtin(ext: &str, builtin: Result<String, String>) -> Result<Extracted, String> {
    builtin.map(|text| Extracted {
        kind: ext.to_string(),
        text,
        engine: "builtin".into(),
    })
}

fn run_engine(engine: &str, filename: &str, ext: &str, bytes: &[u8]) -> Result<String, String> {
    let (bin, env_key) = match engine {
        "mineru" => ("mineru", "CIVIL_MINERU_BIN"),
        "docling" => ("docling", "CIVIL_DOCLING_BIN"),
        "marker" => ("marker_single", "CIVIL_MARKER_BIN"),
        _ => return Err("unknown engine".into()),
    };
    let Some(prog) = bin_of(bin, env_key) else {
        return Err(format!("{engine} 未安装"));
    };
    let tmp = env::temp_dir().join(format!(
        "civil-parse-{}-{}",
        engine,
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_millis())
            .unwrap_or(0)
    ));
    fs::create_dir_all(&tmp).map_err(|e| e.to_string())?;
    let stem = Path::new(filename)
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("doc");
    let stem: String = stem
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || c == '-' || c == '_' {
                c
            } else {
                '_'
            }
        })
        .take(40)
        .collect();
    let input = tmp.join(format!("{stem}.{ext}"));
    let out = tmp.join("out");
    let _ = fs::create_dir_all(&out);
    fs::write(&input, bytes).map_err(|e| e.to_string())?;
    let timeout = if engine == "mineru" { 180 } else { 90 };
    let result = match engine {
        "mineru" => run_cmd(
            &prog,
            &[
                "-p",
                &input.to_string_lossy(),
                "-o",
                &out.to_string_lossy(),
                "-b",
                "pipeline",
            ],
            timeout,
        ),
        "docling" => {
            let a = run_cmd(
                &prog,
                &[
                    input.to_str().unwrap_or(""),
                    "--to",
                    "md",
                    "--output",
                    out.to_str().unwrap_or(""),
                ],
                timeout,
            );
            if a.is_ok() {
                a
            } else {
                run_cmd(
                    &prog,
                    &[
                        "convert",
                        input.to_str().unwrap_or(""),
                        "--to",
                        "md",
                        "--output",
                        out.to_str().unwrap_or(""),
                    ],
                    timeout,
                )
            }
        }
        "marker" => run_cmd(
            &prog,
            &[
                input.to_str().unwrap_or(""),
                "--output_dir",
                out.to_str().unwrap_or(""),
            ],
            timeout,
        ),
        _ => Err("unknown".into()),
    };
    let text = match result {
        Ok(()) => find_longest_md(&tmp).ok_or_else(|| format!("{engine} 未产出 markdown"))?,
        Err(e) => {
            let _ = fs::remove_dir_all(&tmp);
            return Err(e);
        }
    };
    let _ = fs::remove_dir_all(&tmp);
    Ok(text)
}

fn run_cmd(prog: &Path, args: &[&str], timeout_secs: u64) -> Result<(), String> {
    let mut cmd = Command::new(prog);
    cmd.args(args)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000);
    }
    let mut child = cmd.spawn().map_err(|e| format!("{}: {e}", prog.display()))?;
    let start = Instant::now();
    loop {
        match child.try_wait() {
            Ok(Some(st)) => {
                if st.success() {
                    return Ok(());
                }
                return Err(format!("{} 退出 {}", prog.display(), st));
            }
            Ok(None) => {
                if start.elapsed() > Duration::from_secs(timeout_secs) {
                    let _ = child.kill();
                    return Err(format!("{} 超时 {timeout_secs}s", prog.display()));
                }
                thread::sleep(Duration::from_millis(80));
            }
            Err(e) => return Err(e.to_string()),
        }
    }
}

pub fn find_longest_md(root: &Path) -> Option<String> {
    let mut best = String::new();
    walk_md(root, &mut best);
    if best.chars().count() >= 8 {
        Some(best)
    } else {
        None
    }
}

fn walk_md(dir: &Path, best: &mut String) {
    let Ok(rd) = fs::read_dir(dir) else {
        return;
    };
    for ent in rd.flatten() {
        let p = ent.path();
        if p.is_dir() {
            walk_md(&p, best);
            continue;
        }
        if p.extension().and_then(|s| s.to_str()).map(|s| s.eq_ignore_ascii_case("md")) != Some(true)
        {
            continue;
        }
        if let Ok(t) = fs::read_to_string(&p) {
            if t.chars().count() > best.chars().count() {
                *best = t;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_policy_is_auto() {
        assert_eq!(Policy::from_env(), Policy::Auto);
    }

    #[test]
    fn finds_longest_markdown() {
        let dir = env::temp_dir().join("civil-parse-md-test");
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(dir.join("auto")).unwrap();
        fs::write(dir.join("auto").join("a.md"), "short").unwrap();
        fs::write(dir.join("auto").join("b.md"), "Quality 40%\nPrice 60%\nCW01 workhead\n").unwrap();
        let got = find_longest_md(&dir).unwrap();
        assert!(got.contains("Quality 40%"));
        let _ = fs::remove_dir_all(&dir);
    }
}
