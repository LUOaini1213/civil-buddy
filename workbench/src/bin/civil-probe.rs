//! Fresh binary consumer of exclusive writers (not unit-test internals).
use civil_workbench::config::Paths;
use civil_workbench::packs::{self, ToolCtx};
use serde_json::json;

fn main() {
    let paths = Paths::detect();
    let session = "probe-new-writer";
    let mut writer = ToolCtx::new(
        paths.clone(),
        "bid-parse",
        "bid",
        "low",
        true,
        session,
    );
    let tender = "\
INVITATION TO TENDER — Jurong Island tank farm\n\
Evaluation criteria (PQM):\n\
- Quality 40%\n\
- Price 60%\n\
Tenderers shall submit a method statement for working at height.\n\
Required: 临边防护专项方案\n\
Time for Completion: 120 days";
    let ok = packs::execute(
        &mut writer,
        "bid-parse__extract",
        &json!({
            "project_name": "Jurong Island tank farm tender",
            "jurisdiction": "SG",
            "tender_text": tender
        }),
    );
    println!("writer={ok}");
    let artifact = writer.out_dir.join("招标解析表.md");
    println!("artifact={}", artifact.display());
    println!("exists={}", artifact.is_file());
    if let Ok(t) = std::fs::read_to_string(&artifact) {
        println!("has_quality40={}", t.contains("Quality 40%"));
        println!("has_special={}", t.contains("临边防护专项方案"));
        println!("has_method={}", t.contains("method statement for working at height"));
    }
    let mut sib = ToolCtx::new(paths.clone(), "bid-tech", "bid", "low", true, session);
    let refuse = packs::execute(
        &mut sib,
        "bid-parse__extract",
        &json!({"tender_text": "x"}),
    );
    println!("sibling={refuse}");

    let mut scheme = ToolCtx::new(
        paths.clone(),
        "construction",
        "construction",
        "high",
        true,
        "probe-scheme",
    );
    let scheme_ok = packs::execute(
        &mut scheme,
        "construction__scheme_draft",
        &json!({
            "project_name": "滨河路人行道维修",
            "work_scope": "临边防护",
            "site_name": "滨河路人行道",
            "height_m": 3.2,
            "jurisdiction": "SG"
        }),
    );
    println!("scheme_writer={scheme_ok}");
    let scheme_path = scheme.out_dir.join("专项方案-AI草稿.md");
    println!("scheme_artifact={}", scheme_path.display());
    println!("scheme_exists={}", scheme_path.is_file());
    if let Ok(t) = std::fs::read_to_string(&scheme_path) {
        println!("scheme_has_site={}", t.contains("滨河路人行道"));
        println!("scheme_has_height={}", t.contains("3.2"));
    }
    let mut scheme_sib = ToolCtx::new(
        paths.clone(),
        "survey",
        "construction",
        "high",
        true,
        "probe-scheme-sib",
    );
    let scheme_refuse = packs::execute(
        &mut scheme_sib,
        "construction__scheme_draft",
        &json!({"project_name":"滨河路","work_scope":"临边","height_m":3.2}),
    );
    println!("scheme_sibling={scheme_refuse}");

    let mut fire = ToolCtx::new(
        paths.clone(),
        "fire-protect",
        "design",
        "high",
        true,
        "probe-fire",
    );
    let fire_ok = packs::execute(
        &mut fire,
        "fire-protect__brief",
        &json!({"scope": "Tuas warehouse hydrant", "jurisdiction": "SG"}),
    );
    println!("fire_writer={fire_ok}");
    let fire_path = fire.out_dir.join("消防专篇提纲.md");
    println!("fire_artifact={}", fire_path.display());
    println!("fire_exists={}", fire_path.is_file());
    let mut fire_sib = ToolCtx::new(paths.clone(), "architecture", "design", "low", true, "probe-fire-sib");
    let fire_refuse = packs::execute(
        &mut fire_sib,
        "fire-protect__brief",
        &json!({"scope": "x"}),
    );
    println!("fire_sibling={fire_refuse}");

    let mut dual = ToolCtx::new(
        paths,
        "cost",
        "commercial",
        "low",
        true,
        "probe-cost-dual",
    );
    let dual_ok = packs::execute(
        &mut dual,
        "cost__takeoff",
        &json!({"items":"rebar","jurisdiction":"DUAL","other_jurisdiction":"CN"}),
    );
    println!("dual_writer={dual_ok}");
    let dual_path = dual.out_dir.join("工程量拆分表.md");
    println!("dual_exists={}", dual_path.is_file());
    if let Ok(t) = std::fs::read_to_string(&dual_path) {
        println!("dual_has_banner={}", t.contains("DUAL（SG + CN）"));
    }

    let mut cn_cost = ToolCtx::new(
        Paths::detect(),
        "cost",
        "commercial",
        "low",
        true,
        "probe-cost-cn",
    );
    let cn_ok = packs::execute(
        &mut cn_cost,
        "cost__takeoff",
        &json!({"items":"rebar","jurisdiction":"CN"}),
    );
    println!("cn_writer={cn_ok}");
    if let Ok(t) = std::fs::read_to_string(cn_cost.out_dir.join("工程量拆分表.md")) {
        println!("cn_has_psscoc={}", t.contains("PSSCOC"));
        println!("cn_has_zone={}", t.contains("辖区：CN"));
    }

    let mut pack = ToolCtx::new(
        Paths::detect(),
        "pack-ship",
        "plant",
        "low",
        true,
        "probe-pack-off",
    );
    let pack_ok = packs::execute(
        &mut pack,
        "pack-ship__plan",
        &json!({
            "materials": "H-beam 12m x 20 pcs",
            "connected": false
        }),
    );
    println!("pack_writer={pack_ok}");
    if let Ok(t) = std::fs::read_to_string(pack.out_dir.join("装箱作业单.md")) {
        println!("pack_util={}", t.contains("utilization=UNSPECIFIED"));
        println!("pack_fit={}", t.contains("can_fit=UNSPECIFIED"));
        println!("pack_mid50={}", t.contains("mid50=UNSPECIFIED"));
        println!("pack_lash={}", t.contains("系固待办=UNSPECIFIED"));
    }

    let mut scheme11 = ToolCtx::new(
        Paths::detect(),
        "construction",
        "construction",
        "high",
        true,
        "probe-scheme-11",
    );
    let _ = packs::execute(
        &mut scheme11,
        "construction__scheme_draft",
        &json!({
            "project_name": "probe scheme",
            "work_scope": "临边防护",
            "jurisdiction": "SG"
        }),
    );
    if let Ok(t) = std::fs::read_to_string(scheme11.out_dir.join("专项方案-AI草稿.md")) {
        println!("scheme_ch8={}", t.contains("## 8 环保与文明施工"));
        println!("scheme_no_start={}", !t.contains("可以开工"));
    }
}
