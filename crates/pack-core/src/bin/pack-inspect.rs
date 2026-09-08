use pack_core::inspect_file;
use std::env;
use std::path::PathBuf;

fn main() {
    let mut args: Vec<String> = env::args().skip(1).collect();
    if args.is_empty() {
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("..")
            .join("data")
            .join("external")
            .join("web_packing_lists");
        if root.is_dir() {
            args = std::fs::read_dir(&root)
                .unwrap()
                .filter_map(|e| e.ok())
                .map(|e| e.path())
                .filter(|p| {
                    matches!(
                        p.extension()
                            .and_then(|s| s.to_str())
                            .unwrap_or("")
                            .to_ascii_lowercase()
                            .as_str(),
                        "xls" | "xlsx" | "xlsm"
                    )
                })
                .map(|p| p.display().to_string())
                .collect();
        }
    }
    if args.is_empty() {
        eprintln!("usage: pack-inspect <file.xls[x]> [...]");
        std::process::exit(2);
    }

    for a in args {
        println!("{}", "-".repeat(72));
        match inspect_file(&a) {
            Ok(r) => {
                println!("{}  folded={} boxes={}", r.path, r.folded, r.n_boxes);
                for sh in &r.sheets {
                    println!(
                        "  sheet {}  hdr={} lines={} pkg={} lwh={} kg={:.1} rack={}",
                        sh.sheet,
                        sh.header_row,
                        sh.lines,
                        sh.packages,
                        sh.complete_lwh,
                        sh.weight_kg,
                        sh.rack_type.as_deref().unwrap_or("-")
                    );
                }
                for n in &r.notes {
                    println!("  fold {n}");
                }
                if let Some(b) = r.booking {
                    println!("  {}  {}  bind={}", b.container, b.note, b.binding);
                } else {
                    println!("  N0 skipped (no outer LWH)");
                }
            }
            Err(e) => println!("{a}\n  ERR {e}"),
        }
    }
}
