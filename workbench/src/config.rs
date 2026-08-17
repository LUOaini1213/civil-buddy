use std::env;
use std::path::{Path, PathBuf};

#[derive(Clone, Debug)]
pub struct Paths {
    pub repo_root: PathBuf,
    pub demo_root: PathBuf,
    pub kb_root: PathBuf,
    pub out_root: PathBuf,
    pub data_dir: PathBuf,
    pub user_catalog: PathBuf,
    pub skill_hard_rules: PathBuf,
    pub static_dir: PathBuf,
    pub fill_scheme_py: PathBuf,
    pub scan_py: PathBuf,
    pub template_docx: PathBuf,
}

impl Paths {
    pub fn detect() -> Self {
        let demo = detect_demo_root();
        Self::from_demo(demo)
    }

    pub fn from_demo(demo_root: PathBuf) -> Self {
        let repo_root = demo_root
            .parent()
            .filter(|p| p.join("skills").is_dir() || p.join("demo").is_dir())
            .map(Path::to_path_buf)
            .unwrap_or_else(|| demo_root.clone());
        let kb_root = demo_root.join("kb");
        let data_dir = demo_root.join("data");
        let skill = repo_root.join("skills").join("civil-buddy");
        Self {
            out_root: demo_root.join("out"),
            user_catalog: data_dir.join("user_catalog.json"),
            skill_hard_rules: skill.join("references").join("hard-rules.md"),
            fill_scheme_py: skill.join("scripts").join("fill_scheme_template.py"),
            scan_py: skill.join("scripts").join("scan_forbidden_inventions.py"),
            template_docx: skill
                .join("references")
                .join("templates")
                .join("scheme-cn-a4.docx"),
            static_dir: demo_root.join("static"),
            kb_root,
            data_dir,
            repo_root,
            demo_root,
        }
    }
}

fn looks_like_demo(p: &Path) -> bool {
    p.join("kb").is_dir() && p.join("static").is_dir()
}

fn find_demo_upwards(start: &Path) -> Option<PathBuf> {
    let mut dir = Some(start.to_path_buf());
    for _ in 0..10 {
        let d = dir?;
        if looks_like_demo(&d) {
            return Some(d.canonicalize().unwrap_or(d));
        }
        let demo = d.join("demo");
        if looks_like_demo(&demo) {
            return Some(demo.canonicalize().unwrap_or(demo));
        }
        dir = d.parent().map(Path::to_path_buf);
    }
    None
}

fn detect_demo_root() -> PathBuf {
    if let Ok(p) = env::var("CIVIL_DEMO_ROOT") {
        let p = PathBuf::from(p);
        if p.is_dir() {
            return p;
        }
    }
    if let Ok(manifest) = env::var("CARGO_MANIFEST_DIR") {
        if let Some(found) = find_demo_upwards(Path::new(&manifest)) {
            return found;
        }
    }
    if let Ok(exe) = env::current_exe() {
        if let Some(found) = find_demo_upwards(&exe) {
            return found;
        }
    }
    let cwd = env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    find_demo_upwards(&cwd).unwrap_or(cwd)
}

/// cwd `.env` fills gaps; `demo/.env` overrides a stale User-level key.
pub fn load_env() {
    let demo_env = Paths::detect().demo_root.join(".env");
    let _ = dotenvy::dotenv();
    if demo_env.is_file() {
        let _ = dotenvy::from_path_override(&demo_env);
    }
}

pub fn deepseek_api_key() -> String {
    env::var("DEEPSEEK_API_KEY")
        .unwrap_or_default()
        .trim()
        .to_string()
}

pub fn deepseek_base_url() -> String {
    env::var("DEEPSEEK_BASE_URL")
        .unwrap_or_else(|_| "https://api.deepseek.com".into())
        .trim_end_matches('/')
        .to_string()
}

pub fn deepseek_model() -> String {
    env::var("DEEPSEEK_MODEL").unwrap_or_else(|_| "deepseek-v4-flash".into())
}

pub fn max_agent_steps() -> usize {
    env::var("CIVIL_MAX_AGENT_STEPS")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8)
}

pub fn has_key() -> bool {
    !deepseek_api_key().is_empty()
}
