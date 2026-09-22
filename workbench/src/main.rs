use civil_workbench::api::{app, AppState};
use civil_workbench::config::Paths;
use std::net::SocketAddr;

#[tokio::main]
async fn main() {
    civil_workbench::config::load_env();

    let paths = Paths::detect();
    let mut state = AppState::live(paths.clone());
    match civil_workbench::py_engine::PyEngine::start(&paths) {
        Ok(engine) => {
            eprintln!("Python 工具引擎已接上：{}", engine.base());
            state.engine = Some(std::sync::Arc::new(engine));
        }
        Err(err) => eprintln!("Python 工具引擎未启动（CAD / 施工计划 / 箱单 / 招标对照不可用）：{err}"),
    }
    let port: u16 = std::env::var("CIVIL_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8765);
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    eprintln!(
        "Civil Buddy workbench (Rust)  kb={}  http://{addr}",
        paths.kb_root.display()
    );
    let listener = tokio::net::TcpListener::bind(addr)
        .await
        .unwrap_or_else(|e| {
            eprintln!("bind {addr} failed: {e}");
            std::process::exit(1);
        });
    axum::serve(listener, app(state))
        .await
        .expect("server");
}
