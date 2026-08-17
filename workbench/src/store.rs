use crate::catalog::{seed, Category, Expert, DEFAULT_PIPELINE};
use crate::config::Paths;
use crate::kbio::{
    ensure_expert_kb, ensure_kb_root, folder_stats, format_bytes, remove_expert_kb, valid_id,
};
use serde_json::{json, Map, Value};
use std::collections::{HashMap, HashSet};
use std::fs;
use std::sync::Mutex;

pub fn catalog_lock() -> &'static Mutex<()> {
    static LOCK: Mutex<()> = Mutex::new(());
    &LOCK
}

fn empty_user() -> Value {
    json!({
        "categories": [],
        "experts": [],
        "patches": {},
        "disabled": [],
        "kb_soft_limit_kb": 200
    })
}

pub fn load_user(paths: &Paths) -> Value {
    if !paths.user_catalog.is_file() {
        return empty_user();
    }
    let Ok(raw) = fs::read_to_string(&paths.user_catalog) else {
        return empty_user();
    };
    let Ok(parsed) = serde_json::from_str::<Value>(&raw) else {
        return empty_user();
    };
    let mut base = empty_user();
    if let (Some(b), Some(p)) = (base.as_object_mut(), parsed.as_object()) {
        for (k, v) in p {
            if b.contains_key(k) {
                b.insert(k.clone(), v.clone());
            }
        }
    }
    base
}

pub fn save_user(paths: &Paths, data: &Value) -> Result<(), String> {
    if let Some(parent) = paths.user_catalog.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let text = serde_json::to_string_pretty(data).map_err(|e| e.to_string())?;
    fs::write(&paths.user_catalog, text).map_err(|e| e.to_string())
}

pub fn all_categories(paths: &Paths) -> Vec<Category> {
    let user = load_user(paths);
    let mut seen: HashMap<String, Category> = HashMap::new();
    for c in &seed().categories {
        seen.insert(c.id.clone(), c.clone());
    }
    if let Some(extras) = user.get("categories").and_then(|v| v.as_array()) {
        for extra in extras {
            let Some(cid) = extra.get("id").and_then(|v| v.as_str()) else {
                continue;
            };
            if let Some(old) = seen.get(cid) {
                seen.insert(
                    cid.to_string(),
                    Category {
                        id: cid.to_string(),
                        name: extra
                            .get("name")
                            .and_then(|v| v.as_str())
                            .unwrap_or(&old.name)
                            .to_string(),
                        blurb: extra
                            .get("blurb")
                            .and_then(|v| v.as_str())
                            .unwrap_or(&old.blurb)
                            .to_string(),
                        builtin: old.builtin,
                    },
                );
            } else {
                seen.insert(
                    cid.to_string(),
                    Category {
                        id: cid.to_string(),
                        name: extra
                            .get("name")
                            .and_then(|v| v.as_str())
                            .unwrap_or(cid)
                            .to_string(),
                        blurb: extra
                            .get("blurb")
                            .and_then(|v| v.as_str())
                            .unwrap_or("")
                            .to_string(),
                        builtin: false,
                    },
                );
            }
        }
    }
    // keep seed order, then extras
    let mut out = Vec::new();
    let mut used = HashSet::new();
    for c in &seed().categories {
        if let Some(got) = seen.get(&c.id) {
            out.push(got.clone());
            used.insert(c.id.clone());
        }
    }
    for (id, c) in seen {
        if !used.contains(&id) {
            out.push(c);
        }
    }
    out
}

fn cat_name(paths: &Paths, cat_id: &str) -> String {
    all_categories(paths)
        .into_iter()
        .find(|c| c.id == cat_id)
        .map(|c| c.name)
        .unwrap_or_else(|| cat_id.to_string())
}

pub fn all_experts(paths: &Paths) -> Vec<Expert> {
    let user = load_user(paths);
    let disabled: HashSet<String> = user
        .get("disabled")
        .and_then(|v| v.as_array())
        .map(|a| {
            a.iter()
                .filter_map(|x| x.as_str().map(|s| s.to_string()))
                .collect()
        })
        .unwrap_or_default();
    let patches = user
        .get("patches")
        .and_then(|v| v.as_object())
        .cloned()
        .unwrap_or_default();
    let mut out = Vec::new();
    for seed_e in &seed().experts {
        if disabled.contains(&seed_e.id) {
            continue;
        }
        let patch = patches.get(&seed_e.id).cloned().unwrap_or(json!({}));
        out.push(apply_patch(seed_e, &patch, true, paths));
    }
    if let Some(raws) = user.get("experts").and_then(|v| v.as_array()) {
        for raw in raws {
            let Some(eid) = raw.get("id").and_then(|v| v.as_str()) else {
                continue;
            };
            if disabled.contains(eid) || out.iter().any(|e| e.id == eid) {
                continue;
            }
            out.push(from_value(raw, false, paths));
        }
    }
    out
}

