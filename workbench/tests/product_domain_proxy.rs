//! Real loopback upstream verifies the proxy's URL/header boundary without any
//! Python service, provider, model, or engineering solver.
use axum::{
    body::{to_bytes, Body},
    extract::Request,
    http::StatusCode,
    Json, Router,
};
use civil_workbench::product::domains;
use serde_json::{json, Value};
use std::{
    ffi::OsString,
    sync::{Arc, Mutex},
};
use tower::ServiceExt;

struct DomainEnv(Option<OsString>);
impl DomainEnv {
    fn set(url: &str) -> Self {
        let old = std::env::var_os("CIVIL_DOMAIN_URL");
        std::env::set_var("CIVIL_DOMAIN_URL", url);
        Self(old)
    }
}
impl Drop for DomainEnv {
    fn drop(&mut self) {
        match &self.0 {
            Some(value) => std::env::set_var("CIVIL_DOMAIN_URL", value),
            None => std::env::remove_var("CIVIL_DOMAIN_URL"),
        }
    }
}

async fn request(
    app: &Router,
    path: &str,
    origin: Option<&str>,
    site: Option<&str>,
) -> (StatusCode, Value) {
    let mut builder = Request::builder()
        .method("POST")
        .uri(path)
        .header("host", "127.0.0.1:8765")
        .header("content-type", "application/json")
        .header("X-CAD-Operation-ID", "cancel-operation-123")
        .header("x-civil-operation-id", "civil-operation-123")
        .header("x-civil-asr-id", "asr-operation-123")
        .header("authorization", "Bearer must-not-forward")
        .header("cookie", "provider_key=must-not-forward");
    if let Some(value) = origin {
        builder = builder.header("origin", value);
    }
    if let Some(value) = site {
        builder = builder.header("sec-fetch-site", value);
    }
    let response = app
        .clone()
        .oneshot(
            builder
                .body(Body::from(r#"{"operation":"calculate"}"#))
                .unwrap(),
        )
        .await
        .unwrap();
    let status = response.status();
    let bytes = to_bytes(response.into_body(), 1024 * 1024).await.unwrap();
    (
        status,
        serde_json::from_slice(&bytes).unwrap_or(Value::Null),
    )
}

#[tokio::test]
async fn fixed_domain_proxy_preserves_operation_ids_and_rejects_scope_escape() {
    let seen = Arc::new(Mutex::new(Vec::<Value>::new()));
    let captured = seen.clone();
    // Capture every possible upstream path so an accidentally forwarded chat
    // request cannot hide behind a downstream 404.
    let upstream = Router::new().fallback(move |request: Request| {
        let captured = captured.clone();
        async move {
            let (parts, body) = request.into_parts();
            let header = |key| {
                parts
                    .headers
                    .get(key)
                    .and_then(|v| v.to_str().ok())
                    .map(str::to_owned)
            };
            let record = json!({"path":parts.uri.to_string(), "method":parts.method.as_str(),
                "cad_id":header("x-cad-operation-id"),"civil_id":header("x-civil-operation-id"),
                "asr_id":header("x-civil-asr-id"),"origin":header("origin"),
                "authorization":header("authorization"),"cookie":header("cookie"),
                "body":String::from_utf8(to_bytes(body,1024).await.unwrap().to_vec()).unwrap()});
            captured.lock().unwrap().push(record.clone());
            Json(record)
        }
    });
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let base = format!("http://{}", listener.local_addr().unwrap());
    let _env = DomainEnv::set(&base);
    let server = tokio::spawn(async move {
        axum::serve(listener, upstream).await.unwrap();
    });
    let app = domains::router();
    let (status, received) = request(
        &app,
        "/api/engineering/planning/calculate?format=json&name=%E6%96%BD%E5%B7%A5",
        Some("http://127.0.0.1:8765"),
        Some("same-origin"),
    )
    .await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(
        received["path"],
        "/api/engineering/planning/calculate?format=json&name=%E6%96%BD%E5%B7%A5"
    );
    assert_eq!(received["cad_id"], "cancel-operation-123");
    assert_eq!(received["civil_id"], "civil-operation-123");
    assert_eq!(received["asr_id"], "asr-operation-123");
    assert_eq!(received["origin"], base);
    assert_eq!(received["method"], "POST");
    assert_eq!(received["body"], r#"{"operation":"calculate"}"#);
    assert!(received["authorization"].is_null());
    assert!(received["cookie"].is_null());
    for (origin, site) in [
        (Some("https://attacker.invalid"), None),
        (Some("null"), None),
        (Some("http://127.0.0.1:8766"), None),
        (Some("http://127.0.0.1:8765"), Some("cross-site")),
    ] {
        assert_eq!(
            request(&app, "/api/cad/build", origin, site).await.0,
            StatusCode::FORBIDDEN
        );
    }
    assert_eq!(
        seen.lock().unwrap().len(),
        1,
        "rejected origin reached the domain process"
    );
    for path in [
        "/api/chat",
        "/api/agent/turns",
        "/api/settings",
        "/https://attacker.invalid/",
        "/api/cad/../../api/chat",
        "/api/engineering/%2e%2e/%2e%2e/api/chat",
        "/api/cad/./projects",
        "/api/cad/%2F..%2Fapi%2Fchat",
        "/api/cad/%252e%252e/chat",
        "/api/cad/%5c..%5c..%5capi%5cchat",
    ] {
        let (status, _) = request(&app, path, None, None).await;
        assert!(
            status.is_client_error(),
            "forbidden route {path} returned {status}"
        );
        assert_eq!(
            seen.lock().unwrap().len(),
            1,
            "forbidden route {path} was sent upstream"
        );
    }
    std::env::set_var("CIVIL_DOMAIN_URL", "https://attacker.invalid");
    assert_eq!(
        request(&app, "/api/cad/projects", None, None).await.0,
        StatusCode::SERVICE_UNAVAILABLE
    );
    assert_eq!(seen.lock().unwrap().len(), 1);
    server.abort();
}
