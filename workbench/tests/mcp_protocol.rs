//! Drive shipped MCP JSON-RPC (resources + prompts + tools discovery).

use civil_workbench::config::Paths;
use civil_workbench::mcp::{self, McpFilter};
use serde_json::{json, Value};

fn paths() -> Paths {
    Paths::detect()
}

fn rpc(filter: McpFilter, method: &str, params: Value) -> Value {
    let msg = json!({"jsonrpc": "2.0", "id": 1, "method": method, "params": params});
    mcp::handle_rpc(&paths(), &filter, msg).expect("response")
}

#[test]
fn initialize_advertises_three_primitives() {
    let r = rpc(McpFilter { pack: None, expert: None }, "initialize", json!({}));
    let caps = &r["result"]["capabilities"];
    assert!(caps.get("tools").is_some(), "{caps}");
    assert!(caps.get("resources").is_some(), "{caps}");
    assert!(caps.get("prompts").is_some(), "{caps}");
}

#[test]
fn bid_parse_resources_are_scoped_and_readable() {
    let filter = McpFilter {
        pack: None,
        expert: Some("bid-parse".into()),
    };
    let listed = rpc(filter.clone(), "resources/list", json!({}));
    let res = listed["result"]["resources"].as_array().cloned().unwrap_or_default();
    assert!(res.iter().any(|r| r["uri"].as_str() == Some("kb://bid/bid-parse/web-knowledge.md")), "{res:?}");
    // sibling private lib must not appear
    assert!(
        !res.iter().any(|r| r["uri"].as_str().unwrap_or("").contains("bid-tech/")),
        "{res:?}"
    );

    let read = rpc(
        filter.clone(),
        "resources/read",
        json!({"uri": "kb://bid/bid-parse/web-knowledge.md"}),
    );
    let text = read["result"]["contents"][0]["text"].as_str().unwrap_or("");
    assert!(text.contains("招标解析"), "{text}");
    assert!(!text.contains("可以投标") || text.contains("不报"), "{text}");

    let deny = rpc(
        filter,
        "resources/read",
        json!({"uri": "kb://bid/bid-tech/outline.md"}),
    );
    let denied = deny["result"]["contents"][0]["text"].as_str().unwrap_or("");
    assert!(denied.starts_with("拒绝"), "{denied}");
}

#[test]
fn prompts_filtered_and_do_not_invent_bid() {
    let filter = McpFilter {
        pack: None,
        expert: Some("bid-parse".into()),
    };
    let listed = rpc(filter.clone(), "prompts/list", json!({}));
    let names: Vec<&str> = listed["result"]["prompts"]
        .as_array()
        .unwrap()
        .iter()
        .filter_map(|p| p["name"].as_str())
        .collect();
    assert_eq!(names, vec!["civil.bid.parse"]);

    let got = rpc(
        filter,
        "prompts/get",
        json!({
            "name": "civil.bid.parse",
            "arguments": {"tender_text": "工期 90 个日历天", "jurisdiction": "SG"}
        }),
    );
    let text = got["result"]["messages"][0]["content"]["text"]
        .as_str()
        .unwrap_or("");
    assert!(text.contains("90"), "{text}");
    assert!(text.contains("不要判定可投标"), "{text}");
}
