//! 易标模块对照 + 三级工具可见性（通用 / 大类 / 独有）。
//! 映射文件 `yibiao-map.json` 是名册真源；是否挂上可执行工具看 packs 注册表。

use crate::catalog::seed;
use serde::Deserialize;
use std::collections::HashMap;
use std::sync::OnceLock;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ToolLayer {
    Common,
    Category,
    Exclusive,
}

#[derive(Debug, Deserialize)]
struct MapFile {
    yibiao_pipeline: Vec<String>,
    common_tools: Vec<String>,
    category_shared: HashMap<String, Vec<String>>,
    experts: Vec<ExpertMap>,
}

#[derive(Debug, Deserialize, Clone)]
pub struct ExpertMap {
    pub id: String,
    pub yibiao: Vec<String>,
    pub exclusive: Vec<String>,
    pub aligned: bool,
    pub note: String,
}

impl ExpertMap {
    pub fn category(&self) -> &'static str {
        seed()
            .experts
            .iter()
            .find(|e| e.id == self.id)
            .map(|e| e.category.as_str())
            .unwrap_or("")
    }
}

fn map_file() -> &'static MapFile {
    static MAP: OnceLock<MapFile> = OnceLock::new();
    MAP.get_or_init(|| {
        serde_json::from_str(include_str!("../yibiao-map.json")).expect("yibiao-map.json")
    })
}

pub fn yibiao_pipeline() -> &'static [String] {
    &map_file().yibiao_pipeline
}

pub fn common_tools() -> &'static [String] {
    &map_file().common_tools
}

pub fn category_shared(category: &str) -> &[String] {
    map_file()
        .category_shared
        .get(category)
        .map(|v| v.as_slice())
        .unwrap_or(&[])
}

pub fn all_expert_maps() -> &'static [ExpertMap] {
    &map_file().experts
}

pub fn expert_map(expert_id: &str) -> Option<&'static ExpertMap> {
    map_file().experts.iter().find(|e| e.id == expert_id)
}

pub fn exclusive_owner(tool: &str) -> Option<&'static str> {
    for e in &map_file().experts {
        if e.exclusive.iter().any(|t| t == tool) {
            return Some(e.id.as_str());
        }
    }
    None
}

pub fn layer_of(tool: &str) -> Option<ToolLayer> {
    if map_file().common_tools.iter().any(|t| t == tool) {
        return Some(ToolLayer::Common);
    }
    if exclusive_owner(tool).is_some() {
        return Some(ToolLayer::Exclusive);
    }
    for tools in map_file().category_shared.values() {
        if tools.iter().any(|t| t == tool) {
            return Some(ToolLayer::Category);
        }
    }
    None
}

/// Names this expert may see: 通用 + 本大类共享 + 本人独有（含尚未实现的规划名）。
pub fn assigned_names(expert_id: &str) -> Vec<String> {
    let mut out = common_tools().to_vec();
    let cat = seed()
        .experts
        .iter()
        .find(|e| e.id == expert_id)
        .map(|e| e.category.as_str())
        .unwrap_or("");
    for t in category_shared(cat) {
        if !out.iter().any(|x| x == t) {
            out.push(t.clone());
        }
    }
    if let Some(em) = expert_map(expert_id) {
        for t in &em.exclusive {
            if !out.iter().any(|x| x == t) {
                out.push(t.clone());
            }
        }
    }
    out
}

pub fn may_call(expert_id: &str, tool: &str) -> bool {
    if exclusive_owner(tool).is_some_and(|owner| owner != expert_id) {
        return false;
    }
    assigned_names(expert_id).iter().any(|t| t == tool)
}
