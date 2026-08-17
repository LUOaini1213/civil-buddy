use serde_json::{json, Value};

const COMPRESS_MARK: &str = "【对话压缩】";

#[derive(Debug, Clone)]
pub struct Policy {
    pub limit: usize,
    pub reserve: usize,
    pub compress_pct: u8,
    pub warn_pct: u8,
    pub keep_recent: usize,
}

impl Policy {
    pub fn from_env() -> Self {
        Self {
            limit: env_usize("CIVIL_CONTEXT_LIMIT", 1_000_000),
            reserve: env_usize("CIVIL_CONTEXT_RESERVE", 16_384),
            compress_pct: env_u8("CIVIL_CONTEXT_COMPRESS_PCT", 70),
            warn_pct: 50,
            keep_recent: env_usize("CIVIL_CONTEXT_KEEP_RECENT", 4).max(2),
        }
    }

    pub fn usable(&self) -> usize {
        self.limit.saturating_sub(self.reserve).max(1)
    }

    pub fn compress_at(&self) -> usize {
        self.usable().saturating_mul(self.compress_pct as usize) / 100
    }

    pub fn to_value(&self) -> Value {
        json!({
            "limit": self.limit,
            "reserve": self.reserve,
            "usable": self.usable(),
            "compress_pct": self.compress_pct,
            "warn_pct": self.warn_pct,
            "keep_recent": self.keep_recent,
            "compress_at": self.compress_at(),
        })
    }
}

fn env_usize(key: &str, default: usize) -> usize {
    std::env::var(key)
        .ok()
        .and_then(|s| s.parse().ok())
        .filter(|&n| n > 0)
        .unwrap_or(default)
}

fn env_u8(key: &str, default: u8) -> u8 {
    std::env::var(key)
        .ok()
        .and_then(|s| s.parse().ok())
        .filter(|&n| (1..=99).contains(&n))
        .unwrap_or(default)
}

#[derive(Debug, Clone)]
pub struct Report {
    pub used: usize,
    pub policy: Policy,
    pub compressed: bool,
    pub folded: usize,
    pub kept: usize,
}

impl Report {
    pub fn pct(&self) -> u8 {
        let u = self.policy.usable();
        ((self.used.min(u) * 100) / u).min(100) as u8
    }

    pub fn zone(&self) -> &'static str {
        let p = self.pct();
        if p >= 90 {
            "full"
        } else if self.compressed || p >= self.policy.compress_pct {
            "compact"
        } else if p >= self.policy.warn_pct {
            "warn"
        } else {
            "room"
        }
    }

    pub fn note(&self) -> String {
        let at = self.policy.compress_at();
        let keep = self.policy.keep_recent;
        if self.compressed {
            format!(
                "已压缩：更早 {} 条折成摘要，近 {} 条原文仍在。当前约 {} / {} token（{}%）。按字数估算，不是官方精确计数。",
                self.folded, self.kept, self.used, self.policy.limit, self.pct()
            )
        } else if self.pct() >= 90 {
            format!(
                "上下文快满（约 {} / {}，{}%）。再发可能只留最近 {} 条原文。",
                self.used, self.policy.limit, self.pct(), keep
            )
        } else if self.pct() >= self.policy.warn_pct {
            format!(
                "已过半（约 {} / {}，{}%）。用到 {} token（{}%）会把更早对话压成摘要，近 {} 条原文保留。",
                self.used, self.policy.limit, self.pct(), at, self.policy.compress_pct, keep
            )
        } else {
            format!(
                "还很宽裕（约 {} / {}，{}%）。用到 {} token（{}%）会压缩更早对话，近 {} 条原文保留。",
                self.used, self.policy.limit, self.pct(), at, self.policy.compress_pct, keep
            )
        }
    }

    pub fn plus_text(&self, extra: &str) -> Self {
        let mut r = self.clone();
        r.used = r.used.saturating_add(estimate_tokens(extra));
        r
    }

    pub fn to_value(&self) -> Value {
        json!({
            "used": self.used,
            "limit": self.policy.limit,
            "usable": self.policy.usable(),
            "pct": self.pct(),
            "zone": self.zone(),
            "compressed": self.compressed,
            "folded": self.folded,
            "kept": self.kept,
            "keep_recent": self.policy.keep_recent,
            "compress_at": self.policy.compress_at(),
            "note": self.note(),
            "estimated": true,
        })
    }
}

pub fn is_cjk(c: char) -> bool {
    matches!(
        c,
        '\u{4e00}'..='\u{9fff}' | '\u{3400}'..='\u{4dbf}' | '\u{f900}'..='\u{faff}'
    )
}

/// DeepSeek-ish estimate: 1 token per CJK char, 1 per 4 other non-space chars.
pub fn estimate_tokens(text: &str) -> usize {
    let mut cjk = 0usize;
    let mut other = 0usize;
    for c in text.chars() {
        if c.is_whitespace() {
            continue;
        }
        if is_cjk(c) {
            cjk += 1;
        } else {
            other += 1;
        }
    }
    cjk + other.div_ceil(4)
}

pub fn messages_tokens(msgs: &[Value]) -> usize {
    msgs.iter()
        .map(|m| {
            let role = m.get("role").and_then(|v| v.as_str()).unwrap_or("");
            let content = m.get("content").and_then(|v| v.as_str()).unwrap_or("");
            estimate_tokens(role) + estimate_tokens(content) + 4
        })
        .sum()
}

