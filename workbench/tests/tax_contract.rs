//! Offline tax inputs are unverified evidence, never a built-in current rate.
use civil_workbench::{agent, catalog, config::Paths, harness, packs::{self, ToolCtx}};
use serde_json::json;
use std::fs;

struct Fixture(Paths);
impl Fixture {
    fn new() -> Self {
        let base = std::env::temp_dir().join(format!("civil-tax-{}", uuid::Uuid::new_v4()));
        Self(Paths::from_demo(base))
    }
}
impl Drop for Fixture {
    fn drop(&mut self) { let _ = fs::remove_dir_all(&self.0.demo_root); }
}

#[test]
fn tax_chat_needs_no_kb_and_keeps_unknown_region_and_rate() {
    let fixture = Fixture::new();
    let reply = agent::offline_explain(&fixture.0, "什么是 GST？").unwrap();
    assert!(reply.contains("辖区：UNSPECIFIED"));
    assert!(reply.contains("税率：UNSPECIFIED"));
    assert!(!reply.contains("9%"));
    assert!(!fixture.0.demo_root.exists());
}

#[test]
fn tax_chat_accepts_only_one_explicit_user_rate_in_one_region() {
    let fixture = Fixture::new();
    for text in ["SG GST 税率多少？", "CN/SG GST 7.25%", "SG GST 税率：7.25% 或 4.25%"] {
        let reply = agent::offline_explain(&fixture.0, text).unwrap();
        assert!(reply.contains("税率：UNSPECIFIED"), "{reply}");
    }
    let reply = agent::offline_explain(&fixture.0, "SG GST 税率：7.25%").unwrap();
    assert!(reply.contains("税率：7.25%"));
    assert!(reply.contains("用户输入待核"));
    assert!(!reply.contains("9%"));
}

#[test]
fn tax_tool_missing_input_and_dual_do_not_default_tax_facts() {
    let fixture = Fixture::new();
    for (sid, args, zone) in [("missing", json!({}), "UNSPECIFIED"), ("dual", json!({"jurisdiction":"DUAL", "tax_rate":"7.25%"}), "DUAL")] {
        let mut ctx = ToolCtx::new(fixture.0.clone(), "finance-tax", "finance", "low", true, sid);
        assert!(packs::execute(&mut ctx, "finance-tax__calendar", &args).contains("已写入"));
        let text = fs::read_to_string(ctx.out_dir.join("税务检查表.md")).unwrap();
        assert!(text.contains(&format!("辖区：{zone}")));
        assert!(!text.contains("9%"));
        assert!(!text.contains("7.25%"));
        assert!(!text.contains("F5"));
        assert!(text.contains("submit_blocked=true"));
    }
}

#[test]
fn tax_tool_copies_given_structured_values_without_markup_injection() {
    let fixture = Fixture::new();
    let mut ctx = ToolCtx::new(fixture.0.clone(), "finance-tax", "finance", "low", true, "given");
    let args = json!({"jurisdiction":"SG", "entity":"甲|乙<丙", "tax":"GST", "period":"用户期间", "deadline":"用户节点", "tax_rate":"7.25%", "source":"测试.pdf"});
    assert!(packs::execute(&mut ctx, "finance-tax__calendar", &args).contains("已写入"));
    let text = fs::read_to_string(ctx.out_dir.join("税务检查表.md")).unwrap();
    assert!(text.contains("| SG | 甲&#124;乙&lt;丙 | GST | 用户期间 | 用户节点 | 7.25% | UNSPECIFIED | 测试.pdf |"), "{text}");
    assert!(text.contains("适用性未核验"));
}

#[test]
fn tax_harness_does_not_copy_historical_ticket_defaults_into_body() {
    let fixture = Fixture::new();
    let expert = catalog::seed().experts.iter().find(|e| e.id == "finance-tax").unwrap().clone();
    let ticket = harness::Ticket { session: "harness".into(), project: "测试".into(), jurisdiction:"SG".into(), brief:"出一份税务日历".into(), path:String::new(), confirm_ok:false };
    let run = harness::run_expert_steps(&fixture.0, &expert, ticket);
    let file = run.files.iter().find(|f| f["name"] == "税务检查表.md").unwrap();
    let text = fs::read_to_string(file["path"].as_str().unwrap()).unwrap();
    assert!(text.contains("辖区：UNSPECIFIED"), "{text}");
    assert!(!text.contains("2026-08"), "{text}");
    assert!(!text.contains("9%"), "{text}");
}

#[test]
fn tax_tool_owner_denial_remains_in_place() {
    let fixture = Fixture::new();
    let mut ctx = ToolCtx::new(fixture.0.clone(), "finance-fund", "finance", "low", true, "wrong-owner");
    assert!(packs::execute(&mut ctx, "finance-tax__calendar", &json!({})).contains("拒绝"));
    assert!(ctx.deliverables.is_empty());
}
