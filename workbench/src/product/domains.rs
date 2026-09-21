//! Narrow loopback bridge for existing deterministic CAD/engineering pages.
//! It cannot proxy chat, sessions, model settings or arbitrary URLs.
use axum::{
    body::{to_bytes, Body},
    extract::Request,
    http::{header, StatusCode},
    response::{IntoResponse, Response},
    routing::any,
    Router,
};
use serde_json::json;
use std::time::Duration;

pub fn router() -> Router {
    Router::new()
        .route("/cad", any(forward))
        .route("/engineering", any(forward))
        .route("/engineering/{*path}", any(forward))
        .route("/api/cad/{*path}", any(forward))
        .route("/api/engineering/{*path}", any(forward))
        .route("/api/asr", any(forward))
        .route("/api/asr/{*path}", any(forward))
}
fn error(status: StatusCode, message: &str) -> Response {
    (status, axum::Json(json!({"detail":message}))).into_response()
}

async fn forward(request: Request) -> Response {
    let Some(base) = std::env::var("CIVIL_DOMAIN_URL")
        .ok()
        .filter(|s| !s.is_empty())
    else {
        return error(
            StatusCode::SERVICE_UNAVAILABLE,
            "领域服务未启动，请使用 scripts/start_unified_workbench.py 启动完整工作台",
        );
    };
    let Ok(url) = reqwest::Url::parse(&base) else {
        return error(StatusCode::SERVICE_UNAVAILABLE, "领域服务地址无效");
    };
    if url.scheme() != "http"
        || !matches!(url.host_str(), Some("127.0.0.1" | "[::1]"))
        || url.path() != "/"
        || url.query().is_some()
    {
        return error(
            StatusCode::SERVICE_UNAVAILABLE,
            "领域服务必须使用固定回环地址",
        );
    }
    let (parts, body) = request.into_parts();
    if parts
        .headers
        .get("sec-fetch-site")
        .is_some_and(|v| v == "cross-site")
    {
        return error(StatusCode::FORBIDDEN, "只接受当前工作台请求");
    }
    if let Some(origin) = parts.headers.get(header::ORIGIN) {
        let origin = origin
            .to_str()
            .ok()
            .and_then(|s| reqwest::Url::parse(s).ok());
        let host = parts
            .headers
            .get(header::HOST)
            .and_then(|h| h.to_str().ok())
            .unwrap_or("");
        if origin.as_ref().is_none_or(|o| {
            !matches!(o.scheme(), "http" | "https")
                || o.origin().ascii_serialization() != format!("{}://{}", o.scheme(), host)
        }) {
            return error(StatusCode::FORBIDDEN, "请求来源不匹配工作台");
        }
    }
    let bytes = match to_bytes(body, 32 * 1024 * 1024).await {
        Ok(b) => b,
        Err(_) => return error(StatusCode::PAYLOAD_TOO_LARGE, "领域请求超过32MiB"),
    };
    let Ok(client) = reqwest::Client::builder()
        .timeout(Duration::from_secs(150))
        .redirect(reqwest::redirect::Policy::none())
        .build()
    else {
        return error(StatusCode::BAD_GATEWAY, "无法建立领域服务连接");
    };
    let mut outgoing = client
        .request(
            parts.method,
            format!(
                "{}{}",
                base.trim_end_matches('/'),
                parts
                    .uri
                    .path_and_query()
                    .map(|p| p.as_str())
                    .unwrap_or("/")
            ),
        )
        .body(bytes);
    for name in ["content-type", "x-civil-asr-id", "x-civil-operation-id", "x-cad-operation-id"] {
        if let Some(value) = parts.headers.get(name) {
            outgoing = outgoing.header(name, value);
        }
    }
    // Outer same-origin check has passed. The fixed sidecar validates its own host.
    if parts.headers.contains_key(header::ORIGIN) {
        outgoing = outgoing.header(header::ORIGIN, base.trim_end_matches('/'));
    }
    let mut response = match outgoing.send().await {
        Ok(r) => r,
        Err(_) => return error(StatusCode::BAD_GATEWAY, "领域服务不可用或请求超时"),
    };
    let status = response.status();
    let headers = response.headers().clone();
    let mut bytes = Vec::new();
    loop {
        match response.chunk().await {
            Ok(Some(chunk)) => {
                if bytes.len() + chunk.len() > 50 * 1024 * 1024 {
                    return error(StatusCode::BAD_GATEWAY, "领域结果超过50MiB");
                }
                bytes.extend_from_slice(&chunk);
            }
            Ok(None) => break,
            Err(_) => return error(StatusCode::BAD_GATEWAY, "读取领域结果失败"),
        }
    }
    let mut output = Response::builder().status(status);
    for name in [
        header::CONTENT_TYPE,
        header::CONTENT_DISPOSITION,
        header::CACHE_CONTROL,
    ] {
        if let Some(value) = headers.get(&name) {
            output = output.header(name, value);
        }
    }
    output
        .body(Body::from(bytes))
        .unwrap_or_else(|_| error(StatusCode::INTERNAL_SERVER_ERROR, "无效领域响应"))
}
