//! ux(round19) 项目 / 会话索引的行为断言。
//!
//! **自造 fixture，不依赖存量数据**：每个用例造一个临时 demo 根（含空 kb/static），
//! 用 `CIVIL_DEMO_ROOT` 指过去，因此在开发机、CI、评委机上都能真跑。
//! 这是刻意与 `scripts/test_audit_parity.py` 不同的取法 —— 那个依赖真实
//! `data/civilbuddy.db`，无库即 SKIP，在 CI 上几乎恒 SKIP。

use civil_workbench::config::Paths;
use civil_workbench::projects;
use std::fs;
use std::path::PathBuf;

/// 造一个隔离的 demo 根：`<tmp>/cb-projtest-<tag>/demo/{kb,static,out}`。
fn fixture(tag: &str) -> Paths {
    let root = std::env::temp_dir().join(format!("cb-projtest-{tag}"));
    let _ = fs::remove_dir_all(&root);
    let demo = root.join("demo");
    fs::create_dir_all(demo.join("kb")).unwrap();
    fs::create_dir_all(demo.join("static")).unwrap();
    fs::create_dir_all(demo.join("out")).unwrap();
    let mut p = Paths::detect();
    p.demo_root = demo.clone();
    p.kb_root = demo.join("kb");
    p.static_dir = demo.join("static");
    p.out_root = demo.join("out");
    p
}

fn mkdir_session(p: &Paths, sid: &str) -> PathBuf {
    let d = p.out_root.join(sid);
    fs::create_dir_all(&d).unwrap();
    d
}

#[test]
fn empty_out_root_only_yields_inbox() {
    let p = fixture("empty");
    let v = projects::list_projects(&p);
    assert_eq!(v["schema"], projects::SCHEMA_PROJECTS);
    assert_eq!(v["projects"].as_array().unwrap().len(), 0);
    assert_eq!(v["inbox"]["id"], projects::INBOX_ID);
    assert_eq!(v["inbox"]["n_sessions"], 0);
}

#[test]
fn underscore_dirs_are_skipped() {
    // demo/out/_threads 是真实存在的非会话目录；_index 是本模块自己的注册表目录。
    // 朴素扫描会把它们当成会话列出来。
    let p = fixture("underscore");
    mkdir_session(&p, "_threads");
    mkdir_session(&p, "_index");
    mkdir_session(&p, "sess-aaaa");
    let v = projects::list_sessions(&p, "", "", 50, 0);
    let ids: Vec<&str> = v["sessions"]
        .as_array()
        .unwrap()
        .iter()
        .map(|s| s["session_id"].as_str().unwrap())
        .collect();
    assert_eq!(ids, vec!["sess-aaaa"], "下划线目录必须被跳过");
    assert_eq!(v["total"], 1);
}

#[test]
fn pagination_limit_and_offset() {
    let p = fixture("page");
    for i in 0..5 {
        mkdir_session(&p, &format!("sess-{i:04}"));
    }
    let all = projects::list_sessions(&p, "", "", 50, 0);
    assert_eq!(all["total"], 5);
    let page = projects::list_sessions(&p, "", "", 2, 1);
    assert_eq!(page["limit"], 2);
    assert_eq!(page["offset"], 1);
    assert_eq!(page["sessions"].as_array().unwrap().len(), 2);
    assert_eq!(page["total"], 5, "total 是过滤后的全量，不随分页变");
    // limit 有服务端硬上限
    let big = projects::list_sessions(&p, "", "", 9999, 0);
    assert_eq!(big["limit"], 100);
}

#[test]
fn create_is_idempotent_by_name() {
    let p = fixture("idem");
    let (a, merged_a) = projects::create_project(&p, "滨河路维修").unwrap();
    assert!(!merged_a);
    let (b, merged_b) = projects::create_project(&p, "  滨河路维修  ").unwrap();
    assert!(merged_b, "同名重复建档必须幂等");
    assert_eq!(a["id"], b["id"]);
    assert!(projects::create_project(&p, "   ").is_err(), "空名必须拒绝");
}

#[test]
fn rename_keeps_id_and_carries_old_name_into_aliases() {
    let p = fixture("rename");
    let (a, _) = projects::create_project(&p, "滨河路人行道维修").unwrap();
    let id = a["id"].as_str().unwrap().to_string();
    let b = projects::patch_project(&p, &id, Some("滨河路维修一标"), None).unwrap();
    assert_eq!(b["id"].as_str().unwrap(), id, "改名不能换 id —— 存量会话靠 id 跟随");
    let aliases: Vec<&str> = b["aliases"].as_array().unwrap().iter().map(|v| v.as_str().unwrap()).collect();
    assert!(aliases.contains(&"滨河路人行道维修"), "旧名必须进 aliases，自动归类仍按旧名命中");
}

#[test]
fn inbox_is_immutable() {
    let p = fixture("inbox");
    assert!(projects::patch_project(&p, projects::INBOX_ID, Some("x"), None).is_err());
    assert!(projects::merge_project(&p, projects::INBOX_ID, "p-00000001").is_err());
}

