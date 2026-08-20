use crate::config::{llm_api_key, llm_config, llm_uses_thinking};
use serde_json::{json, Value};
use thiserror::Error;

#[derive(Debug, Error)]
#[error("{0}")]
pub struct LlmError(pub String);

pub fn has_key() -> bool {
    crate::config::has_key()
}

fn headers() -> Result<reqwest::header::HeaderMap, LlmError> {
    let key = llm_api_key();
    if key.is_empty() {
        return Err(LlmError(
            "未配置 API Key。在 demo/.env 写入 CIVIL_API_KEY / OPENAI_API_KEY / DEEPSEEK_API_KEY 后重启。".into(),
        ));
    }
    let mut h = reqwest::header::HeaderMap::new();
    h.insert(
        reqwest::header::AUTHORIZATION,
        format!("Bearer {key}")
            .parse()
            .map_err(|e: reqwest::header::InvalidHeaderValue| LlmError(e.to_string()))?,
    );
    h.insert(
        reqwest::header::CONTENT_TYPE,
        "application/json".parse().unwrap(),
    );
    h.insert(
        reqwest::header::ACCEPT_ENCODING,
        "identity".parse().unwrap(),
    );
    Ok(h)
}

fn thinking_on(for_tools: bool) -> bool {
    match std::env::var("DEEPSEEK_THINKING")
        .unwrap_or_default()
        .to_ascii_lowercase()
        .as_str()
    {
        "0" | "off" | "disabled" | "false" => false,
        "1" | "on" | "enabled" | "true" => true,
        _ => for_tools,
    }
}

fn http_client() -> Result<reqwest::Client, LlmError> {
    reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(120))
        .http1_only()
        .build()
        .map_err(|e| LlmError(format!("http client: {e}")))
}

fn http_err(status: reqwest::StatusCode, body: &str) -> LlmError {
    if status.as_u16() == 401 {
        return LlmError(
            "API Key 401：无效。请更新 demo/.env 后重启工作台。".into(),
        );
    }
    let cut: String = body.chars().take(400).collect();
    LlmError(format!("LLM {status}: {cut}"))
}

pub async fn chat(messages: &[Value], tools: Option<&[Value]>, temperature: f32) -> Result<Value, LlmError> {
    let cfg = llm_config();
    let thinking = llm_uses_thinking(&cfg.base_url) && thinking_on(tools.is_some());
    let mut payload = json!({
        "model": cfg.model,
        "messages": messages,
    });
    if thinking {
        payload["thinking"] = json!({ "type": "enabled" });
    } else {
        payload["temperature"] = json!(temperature);
    }
    if let Some(tools) = tools {
        payload["tools"] = json!(tools);
        payload["tool_choice"] = json!("auto");
    }
    let url = format!("{}/chat/completions", cfg.base_url);
    let r = http_client()?
        .post(url)
        .headers(headers()?)
        .json(&payload)
        .send()
        .await
        .map_err(|e| LlmError(format!("chat send: {e}")))?;
    let status = r.status();
    let raw = r
        .bytes()
        .await
        .map_err(|e| LlmError(format!("chat body: {e}")))?;
    let body = String::from_utf8_lossy(&raw).into_owned();
    if !status.is_success() {
        return Err(http_err(status, &body));
    }
    let v: Value = serde_json::from_str(&body).map_err(|e| LlmError(e.to_string()))?;
    v.pointer("/choices/0/message")
        .cloned()
        .ok_or_else(|| LlmError("LLM 响应缺少 message".into()))
}

pub async fn stream_plain<F>(messages: &[Value], temperature: f32, mut on_piece: F) -> Result<(), LlmError>
where
    F: FnMut(&str),
{
    let cfg = llm_config();
    let thinking = llm_uses_thinking(&cfg.base_url) && thinking_on(false);
    let mut payload = json!({
        "model": cfg.model,
        "messages": messages,
        "stream": true,
    });
    if thinking {
        payload["thinking"] = json!({ "type": "enabled" });
    } else {
        payload["temperature"] = json!(temperature);
    }
    let url = format!("{}/chat/completions", cfg.base_url);
    let mut r = http_client()?
        .post(url)
        .headers(headers()?)
        .json(&payload)
        .send()
        .await
        .map_err(|e| LlmError(format!("stream send: {e}")))?;
    if !r.status().is_success() {
        let status = r.status();
        let raw = r.bytes().await.unwrap_or_default();
        let body = String::from_utf8_lossy(&raw).into_owned();
        return Err(http_err(status, &body));
    }
    while let Some(chunk) = r
        .chunk()
        .await
        .map_err(|e| LlmError(format!("stream chunk: {e}")))?
    {
        let text = String::from_utf8_lossy(&chunk);
        for line in text.split('\n') {
            let line = line.trim();
            if line.is_empty() {
                continue;
            }
            let data = line.strip_prefix("data: ").unwrap_or("");
            if data.is_empty() {
                continue;
            }
            if data.trim() == "[DONE]" {
                return Ok(());
            }
            if let Ok(chunk) = serde_json::from_str::<Value>(data) {
                if let Some(piece) = chunk
                    .pointer("/choices/0/delta/content")
                    .and_then(|v| v.as_str())
                {
                    if !piece.is_empty() {
                        on_piece(piece);
                    }
                }
            }
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn unauthorized_does_not_echo_key_suffix() {
        let msg = http_err(
            reqwest::StatusCode::UNAUTHORIZED,
            r#"{"error":{"message":"Authentication Fails, Your api key: ****715b is invalid"}}"#,
        );
        let text = msg.to_string();
        assert!(!text.contains("715b"), "{text}");
        assert!(text.contains("401"), "{text}");
        assert!(text.contains("demo/.env"), "{text}");
    }
}
