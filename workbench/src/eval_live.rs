//! Live official-page + intent eval. Not run from `cargo test`.

use crate::agent::{self, Intent};
use crate::config::Paths;
use crate::websearch;
use serde_json::{json, Value};

struct PageCheck {
    id: &'static str,
    url: &'static str,
    needles: &'static [&'static str],
}

const PAGES: &[PageCheck] = &[
    PageCheck {
        id: "iras-gst",
        url: "https://www.iras.gov.sg/taxes/goods-services-tax-(gst)/basics-of-gst/current-gst-rates",
        needles: &["9%", "Current GST rates"],
    },
    PageCheck {
        id: "scdf-fire-code",
        url: "https://www.scdf.gov.sg/fire-safety-services-listing/fire-code-2023",
        needles: &["Fire Code 2023", "Fire Precautions"],
    },
    PageCheck {
        id: "ctu-code",
        url: "https://www.imo.org/en/ourwork/safety/pages/ctu-code.aspx",
        needles: &["CTU", "2014"],
    },
    PageCheck {
        id: "corenet-x",
        url: "https://info.corenet.gov.sg/regulatory-process/corenet-x-code-of-practice",
        needles: &["CORENET", "Code of Practice"],
    },
    PageCheck {
        id: "mof-procurement",
        url: "https://www.mof.gov.sg/policies/government-procurement/procurement-processes/",
        needles: &["procurement", "Tender"],
    },
];

pub fn report(paths: &Paths) -> Value {
    let intents = intent_rounds();
    let intent_ok = intents.iter().all(|c| c["ok"] == true);
    let pages: Vec<Value> = PAGES.iter().map(fetch_page).collect();
    let pages_hit = pages.iter().filter(|p| p["ok"] == true).count();
    let pages_ok = pages_hit >= 3;
    let search = search_round();
    let hitl = hitl_round(paths);
    let parse = parse_round(paths);
    let ok = intent_ok && pages_ok && search["ok"] == true && hitl["ok"] == true && parse["ok"] == true;
    json!({
        "ok": ok,
        "date": chrono::Local::now().format("%Y-%m-%d").to_string(),
        "thesis": "understand first; chat or run; writes stay steps; official pages not invented",
        "rounds": {
            "intent": { "ok": intent_ok, "cases": intents },
            "official_pages": { "ok": pages_ok, "hit": pages_hit, "pages": pages },
            "web_search": search,
            "hitl": hitl,
            "bid_parse": parse,
        },
    })
}

fn intent_rounds() -> Vec<Value> {
    let cases: &[(&str, Intent)] = &[
        ("什么是 GST", Intent::Chat),
        ("IRAS 发票是什么意思", Intent::Chat),
        ("临边防护算不算危大？要不要专家论证？", Intent::Chat),
        ("新加坡现在 GST 税率多少？", Intent::Chat),
        ("写临边防护方案讨论提纲", Intent::Run),
        ("按虚构滨河路人行道维修，写临边与洞口防护专项方案讨论提纲。", Intent::Run),
        ("一人公司成套投标", Intent::Run),
        ("先解释 GST 再出一份税务日历", Intent::Both),
    ];
    cases
        .iter()
        .map(|(text, want)| {
            let got = agent::understand(text);
            json!({
                "text": text,
                "want": want.as_str(),
                "got": got.as_str(),
                "ok": got == *want,
            })
        })
        .collect()
}

fn needle_hit(raw: &str, n: &str) -> bool {
    if raw.contains(n) {
        return true;
    }
    n == "9%" && (raw.contains("9 %") || raw.contains("9 per cent") || raw.contains("9 percent"))
}

fn fetch_page(p: &PageCheck) -> Value {
    let raw = websearch::open_url(p.url);
    let opened = raw.contains("【网页摘录") && !raw.contains("打开失败");
    let missing: Vec<&str> = p
        .needles
        .iter()
        .copied()
        .filter(|n| !needle_hit(&raw, n))
        .collect();
    json!({
        "id": p.id,
        "url": p.url,
        "opened": opened,
        "missing": missing,
        "ok": opened && missing.is_empty(),
        "excerpt": raw.chars().take(220).collect::<String>(),
    })
}

fn search_round() -> Value {
    let out = websearch::search("IRAS current GST rates Singapore 9%");
    let ok = out.contains("iras.gov.sg") || out.contains("GST");
    json!({
        "ok": ok,
        "query": "IRAS current GST rates Singapore 9%",
        "excerpt": out.chars().take(280).collect::<String>(),
    })
}

fn hitl_round(paths: &Paths) -> Value {
    let Some(exp) = crate::catalog::seed()
        .experts
        .iter()
        .find(|e| e.id == "construction")
        .cloned()
    else {
        return json!({"ok": false, "error": "no construction"});
    };
    let ticket = crate::harness::Ticket {
        session: "live-eval-hitl".into(),
        project: "滨河路".into(),
        jurisdiction: "SG".into(),
        brief: "写临边防护专项方案讨论提纲".into(),
        path: String::new(),
        confirm_ok: false,
    };
    let run = crate::harness::run_expert_steps(paths, &exp, ticket);
    json!({
        "ok": run.hitl.pending && run.files.is_empty() && run.illegal_count() == 0,
        "pending": run.hitl.pending,
        "files": run.files.len(),
        "illegal": run.illegal_count(),
    })
}

fn parse_round(paths: &Paths) -> Value {
    let Some(exp) = crate::catalog::seed()
        .experts
        .iter()
        .find(|e| e.id == "bid-parse")
        .cloned()
    else {
        return json!({"ok": false, "error": "no bid-parse"});
    };
    let ticket = crate::harness::Ticket {
        session: "live-eval-parse".into(),
        project: "Tuas".into(),
        jurisdiction: "SG".into(),
        brief: "Quality 40%\nPrice 60%\nTwo Envelope\nBCA workhead CW01\nmethod statement for working at height".into(),
        path: String::new(),
        confirm_ok: true,
    };
    let run = crate::harness::run_expert_steps(paths, &exp, ticket);
    let parse = run
        .files
        .iter()
        .find(|f| f.get("name").and_then(|v| v.as_str()) == Some("招标解析表.md"))
        .and_then(|f| f.get("path").and_then(|v| v.as_str()))
        .and_then(|p| std::fs::read_to_string(p).ok())
        .unwrap_or_default();
    let ok = run.illegal_count() == 0
        && parse.contains("Quality 40%")
        && parse.contains("CW01");
    json!({
        "ok": ok,
        "illegal": run.illegal_count(),
        "has_quality": parse.contains("Quality 40%"),
        "has_cw01": parse.contains("CW01"),
    })
}
