//! One-person firm facade — production path is harness `steps`.

use crate::config::Paths;
use crate::extract::TenderFacts;
use serde_json::Value;

pub fn run_bid_job(paths: &Paths, session: &str, args: &Value) -> Value {
    let ticket = crate::harness::Ticket::from_args(session, args);
    crate::harness::run_bid_steps(paths, ticket).to_value()
}

pub fn empty_price_md(project: &str, jur: &str, facts: &TenderFacts) -> String {
    let mut md = format!(
        "# {project} · 价表（待填）\n\n内部讨论 AI 草稿，不是报价承诺，不是可提交的 Form of Tender。单价与合价不得编造，一律 UNSPECIFIED。合同族只写标题：PSSCOC for Construction Works 2020 / PSSCOC-lite for Construction Works 2025，条款 UNSPECIFIED。\n\n- 辖区：{jur}\n\n| 原文清单行 | 单位 | 数量 | 单价 | 合价 | 来源 |\n| --- | --- | --- | --- | --- | --- |\n"
    );
    if facts.price_items.is_empty() {
        md.push_str("| 未在原文检出清单行 [A001] | [A001] | [A001] | UNSPECIFIED | UNSPECIFIED | 招标未写 |\n");
    } else {
        for p in &facts.price_items {
            md.push_str(&format!(
                "| {} | {} | {} | UNSPECIFIED | UNSPECIFIED | ITT 原文 |\n",
                p.line, p.unit, p.qty
            ));
        }
    }
    md.push_str("\n禁止把上表单价写成可报价格。\n");
    md
}
