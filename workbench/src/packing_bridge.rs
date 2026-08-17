//! Sidecar to packing-agent. Numbers come from tools only; this crate never invents xyz.
//!
//! Connect:
//! - `PACKING_AGENT_URL` — e.g. http://127.0.0.1:8000  (POST /api/pipeline)
//! - `PACKING_AGENT_ROOT` — local checkout; runs `scripts/run_packing_sidecar.py`

use serde_json::{json, Value};
use std::env;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::Duration;

#[derive(Debug, Clone, Default)]
pub struct PackingSummary {
    pub ok: bool,
    pub n0: String,
    pub containers_used: String,
    pub boxes: String,
    pub can_fit: String,
    pub ship_ok: String,
    pub phase: String,
    pub source: String,
    pub error: Option<String>,
}

impl PackingSummary {
    pub fn markdown(&self) -> String {
        if let Some(e) = &self.error {
            return format!(
                "未接通或失败：{e}\n设 `PACKING_AGENT_URL`（http://127.0.0.1:8000）或 `PACKING_AGENT_ROOT`（packing-agent 仓库路径）后重跑。本岗**不编**柜数、xyz、重心。\n"
            );
        }
        format!(
            "- 来源：{}\n- ok: {}\n- n0: {}\n- containers_used: {}\n- boxes: {}\n- can_fit: {}\n- ship_ok: {}\n- phase: {}\n- 坐标/摆位：见 packing-agent 产物；本岗不重写 xyz。\n",
            self.source, self.ok, self.n0, self.containers_used, self.boxes, self.can_fit, self.ship_ok, self.phase
        )
    }

    pub fn n0_line(&self) -> String {
        if self.error.is_some() {
            "柜数 N0* = UNSPECIFIED；摆位 xyz = UNSPECIFIED。".into()
        } else {
            "柜数/N0* 以上文工具回传为准；未出现的数字标 UNSPECIFIED。".into()
        }
    }
}

pub fn url_configured() -> Option<String> {
    let base = env::var("PACKING_AGENT_URL")
        .unwrap_or_default()
        .trim()
        .trim_end_matches('/')
        .to_string();
    if base.is_empty() {
        return None;
    }
    if !(base.starts_with("http://127.0.0.1")
        || base.starts_with("http://localhost")
        || base.starts_with("https://"))
    {
        return None;
    }
    Some(base)
}

fn looks_like_engine(p: &Path) -> bool {
    p.is_dir() && p.join("packing_assistant").is_dir()
}

pub fn root_configured() -> Option<PathBuf> {
    let p = env::var("PACKING_AGENT_ROOT").unwrap_or_default();
    let p = PathBuf::from(p.trim());
    if looks_like_engine(&p) {
        return Some(p);
    }
    if let Ok(m) = env::var("CARGO_MANIFEST_DIR") {
        let repo = Path::new(&m).parent().map(Path::to_path_buf);
        if let Some(repo) = repo {
            if looks_like_engine(&repo) {
                return Some(repo);
            }
        }
    }
    if let Ok(cwd) = env::current_dir() {
        if looks_like_engine(&cwd) {
            return Some(cwd);
        }
        if looks_like_engine(&cwd.join("..")) {
            return Some(cwd.join(".."));
        }
    }
    None
}

pub fn probe() -> Value {
    let url = url_configured();
    let root = root_configured();
    let mut http = json!({"configured": url.is_some(), "up": false});
    if let Some(base) = url.clone() {
        http["url"] = json!(base);
        if let Ok(h) = http_health(&base) {
            http["up"] = json!(true);
            http["health"] = h;
        }
    }
    json!({
        "http": http,
        "python_root": root.as_ref().map(|p| p.display().to_string()),
        "connected": url.is_some() || root.is_some(),
    })
}

pub fn run(materials: &str, notes: &str) -> PackingSummary {
    if let Some(base) = url_configured() {
        match http_pipeline(&base, materials, notes) {
            Ok(s) => return s,
            Err(e) => {
                if root_configured().is_none() {
                    return PackingSummary {
                        error: Some(format!("HTTP {base}: {e}")),
                        ..Default::default()
                    };
                }
            }
        }
    }
    if let Some(root) = root_configured() {
        return match python_sidecar(&root, materials, notes) {
            Ok(s) => s,
            Err(e) => PackingSummary {
                error: Some(format!("sidecar: {e}")),
                ..Default::default()
            },
        };
    }
    PackingSummary {
        error: Some("未设置 PACKING_AGENT_URL 或 PACKING_AGENT_ROOT".into()),
        ..Default::default()
    }
}

