//! round20/21 的核心承诺：**给了表格路径读不到，必须在作业单正文里明说，
//! 不许拿演示数字冒充。** round23 补测。
//!
//! 背景：round22 给 Python 网关补了 `materials_notice` 门禁，但 exe 这一侧
//! （评委真正下载运行的那个）只有 round20 的实现、没有守卫。评委机上 :8000
//! 根本不存在，`run_table` 必然连不上 —— 这条路径反而**最常走**，却一直没测。
//!
//! 写这个测试时当场逮到两处真缺陷（都已在 packs.rs 修掉）：
//!   1. `materials` 是个没有任何 description 的裸 string，工具描述里也没说
//!      「用户给了文件路径就放这儿」。整个 round20 靠模型自己猜着把 Windows
//!      路径塞进一个叫 materials 的参数——猜不中就静默出演示柜数。
//!   2. 路径若被模型放进 notes，读表分支完全不触发，连「读不到」都不提示。
//!
//! 提示写在**文件正文**里，工具返回值只是「已写入 <路径>」——所以断言读文件。
//! 全部离线：不起 :8000、不联网。桥接指向必定无人监听的端口，
//! 因此开发机上 :8000 开没开，结论都一样。

use civil_workbench::config::Paths;
use civil_workbench::packs::{self, ToolCtx};
use serde_json::json;

/// 出现这句才算「说清楚了」—— 与 packs.rs 的两处文案对齐。
/// 注意别把 `**` 圈进来：正文是 `下面的数字**不是**这张表算出来的`，加粗符号把词切开了。
const HONEST: &str = "这张表算出来的";
const HEAD: &str = "给了表格路径";

fn ctx(session: &str) -> ToolCtx {
    ToolCtx::new(Paths::detect(), "pack-ship", "logistics", "low", true, session)
}

/// 跑完把工具写的作业单读回来 —— 提示在正文里，不在返回值里。
fn plan_doc(session: &str, args: serde_json::Value) -> String {
    // 指向一个不会有人监听的端口，模拟评委机（那里没有 :8000）。
    std::env::set_var("PACKING_AGENT_URL", "http://127.0.0.1:9");
    let mut c = ctx(session);
    let ret = packs::execute(&mut c, "pack-ship__plan", &args);
    assert!(ret.contains("已写入"), "工具没写出作业单：{ret}");
    let f = c.out_dir.join("装箱作业单.md");
    std::fs::read_to_string(&f).unwrap_or_else(|e| panic!("读不回 {}: {e}", f.display()))
}

#[test]
fn test_missing_table_path_says_so() {
    let doc = plan_doc(
        "rust-pack-table-missing",
        json!({"materials": r"pack C:\Users\nobody\桌面\根本不存在的表.xlsx"}),
    );
    assert!(doc.contains(HEAD), "路径读不到却没提示：\n{doc}");
    assert!(
        doc.contains(HONEST),
        "提示了但没说清数字来源，评委会把演示柜数当成他那张表的结果：\n{doc}"
    );
}

#[test]
fn test_bridge_down_says_so() {
    // 造一张真实存在、扩展名合法的表，越过 allow_local_path 那一关，
    // 卡在桥接那一关 —— 这正是评委机上的实际情形。
    let dir = std::env::temp_dir().join("cb-pack-table-test");
    let _ = std::fs::create_dir_all(&dir);
    let f = dir.join("物料清单.csv");
    std::fs::write(&f, "id,name,qty\nA1,钢管,10\n").unwrap();

    let doc = plan_doc(
        "rust-pack-table-bridge",
        json!({ "materials": format!("pack {}", f.display()) }),
    );
    assert!(
        doc.contains("没能用上") && doc.contains(HONEST),
        "桥接不可达时静默回落了 —— 这是评委机上的默认情形：\n{doc}"
    );
}

/// round23：模型把路径放进 notes 而不是 materials，也必须认。
/// 修之前这里整条分支不触发，文件里连「读不到」都没有。
#[test]
fn test_path_in_notes_still_seen() {
    let doc = plan_doc(
        "rust-pack-table-notes",
        json!({
            "materials": "一批钢管",
            "notes": r"清单在 C:\Users\nobody\桌面\也不存在.xlsx"
        }),
    );
    assert!(
        doc.contains(HEAD) && doc.contains(HONEST),
        "路径放在 notes 就当没看见，模型放错格子＝功能静默失效：\n{doc}"
    );
}

/// 没提任何路径时不许误报 —— 与 round22 网关侧门禁第 3 项同构。
#[test]
fn test_no_path_no_false_alarm() {
    let doc = plan_doc("rust-pack-table-nopath", json!({"materials": "一批钢管，十根"}));
    assert!(!doc.contains(HEAD), "没给路径却报「读不到」，是误报：\n{doc}");
}