pub fn get_expert(paths: &Paths, expert_id: &str) -> Option<Expert> {
    all_experts(paths).into_iter().find(|e| e.id == expert_id)
}

pub fn catalog_payload(paths: &Paths) -> Value {
    ensure_kb_root(paths);
    let user = load_user(paths);
    let limit = user
        .get("kb_soft_limit_kb")
        .and_then(|v| v.as_u64())
        .unwrap_or(200);
    let mut experts = Vec::new();
    for exp in all_experts(paths) {
        let st = folder_stats(
            paths,
            &paths.kb_root.join(&exp.category).join(&exp.id),
            &format!("{}/{}", exp.category, exp.id),
            "expert",
        );
        let shared = folder_stats(
            paths,
            &paths.kb_root.join(&exp.category).join("_shared"),
            &format!("{}/_shared", exp.category),
            "category",
        );
        let mut row = serde_json::to_value(&exp).unwrap_or(json!({}));
        if let Some(obj) = row.as_object_mut() {
            obj.insert("kb_bytes".into(), json!(st.bytes));
            obj.insert("kb_count".into(), json!(st.count));
            obj.insert("kb_label".into(), json!(format_bytes(st.bytes)));
            obj.insert("shared_bytes".into(), json!(shared.bytes));
            obj.insert("over_limit".into(), json!(st.bytes > limit * 1024));
        }
        experts.push(row);
    }
    let company = folder_stats(paths, &paths.kb_root.join("company"), "company", "company");
    json!({
        "mode_plain": "不召唤专家 = 普通 DeepSeek，无知识库、无出稿工具",
        "mode_expert": "召唤后该专家独立完成整件事（理解→检索本库+大类库→成稿→自检）",
        "categories": all_categories(paths),
        "experts": experts,
        "kb_soft_limit_kb": limit,
        "company_kb": {
            "bytes": company.bytes,
            "count": company.count,
            "label": format_bytes(company.bytes)
        },
        "max_file_bytes": 512 * 1024
    })
}

pub fn resolve_mentions(paths: &Paths, text: &str) -> Vec<String> {
    let mut found = Vec::new();
    if text.trim().is_empty() {
        return found;
    }
    for exp in all_experts(paths) {
        let mut labels = vec![exp.id.clone(), exp.name.clone()];
        labels.extend(exp.aliases.iter().cloned());
        let hit = labels.iter().any(|lab| {
            !lab.is_empty() && (text.contains(&format!("@{lab}")) || text.contains(&format!("召唤{lab}")))
        });
        if hit && !found.contains(&exp.id) {
            found.push(exp.id);
        }
    }
    found
}

pub fn upsert_category(paths: &Paths, cid: &str, name: &str, blurb: &str) -> Result<Value, String> {
    if !valid_id(cid) {
        return Err("大类 id：小写字母开头，字母数字连字符，2–32 位".into());
    }
    let _g = catalog_lock().lock().ok();
    let mut user = load_user(paths);
    let cats: Vec<Value> = user
        .get("categories")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default()
        .into_iter()
        .filter(|c| c.get("id").and_then(|v| v.as_str()) != Some(cid))
        .collect();
    let mut cats = cats;
    cats.push(json!({
        "id": cid,
        "name": if name.trim().is_empty() { cid } else { name.trim() },
        "blurb": blurb.trim(),
        "builtin": false
    }));
    user["categories"] = Value::Array(cats);
    save_user(paths, &user)?;
    ensure_expert_kb(paths, cid, "_placeholder", "placeholder");
    let placeholder = paths.kb_root.join(cid).join("_placeholder");
    if placeholder.exists() {
        let _ = fs::remove_dir_all(placeholder);
    }
    Ok(json!({"id": cid, "name": name, "blurb": blurb}))
}