#[test]
fn merge_leaves_tombstone_and_resolves_one_hop() {
    let p = fixture("merge");
    let (a, _) = projects::create_project(&p, "甲项目").unwrap();
    let (b, _) = projects::create_project(&p, "乙项目").unwrap();
    let (ida, idb) = (a["id"].as_str().unwrap().to_string(), b["id"].as_str().unwrap().to_string());

    // 先把一个会话归到 b
    mkdir_session(&p, "sess-merge01");
    projects::set_session_meta(&p, "sess-merge01", Some(&idb), None).unwrap();

    projects::merge_project(&p, &idb, &ida).unwrap();

    // 已写进 meta 的旧 id 不需要回写 —— 解析时跟随墓碑一跳
    let v = projects::list_sessions(&p, &ida, "", 50, 0);
    assert_eq!(v["total"], 1, "合并后旧 id 的会话应出现在目标项目下");

    let listed = projects::list_projects(&p);
    let ids: Vec<&str> = listed["projects"].as_array().unwrap().iter()
        .map(|x| x["id"].as_str().unwrap()).collect();
    assert!(ids.contains(&ida.as_str()));
    assert!(!ids.contains(&idb.as_str()), "墓碑不出现在活跃列表里");
}

#[test]
fn auto_classify_matches_name_and_alias_but_never_creates() {
    let p = fixture("auto");
    let (a, _) = projects::create_project(&p, "滨河路人行道维修").unwrap();
    let id = a["id"].as_str().unwrap().to_string();
    projects::patch_project(&p, &id, Some("滨河路维修一标"), None).unwrap();

    mkdir_session(&p, "sess-newname");
    projects::touch_session(&p, "sess-newname", "给滨河路维修一标写个交底", "");
    let m: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(p.out_root.join("sess-newname/session.meta.json")).unwrap()).unwrap();
    assert_eq!(m["project_id"].as_str().unwrap(), id, "按当前名命中");
    assert_eq!(m["project_source"], "auto");

    mkdir_session(&p, "sess-oldname");
    projects::touch_session(&p, "sess-oldname", "滨河路人行道维修 进度", "");
    let m2: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(p.out_root.join("sess-oldname/session.meta.json")).unwrap()).unwrap();
    assert_eq!(m2["project_id"].as_str().unwrap(), id, "按 alias（旧名）也要命中");

    mkdir_session(&p, "sess-nomatch");
    projects::touch_session(&p, "sess-nomatch", "完全无关的一句话", "");
    let m3: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(p.out_root.join("sess-nomatch/session.meta.json")).unwrap()).unwrap();
    assert_eq!(m3["project_id"].as_str().unwrap(), "", "不命中就是不归类");
    // 关键：自动归类**永不新建项目**（trace.json 的 project 实测是 "问" 这类垃圾）
    assert_eq!(projects::list_projects(&p)["projects"].as_array().unwrap().len(), 1);
}

#[test]
fn manual_classification_wins_over_auto() {
    let p = fixture("manual");
    let (a, _) = projects::create_project(&p, "甲项目").unwrap();
    let (b, _) = projects::create_project(&p, "乙项目").unwrap();
    let idb = b["id"].as_str().unwrap().to_string();
    mkdir_session(&p, "sess-man01");
    projects::set_session_meta(&p, "sess-man01", Some(&idb), None).unwrap();
    // 后续消息即使提到「甲项目」，也不能把人工归类改掉
    projects::touch_session(&p, "sess-man01", "顺便说下甲项目", "");
    let m: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(p.out_root.join("sess-man01/session.meta.json")).unwrap()).unwrap();
    assert_eq!(m["project_id"].as_str().unwrap(), idb);
    assert_eq!(m["project_source"], "manual");
    let _ = a;
}

#[test]
fn title_is_set_once_and_transcript_appends() {
    let p = fixture("title");
    mkdir_session(&p, "sess-title1");
    projects::touch_session(&p, "sess-title1", "第一句话定标题", "");
    projects::touch_session(&p, "sess-title1", "第二句话不该改标题", "");
    let m: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(p.out_root.join("sess-title1/session.meta.json")).unwrap()).unwrap();
    assert_eq!(m["title"].as_str().unwrap(), "第一句话定标题");
    assert_eq!(m["turns"], 2);

    projects::append_turn(&p, "sess-title1", "user", "问");
    projects::append_turn(&p, "sess-title1", "assistant", "答");
    let d = projects::session_detail(&p, "sess-title1").unwrap();
    let roles: Vec<&str> = d["transcript"].as_array().unwrap().iter()
        .map(|t| t["role"].as_str().unwrap()).collect();
    assert_eq!(roles, vec!["user", "assistant"]);
    assert_eq!(d["schema"], projects::SCHEMA_SESSION_DETAIL);
}

#[test]
fn session_id_guard_rejects_traversal_and_underscore() {
    assert!(projects::safe_session_id("_threads").is_err());
    assert!(projects::safe_session_id("..").is_err());
    assert!(projects::safe_session_id("a/b").is_err(), "斜杠被过滤后长度不足");
    assert!(projects::safe_session_id("ok-session-1").is_ok());
}

#[test]
fn broken_registry_never_loses_sessions() {
    // 注册表被手工改坏 / 指向不存在的项目 —— 会话必须仍然出现在 inbox，不能消失
    let p = fixture("broken");
    mkdir_session(&p, "sess-brk01");
    projects::set_session_meta(&p, "sess-brk01", Some("p-deadbeef"), None).unwrap();
    let v = projects::list_sessions(&p, projects::INBOX_ID, "", 50, 0);
    assert_eq!(v["total"], 1, "指向不存在项目的会话必须归 inbox");
}
