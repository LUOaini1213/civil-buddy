//! RAG 对拍探针（data-plan M4 · D-R3）：从命令行驱动 workbench 检索，输出 JSON hits，
//! 供 scripts/test_rag_parity.py 与 Python 新实现 top-3 对拍（parity ≥95% 红线）。
//!
//! 用法：civil-rag-probe <expert_id> <category> <query> [limit]
use civil_workbench::config::Paths;
use civil_workbench::rag;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 4 {
        eprintln!("usage: civil-rag-probe <expert_id> <category> <query> [limit]");
        std::process::exit(2);
    }
    let paths = Paths::detect();
    let limit: usize = args.get(4).and_then(|s| s.parse().ok()).unwrap_or(3);
    let hits = rag::search_kb(&paths, &args[1], &args[2], &args[3], limit);
    let out = serde_json::json!({
        "engine": if std::env::var("CB_RUST_RAG").as_deref().map(|v| v.eq_ignore_ascii_case("scan")).unwrap_or(false) {
            "scan"
        } else {
            "fts"
        },
        "hits": hits,
    });
    println!("{out}");
}