pub fn upsert_expert(paths: &Paths, payload: &Value) -> Result<Expert, String> {
    let eid = payload
        .get("id")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .trim()
        .to_string();
    if !valid_id(&eid) {
        return Err("专家 id：小写字母开头，字母数字连字符，2–32 位".into());
    }
    let cat = payload
        .get("category")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .trim()
        .to_string();
    if !all_categories(paths).iter().any(|c| c.id == cat) {
        return Err("未知大类，请先建大类".into());
    }
    let name = payload
        .get("name")
        .and_then(|v| v.as_str())
        .unwrap_or(&eid)
        .trim()
        .to_string();
    let risk = if payload.get("risk").and_then(|v| v.as_str()) == Some("high") {
        "high"
    } else {
        "low"
    };
    let aliases = aliases_from(payload.get("aliases"));
    let title = payload
        .get("title")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .trim()
        .to_string();
    let delivers = {
        let d = payload
            .get("delivers")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .trim();
        if d.is_empty() {
            "独立成稿".to_string()
        } else {
            d.to_string()
        }
    };
    let pipeline = {
        let p = payload
            .get("pipeline")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .trim();
        if p.is_empty() {
            DEFAULT_PIPELINE.to_string()
        } else {
            p.to_string()
        }
    };
    let data = json!({
        "id": eid,
        "name": name,
        "category": cat,
        "category_name": cat_name(paths, &cat),
        "title": title,
        "delivers": delivers,
        "risk": risk,
        "aliases": aliases,
        "pipeline": pipeline,
        "builtin": false,
        "enabled": true
    });
    let _g = catalog_lock().lock().ok();
    let mut user = load_user(paths);
    let is_seed = seed().experts.iter().any(|s| s.id == eid);
    if is_seed {
        let mut patch = Map::new();
        for k in [
            "name",
            "title",
            "delivers",
            "risk",
            "aliases",
            "pipeline",
            "category",
            "category_name",
        ] {
            if let Some(v) = data.get(k) {
                patch.insert(k.to_string(), v.clone());
            }
        }
        user["patches"][&eid] = Value::Object(patch);
        if let Some(dis) = user.get_mut("disabled").and_then(|v| v.as_array_mut()) {
            dis.retain(|x| x.as_str() != Some(&eid));
        }
    } else {
        let mut experts: Vec<Value> = user
            .get("experts")
            .and_then(|v| v.as_array())
            .cloned()
            .unwrap_or_default()
            .into_iter()
            .filter(|e| e.get("id").and_then(|v| v.as_str()) != Some(&eid))
            .collect();
        experts.push(data);
        user["experts"] = Value::Array(experts);
    }
    save_user(paths, &user)?;
    ensure_kb_root(paths);
    ensure_expert_kb(paths, &cat, &eid, &name);
    get_expert(paths, &eid).ok_or_else(|| "保存失败".into())
}

pub fn disable_or_delete_expert(paths: &Paths, eid: &str, delete_kb: bool) -> Result<(), String> {
    let _g = catalog_lock().lock().ok();
    let mut user = load_user(paths);
    if seed().experts.iter().any(|s| s.id == eid) {
        let mut dis: Vec<Value> = user
            .get("disabled")
            .and_then(|v| v.as_array())
            .cloned()
            .unwrap_or_default();
        if !dis.iter().any(|x| x.as_str() == Some(eid)) {
            dis.push(json!(eid));
        }
        user["disabled"] = Value::Array(dis);
        return save_user(paths, &user);
    }
    let before: Vec<Value> = user
        .get("experts")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default()
        .into_iter()
        .filter(|e| e.get("id").and_then(|v| v.as_str()) == Some(eid))
        .collect();
    let remain: Vec<Value> = user
        .get("experts")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default()
        .into_iter()
        .filter(|e| e.get("id").and_then(|v| v.as_str()) != Some(eid))
        .collect();
    user["experts"] = Value::Array(remain);
    save_user(paths, &user)?;
    if delete_kb {
        if let Some(remove) = before.first() {
            let cat = remove.get("category").and_then(|v| v.as_str()).unwrap_or("");
            remove_expert_kb(paths, cat, eid);
        }
    }
    Ok(())
}

pub fn set_soft_limit(paths: &Paths, kb: i64) -> i64 {
    let kb = kb.clamp(8, 8192);
    let _g = catalog_lock().lock().ok();
    let mut user = load_user(paths);
    user["kb_soft_limit_kb"] = json!(kb);
    let _ = save_user(paths, &user);
    kb
}

