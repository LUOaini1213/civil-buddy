//! ux(round19) 对拍用的一次性 dump：把 projects.rs 的一组行为跑一遍并打印 JSON，
//! 供 `scripts/test_projects_parity.py` 与 Python 侧 `demo/projects.py` 逐字段比对。
//!
//! 只读参数：`parity_dump <out_root>`。不进发布包（package-workbench-release.ps1
//! 只拷 civil-workbench.exe），仅供测试。

use civil_workbench::config::Paths;
use civil_workbench::projects;
use serde_json::{json, Map, Value};
use std::path::PathBuf;

fn main() {
    let arg = std::env::args().nth(1).unwrap_or_default();
    if arg.is_empty() {
        eprintln!("用法: parity_dump <out_root>");
        std::process::exit(2);
    }
    let mut p = Paths::detect();
    p.out_root = PathBuf::from(&arg);

    let mut res = Map::new();
    res.insert("empty_projects".into(), projects::list_projects(&p));
    res.insert(
        "empty_sessions".into(),
        projects::list_sessions(&p, "", "", 50, 0),
    );

    let (a, merged_a) = projects::create_project(&p, "滨河路人行道维修").unwrap();
    res.insert("create".into(), json!({"project": a, "merged": merged_a}));

    let (b, merged_b) = projects::create_project(&p, "  滨河路人行道维修  ").unwrap();
    res.insert(
        "create_idempotent".into(),
        json!({"merged": merged_b, "same_id": a["id"] == b["id"]}),
    );

    let id = a["id"].as_str().unwrap().to_string();
    let r = projects::patch_project(&p, &id, Some("滨河路维修一标"), None).unwrap();
    res.insert(
        "rename".into(),
        json!({"project": r, "id_stable": r["id"].as_str().unwrap() == id}),
    );

    projects::touch_session(&p, "sess-alpha", "给滨河路维修一标写个交底", "");
    projects::touch_session(&p, "sess-beta", "滨河路人行道维修 的进度", "");
    projects::touch_session(&p, "sess-gamma", "完全无关的一句话", "");

    res.insert("after_touch_projects".into(), projects::list_projects(&p));
    res.insert("by_project".into(), projects::list_sessions(&p, &id, "", 50, 0));
    res.insert(
        "inbox".into(),
        projects::list_sessions(&p, projects::INBOX_ID, "", 50, 0),
    );
    res.insert("page".into(), projects::list_sessions(&p, "", "", 2, 1));
    res.insert(
        "limit_cap".into(),
        projects::list_sessions(&p, "", "", 9999, 0)["limit"].clone(),
    );

    projects::append_turn(&p, "sess-alpha", "user", "问一句");
    projects::append_turn(&p, "sess-alpha", "assistant", "答一句");
    res.insert("detail".into(), projects::session_detail(&p, "sess-alpha").unwrap());

    // 守卫：与 Python 侧同序、同标签
    let mut guards: Vec<String> = Vec::new();
    guards.push(match projects::safe_session_id("_threads") {
        Ok(_) => "safe_session_id('_threads',)=NO-RAISE".into(),
        Err(_) => "safe_session_id=raise".into(),
    });
    guards.push(match projects::safe_session_id("..") {
        Ok(_) => "safe_session_id('..',)=NO-RAISE".into(),
        Err(_) => "safe_session_id=raise".into(),
    });
    guards.push(match projects::set_session_meta(&p, "sess-alpha", Some("nope"), None) {
        Ok(_) => "safe_project_id('nope',)=NO-RAISE".into(),
        Err(_) => "safe_project_id=raise".into(),
    });
    guards.push(match projects::create_project(&p, "   ") {
        Ok(_) => "clean_name('   ',)=NO-RAISE".into(),
        Err(_) => "clean_name=raise".into(),
    });
    guards.push(match projects::patch_project(&p, projects::INBOX_ID, Some("x"), None) {
        Ok(_) => "inbox-patch=NO-RAISE".into(),
        Err(_) => "inbox-patch=raise".into(),
    });
    res.insert("guards".into(), json!(guards));

    println!("{}", Value::Object(res));
}