fn clip(s: &str, n: usize) -> String {
    let count = s.chars().count();
    let t: String = s.chars().take(n).collect();
    if count > n {
        format!("{t}…")
    } else {
        t
    }
}

fn fold_messages(old: &[Value]) -> String {
    let mut lines = vec![format!(
        "{COMPRESS_MARK}更早 {} 条原文已不再进入模型。下面是摘录。缺的事实标 [A001] / UNSPECIFIED，不要假装读过被丢掉的细节。",
        old.len()
    )];
    for (i, m) in old.iter().enumerate() {
        let role = m.get("role").and_then(|v| v.as_str()).unwrap_or("?");
        let who = if role == "user" { "你" } else { "助手" };
        let content = m
            .get("content")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .replace('\n', " ");
        lines.push(format!("{}. {}：{}", i + 1, who, clip(&content, 80)));
    }
    lines.join("\n")
}

fn looks_compressed(history: &[Value]) -> bool {
    history
        .first()
        .and_then(|m| m.get("content").and_then(|v| v.as_str()))
        .is_some_and(|s| s.contains(COMPRESS_MARK))
}

fn folded_count(history: &[Value]) -> usize {
    let Some(s) = history
        .first()
        .and_then(|m| m.get("content").and_then(|v| v.as_str()))
    else {
        return 0;
    };
    s.split("更早 ")
        .nth(1)
        .and_then(|rest| rest.split(['条', ' ']).next())
        .and_then(|n| n.parse().ok())
        .unwrap_or(0)
}

pub fn prepare_with(policy: &Policy, mut history: Vec<Value>) -> (Vec<Value>, Report) {
    let keep = policy.keep_recent.min(history.len().max(1));
    let mut compressed = false;
    let mut folded = 0usize;

    if history.len() > keep && messages_tokens(&history) >= policy.compress_at() {
        let split = history.len() - keep;
        let old: Vec<Value> = history.drain(..split).collect();
        folded = old.len();
        compressed = true;
        let summary = fold_messages(&old);
        let mut next = vec![json!({"role": "user", "content": summary})];
        next.append(&mut history);
        history = next;
    }

    if history.len() > 2 && messages_tokens(&history) >= policy.usable() * 90 / 100 {
        let split = history.len() - 2;
        let old: Vec<Value> = history.drain(..split).collect();
        folded += old.len();
        compressed = true;
        let summary = fold_messages(&old);
        let mut next = vec![json!({"role": "user", "content": summary})];
        next.append(&mut history);
        history = next;
    }

    let used = messages_tokens(&history);
    let kept = if compressed {
        history.len().saturating_sub(1)
    } else {
        history.len()
    };
    (
        history,
        Report {
            used,
            policy: policy.clone(),
            compressed,
            folded,
            kept,
        },
    )
}

pub fn prepare_history(history: Vec<Value>) -> (Vec<Value>, Report) {
    prepare_with(&Policy::from_env(), history)
}

pub fn inspect(history: &[Value], extras: &[&str]) -> Report {
    let policy = Policy::from_env();
    let mut used = messages_tokens(history);
    for e in extras {
        used = used.saturating_add(estimate_tokens(e));
    }
    let compressed = looks_compressed(history);
    let folded = if compressed {
        folded_count(history)
    } else {
        0
    };
    let kept = if compressed {
        history.len().saturating_sub(1)
    } else {
        history.len()
    };
    Report {
        used,
        policy,
        compressed,
        folded,
        kept,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cjk_counts_as_one_token() {
        assert_eq!(estimate_tokens("招标解析"), 4);
        assert_eq!(estimate_tokens("abcd"), 1);
    }

    #[test]
    fn short_history_not_compressed() {
        let policy = Policy {
            limit: 128_000,
            reserve: 4_096,
            compress_pct: 70,
            warn_pct: 50,
            keep_recent: 4,
        };
        let hist = vec![
            json!({"role":"user","content":"你好"}),
            json!({"role":"assistant","content":"请说项目"}),
        ];
        let (out, report) = prepare_with(&policy, hist);
        assert!(!report.compressed);
        assert_eq!(out.len(), 2);
        assert_eq!(report.zone(), "room");
    }

    #[test]
    fn long_history_folds_old_turns() {
        let policy = Policy {
            limit: 200,
            reserve: 20,
            compress_pct: 40,
            warn_pct: 30,
            keep_recent: 2,
        };
        let mut hist = Vec::new();
        for i in 0..8 {
            hist.push(json!({"role":"user","content": format!("这是第{}轮用户问题，新加坡T5航站楼投标资料还缺评分点", i)}));
            hist.push(json!({"role":"assistant","content": format!("这是第{}轮助手回答，先列 GeBIZ 与 BCA PQM 待核项", i)}));
        }
        let (out, report) = prepare_with(&policy, hist);
        assert!(report.compressed, "{report:?}");
        assert!(report.folded >= 2, "folded={}", report.folded);
        assert!(out.len() <= 3, "len={}", out.len());
        let first = out[0]["content"].as_str().unwrap();
        assert!(first.contains(COMPRESS_MARK), "{first}");
    }
}