pub fn tree_payload(paths: &Paths) -> Value {
    ensure_kb_root(paths);
    let limit = load_user(paths)
        .get("kb_soft_limit_kb")
        .and_then(|v| v.as_u64())
        .unwrap_or(200);
    let company = folder_stats(paths, &paths.kb_root.join("company"), "company", "company");
    let mut cats = Vec::new();
    let mut total = company.bytes;
    let experts = all_experts(paths);
    for cat in all_categories(paths) {
        let shared = folder_stats(
            paths,
            &paths.kb_root.join(&cat.id).join("_shared"),
            &format!("{}/_shared", cat.id),
            "category",
        );
        let mut members = Vec::new();
        for exp in experts.iter().filter(|e| e.category == cat.id) {
            let privs = folder_stats(
                paths,
                &paths.kb_root.join(&cat.id).join(&exp.id),
                &format!("{}/{}", cat.id, exp.id),
                "expert",
            );
            members.push(json!({
                "id": exp.id,
                "name": exp.name,
                "builtin": exp.builtin,
                "risk": exp.risk,
                "title": exp.title,
                "delivers": exp.delivers,
                "aliases": exp.aliases,
                "pipeline": exp.pipeline,
                "bytes": privs.bytes,
                "files": privs.files,
                "count": privs.count,
                "label": format_bytes(privs.bytes),
                "over_limit": privs.bytes > limit * 1024
            }));
            total += privs.bytes;
        }
        total += shared.bytes;
        cats.push(json!({
            "id": cat.id,
            "name": cat.name,
            "blurb": cat.blurb,
            "builtin": cat.builtin,
            "shared": {
                "bytes": shared.bytes,
                "files": shared.files,
                "count": shared.count,
                "label": format_bytes(shared.bytes)
            },
            "experts": members
        }));
    }
    json!({
        "company": {
            "bytes": company.bytes,
            "files": company.files,
            "count": company.count,
            "label": format_bytes(company.bytes)
        },
        "categories": cats,
        "total_bytes": total,
        "total_label": format_bytes(total),
        "kb_soft_limit_kb": limit,
        "max_file_bytes": 512 * 1024
    })
}

fn aliases_from(value: Option<&Value>) -> Vec<String> {
    match value {
        Some(Value::String(s)) => s
            .replace('，', ",")
            .split(',')
            .map(|p| p.trim().to_string())
            .filter(|p| !p.is_empty())
            .collect(),
        Some(Value::Array(a)) => a
            .iter()
            .filter_map(|x| x.as_str().map(|s| s.trim().to_string()))
            .filter(|s| !s.is_empty())
            .collect(),
        _ => vec![],
    }
}

fn apply_patch(seed: &Expert, patch: &Value, builtin: bool, paths: &Paths) -> Expert {
    let mut data = serde_json::to_value(seed).unwrap_or(json!({}));
    if let (Some(obj), Some(p)) = (data.as_object_mut(), patch.as_object()) {
        for (k, v) in p {
            if obj.contains_key(k) {
                obj.insert(k.clone(), v.clone());
            }
        }
    }
    from_value(&data, builtin, paths)
}

fn from_value(raw: &Value, builtin: bool, paths: &Paths) -> Expert {
    let cat = raw
        .get("category")
        .and_then(|v| v.as_str())
        .unwrap_or("construction")
        .to_string();
    let title_fallback = raw
        .get("name")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    Expert {
        id: raw
            .get("id")
            .and_then(|v| v.as_str())
            .unwrap_or("unknown")
            .to_string(),
        name: raw
            .get("name")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
            .unwrap_or_else(|| raw.get("id").and_then(|v| v.as_str()).unwrap_or("unknown"))
            .to_string(),
        category_name: raw
            .get("category_name")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
            .map(|s| s.to_string())
            .unwrap_or_else(|| cat_name(paths, &cat)),
        category: cat,
        title: raw
            .get("title")
            .and_then(|v| v.as_str())
            .unwrap_or(&title_fallback)
            .to_string(),
        delivers: raw
            .get("delivers")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string(),
        risk: if raw.get("risk").and_then(|v| v.as_str()) == Some("high") {
            "high".into()
        } else {
            "low".into()
        },
        aliases: aliases_from(raw.get("aliases")),
        pipeline: raw
            .get("pipeline")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
            .unwrap_or(DEFAULT_PIPELINE)
            .to_string(),
        builtin,
        enabled: raw.get("enabled").and_then(|v| v.as_bool()).unwrap_or(true),
    }
}
