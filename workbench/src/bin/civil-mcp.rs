use civil_workbench::config::Paths;
use civil_workbench::mcp;

fn main() {
    civil_workbench::config::load_env();

    let mut pack = None;
    let mut expert = None;
    let mut args = std::env::args().skip(1);
    while let Some(a) = args.next() {
        match a.as_str() {
            "--pack" => pack = args.next(),
            "--expert" => expert = args.next(),
            "--help" | "-h" => {
                eprintln!(
                    "civil-mcp [--pack <category>] [--expert <id>]\n  --pack uses that 大类 + default expert exclusives\n  --expert lists 通用 + 大类共享 + 该专家独有\n  categories: {}",
                    civil_workbench::catalog::pack_ids().join(", ")
                );
                return;
            }
            other => {
                eprintln!("unknown arg {other}");
                std::process::exit(2);
            }
        }
    }
    if let Err(e) = mcp::serve_stdio(Paths::detect(), mcp::McpFilter { pack, expert }) {
        eprintln!("civil-mcp: {e}");
        std::process::exit(1);
    }
}
