use serde::{Deserialize, Serialize};
use std::sync::OnceLock;

pub const DEFAULT_PIPELINE: &str = "理解任务 → 检索本库与大类库 → 提纲 → 独立成稿 → 自检";

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Category {
    pub id: String,
    pub name: String,
    pub blurb: String,
    #[serde(default)]
    pub builtin: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Expert {
    pub id: String,
    pub name: String,
    pub category: String,
    pub category_name: String,
    pub title: String,
    pub delivers: String,
    pub risk: String,
    #[serde(default)]
    pub aliases: Vec<String>,
    #[serde(default = "default_pipeline")]
    pub pipeline: String,
    #[serde(default = "default_true")]
    pub builtin: bool,
    #[serde(default = "default_true")]
    pub enabled: bool,
}

impl Expert {
    pub fn default_pipeline() -> &'static str {
        DEFAULT_PIPELINE
    }

    pub fn is_high_risk(&self) -> bool {
        self.risk == "high"
    }
}

fn default_pipeline() -> String {
    DEFAULT_PIPELINE.to_string()
}

fn default_true() -> bool {
    true
}

#[derive(Debug, Deserialize)]
struct SeedFile {
    categories: Vec<Category>,
    experts: Vec<Expert>,
}

pub struct Seed {
    pub categories: Vec<Category>,
    pub experts: Vec<Expert>,
}

pub fn seed() -> &'static Seed {
    static SEED: OnceLock<Seed> = OnceLock::new();
    SEED.get_or_init(|| {
        let raw: SeedFile = serde_json::from_str(include_str!("../seed.json"))
            .expect("workbench/seed.json must deserialize");
        Seed {
            categories: raw.categories,
            experts: raw.experts,
        }
    })
}

pub fn pack_ids() -> Vec<&'static str> {
    seed().categories.iter().map(|c| c.id.as_str()).collect()
}