pub fn summarize_pipeline_json(v: &Value, source: &str) -> PackingSummary {
    let summary = v.get("summary").cloned().unwrap_or(json!({}));
    let pick = |keys: &[&str]| -> String {
        for k in keys {
            if let Some(x) = summary.get(*k).filter(|x| !x.is_null()) {
                return x.to_string();
            }
            if let Some(x) = v.get(*k).filter(|x| !x.is_null()) {
                return x.to_string();
            }
        }
        "UNSPECIFIED".into()
    };
    PackingSummary {
        ok: v
            .get("ok")
            .and_then(|x| x.as_bool())
            .or_else(|| summary.get("ok").and_then(|x| x.as_bool()))
            .unwrap_or(false),
        n0: pick(&["n0"]),
        containers_used: pick(&["containers_used"]),
        boxes: pick(&["boxes"]),
        can_fit: pick(&["can_fit"]),
        ship_ok: pick(&["ship_ok"]),
        phase: pick(&["phase"]),
        source: source.to_string(),
        error: None,
    }
}

fn http_health(base: &str) -> Result<Value, String> {
    let client = reqwest::blocking::Client::builder()
        .timeout(Duration::from_secs(4))
        .http1_only()
        .build()
        .map_err(|e| e.to_string())?;
    let resp = client
        .get(format!("{base}/api/health"))
        .send()
        .map_err(|e| e.to_string())?;
    if !resp.status().is_success() {
        return Err(format!("HTTP {}", resp.status()));
    }
    resp.json().map_err(|e| e.to_string())
}

fn http_pipeline(base: &str, materials: &str, notes: &str) -> Result<PackingSummary, String> {
    let url = format!("{base}/api/pipeline");
    let payload = json!({
        "user_input": format!("{materials}\n{notes}"),
        "mode": "steps",
        "agent_mode": "steps",
        "enable_auto_confirm": true,
        "save_artifacts": false,
        "session_id": format!("civil-buddy-{}", chrono::Local::now().format("%H%M%S")),
    });
    let client = reqwest::blocking::Client::builder()
        .timeout(Duration::from_secs(180))
        .http1_only()
        .build()
        .map_err(|e| e.to_string())?;
    let resp = client
        .post(url)
        .json(&payload)
        .send()
        .map_err(|e| e.to_string())?;
    if !resp.status().is_success() {
        return Err(format!("HTTP {}", resp.status()));
    }
    let v: Value = resp.json().map_err(|e| e.to_string())?;
    Ok(summarize_pipeline_json(&v, &format!("http {base}")))
}

fn sidecar_script() -> Option<PathBuf> {
    if let Ok(m) = env::var("CARGO_MANIFEST_DIR") {
        let p = Path::new(&m).join("scripts").join("run_packing_sidecar.py");
        if p.is_file() {
            return Some(p);
        }
    }
    None
}

fn python_sidecar(root: &Path, materials: &str, notes: &str) -> Result<PackingSummary, String> {
    let script = sidecar_script().ok_or_else(|| "找不到 workbench/scripts/run_packing_sidecar.py".to_string())?;
    let mut child = Command::new("python")
        .arg(&script)
        .env("PACKING_AGENT_ROOT", root)
        .env("PACKING_SKIP_SKJOLBER", "1")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("启动 python: {e}"))?;
    let payload = json!({"user_input": format!("{materials}\n{notes}")});
    if let Some(stdin) = child.stdin.as_mut() {
        use std::io::Write;
        stdin
            .write_all(payload.to_string().as_bytes())
            .map_err(|e| e.to_string())?;
    }
    let out = child.wait_with_output().map_err(|e| e.to_string())?;
    if !out.status.success() {
        return Err(format!(
            "exit {:?} stderr={}",
            out.status.code(),
            String::from_utf8_lossy(&out.stderr).chars().take(400).collect::<String>()
        ));
    }
    let v: Value = serde_json::from_slice(&out.stdout).map_err(|e| {
        format!(
            "sidecar JSON: {e} stdout={}",
            String::from_utf8_lossy(&out.stdout).chars().take(200).collect::<String>()
        )
    })?;
    if v.get("error").and_then(|x| x.as_str()).is_some() && v.get("ok") != Some(&json!(true)) {
        return Err(v["error"].as_str().unwrap_or("sidecar error").into());
    }
    Ok(summarize_pipeline_json(
        &v,
        &format!("python {}", root.display()),
    ))
}
