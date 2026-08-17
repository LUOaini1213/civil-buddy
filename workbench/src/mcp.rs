//! Minimal MCP stdio (newline-delimited JSON-RPC, plus Content-Length framing).

use crate::catalog::seed;
use crate::config::Paths;
use crate::packs::{self, ToolCtx};
use crate::store;
use serde_json::{json, Value};
use std::io::{self, BufRead, Write};

pub struct McpFilter {
    pub pack: Option<String>,
    pub expert: Option<String>,
}

pub fn serve_stdio(paths: Paths, filter: McpFilter) -> io::Result<()> {
    if let Some(p) = filter.pack.as_deref() {
        if !packs::valid_pack(p) {
            eprintln!("unknown pack {p}; valid: {:?}", crate::catalog::pack_ids());
            std::process::exit(2);
        }
    }
    let stdin = io::stdin();
    let mut lock = stdin.lock();
    let mut stdout = io::stdout();
    loop {
        let Some(msg) = read_message(&mut lock)? else {
            break;
        };
        if let Some(resp) = handle(&paths, &filter, msg) {
            write_message(&mut stdout, &resp)?;
        }
    }
    Ok(())
}

fn read_message(r: &mut impl BufRead) -> io::Result<Option<Value>> {
    let mut first = String::new();
    let n = r.read_line(&mut first)?;
    if n == 0 {
        return Ok(None);
    }
    let trimmed = first.trim();
    if trimmed.is_empty() {
        return read_message(r);
    }
    if trimmed.to_ascii_lowercase().starts_with("content-length:") {
        let len: usize = trimmed
            .split(':')
            .nth(1)
            .and_then(|s| s.trim().parse().ok())
            .unwrap_or(0);
        loop {
            let mut line = String::new();
            r.read_line(&mut line)?;
            if line.trim().is_empty() {
                break;
            }
        }
        let mut buf = vec![0u8; len];
        io::Read::read_exact(r, &mut buf)?;
        let v = serde_json::from_slice(&buf).unwrap_or(json!({}));
        return Ok(Some(v));
    }
    let v = serde_json::from_str(trimmed).unwrap_or(json!({}));
    Ok(Some(v))
}

fn write_message(w: &mut impl Write, v: &Value) -> io::Result<()> {
    let s = serde_json::to_string(v).unwrap_or_else(|_| "{}".into());
    writeln!(w, "{s}")?;
    w.flush()
}

fn handle(paths: &Paths, filter: &McpFilter, msg: Value) -> Option<Value> {
    let method = msg.get("method").and_then(|v| v.as_str()).unwrap_or("");
    let id = msg.get("id").cloned();
    if method.is_empty() || method.starts_with("notifications/") {
        return None;
    }
    let result = match method {
        "initialize" => {
            let ver = msg
                .pointer("/params/protocolVersion")
                .and_then(|v| v.as_str())
                .unwrap_or("2024-11-05");
            let name = filter
                .expert
                .as_deref()
                .map(|e| format!("civil-{e}"))
                .or_else(|| filter.pack.as_deref().map(|p| format!("civil-{p}")))
                .unwrap_or_else(|| "civil-buddy".into());
            json!({
                "protocolVersion": ver,
                "capabilities": { "tools": {} },
                "serverInfo": { "name": name, "version": "0.1.0" }
            })
        }
        "ping" => json!({}),
        "tools/list" => {
            let tools: Vec<Value> = list_tools(filter).iter().map(|t| t.mcp_tool()).collect();
            json!({ "tools": tools })
        }
        "tools/call" => {
            let name = msg
                .pointer("/params/name")
                .and_then(|v| v.as_str())
                .unwrap_or("");
            let args = msg
                .pointer("/params/arguments")
                .cloned()
                .unwrap_or(json!({}));
            let (text, is_err) = call_tool(paths, filter, name, &args);
            json!({
                "content": [{ "type": "text", "text": text }],
                "isError": is_err
            })
        }
        _ => {
            return Some(json!({
                "jsonrpc": "2.0",
                "id": id,
                "error": { "code": -32601, "message": format!("Method not found: {method}") }
            }));
        }
    };
    Some(json!({"jsonrpc": "2.0", "id": id, "result": result}))
}

fn list_tools(filter: &McpFilter) -> Vec<packs::ToolDef> {
    if let Some(eid) = filter.expert.as_deref() {
        return packs::tools_for_expert(eid);
    }
    packs::all_tools_filtered(filter.pack.as_deref())
}

fn call_tool(paths: &Paths, filter: &McpFilter, name: &str, args: &Value) -> (String, bool) {
    let expert_id = args
        .get("expert_id")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())
        .or_else(|| filter.expert.clone())
        .or_else(|| filter.pack.as_deref().map(|p| packs::default_expert(p).to_string()))
        .unwrap_or_else(|| infer_expert(name).to_string());
    let exp = store::get_expert(paths, &expert_id);
    let (category, risk) = match &exp {
        Some(e) => (e.category.clone(), e.risk.clone()),
        None => {
            let cat = filter
                .pack
                .as_deref()
                .map(|s| s.to_string())
                .or_else(|| {
                    seed()
                        .experts
                        .iter()
                        .find(|e| e.id == expert_id)
                        .map(|e| e.category.clone())
                })
                .unwrap_or_else(|| "construction".into());
            (cat, "low".into())
        }
    };
    let confirm_ok = args
        .get("confirm_ok")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);
    let session = args
        .get("session_id")
        .and_then(|v| v.as_str())
        .unwrap_or("mcp");
    let mut ctx = ToolCtx::new(paths.clone(), &expert_id, &category, &risk, confirm_ok, session);
    let text = packs::execute(&mut ctx, name, args);
    let err = text.starts_with("拒绝")
        || text.starts_with("未知工具")
        || text.starts_with("找不到")
        || text.starts_with("缺少")
        || text.starts_with("文件不存在");
    (text, err)
}

fn infer_expert(tool: &str) -> &'static str {
    if let Some(owner) = crate::tier_map::exclusive_owner(tool) {
        return owner;
    }
    let pack = tool.split("__").next().unwrap_or("");
    if packs::valid_pack(pack) {
        packs::default_expert(pack)
    } else {
        "construction"
    }
}
