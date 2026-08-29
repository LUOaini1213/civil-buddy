//! 意图行为金句测试（Rust 侧）。
//!
//! 读同一份金句 `test/eval/intents_golden.json` + 契约 `contract/intents.v1.json`，
//! 断言 `agent::understand` / `agent::match_skill_implicit` 与冻结基线一致。
//! Python 侧由 `scripts/test_stack_parity.py` 实跑 understand()+match_skill() 断言同一份金句。

use civil_workbench::agent::{match_skill_implicit, understand, Intent};

#[test]
fn intents_golden_matches_frozen_baseline() {
    let manifest = env!("CARGO_MANIFEST_DIR");
    let golden_path = std::path::Path::new(manifest)
        .join("..")
        .join("test")
        .join("eval")
        .join("intents_golden.json");
    let raw = std::fs::read_to_string(&golden_path)
        .unwrap_or_else(|e| panic!("金句文件缺失 {:?}: {e}", golden_path));
    let golden: serde_json::Value =
        serde_json::from_str(&raw).unwrap_or_else(|e| panic!("金句文件非法 JSON: {e}"));
    let cases = golden
        .get("cases")
        .and_then(|c| c.as_array())
        .unwrap_or_else(|| panic!("金句缺 cases 数组"));
    assert!(cases.len() >= 15, "金句至少 15 条，实为 {}", cases.len());
    for case in cases {
        let text = case
            .get("text")
            .and_then(|t| t.as_str())
            .unwrap_or_else(|| panic!("金句 case 缺 text"));
        let want_intent = case
            .get("intent")
            .and_then(|t| t.as_str())
            .unwrap_or_else(|| panic!("金句 case 缺 intent: {text}"));
        let want_skill = case.get("skill").and_then(|t| t.as_str());
        let got_intent = understand(text).as_str();
        let got_skill = match_skill_implicit(text);
        assert_eq!(
            got_intent, want_intent,
            "intent 漂移: {text:?}（want={want_intent} got={got_intent}；若为新行为请同步金句并说明）"
        );
        assert_eq!(
            got_skill.as_deref(),
            want_skill,
            "skill 漂移: {text:?}（want={want_skill:?} got={:?}；若为新行为请同步金句并说明）",
            got_skill.as_deref()
        );
    }
}

#[test]
fn contract_vocab_is_wired_not_inlined() {
    // agent.rs 源码不得再内联契约词表字面量（唯一真源 = contract/intents.v1.json）。
    // 判据与 scripts/test_stack_parity.py 一致：
    // a) 不得出现 ≥2 个契约词组的字符串数组字面量（词表复制的结构签名）；
    // b) 高区分度词组（提示文案里不会合法出现的）不得以标量形式出现。
    let src = include_str!("../src/agent.rs");
    let manifest = env!("CARGO_MANIFEST_DIR");
    let contract_path = std::path::Path::new(manifest)
        .join("..")
        .join("contract")
        .join("intents.v1.json");
    let raw =
        std::fs::read_to_string(&contract_path).unwrap_or_else(|e| panic!("契约文件缺失: {e}"));
    let contract: serde_json::Value =
        serde_json::from_str(&raw).unwrap_or_else(|e| panic!("契约非法 JSON: {e}"));
    let mut vocab: Vec<String> = Vec::new();
    for key in [
        "pack_action_zh",
        "packish",
        "phrase_write",
        "write_nouns",
        "ask",
        "tender",
    ] {
        for v in contract[key].as_array().expect("契约词表必须是数组") {
            vocab.push(v.as_str().expect("词表元素必须是字符串").to_string());
        }
    }
    for item in contract["strong_match"].as_array().expect("strong_match 数组") {
        let pair = item
            .as_array()
            .filter(|p| p.len() == 2)
            .expect("strong_match 元素必须是 [phrase, expert_id]");
        vocab.push(pair[0].as_str().expect("phrase 必须是字符串").to_string());
    }
    assert!(
        src.contains(r#"include_str!("../../contract/intents.v1.json")"#),
        "agent.rs 未从契约 include_str 加载词表"
    );

    // a) 字符串数组字面量中 ≥2 个词组 → 内联词表
    for arr in rust_string_arrays(src) {
        let overl: Vec<&String> = arr.iter().filter(|s| vocab.contains(*s)).collect();
        assert!(
            overl.len() < 2,
            "agent.rs 残留内联词表数组: {overl:?}（唯一真源是 contract/intents.v1.json）"
        );
    }

    // b) 高区分度词组不得出现在源码任何位置（"出稿/成稿/落盘/方案/提纲/草稿/解释/科普/招标"
    //    在提示文案中合法出现，不在禁列；"pack" 是其它标识符的子串，跳过）。
    let legit_prose = [
        "出稿", "成稿", "落盘", "方案", "提纲", "草稿", "解释", "科普", "招标", "pack",
    ];
    for phrase in &vocab {
        if legit_prose.contains(&phrase.as_str()) {
            continue;
        }
        assert!(
            !src.contains(phrase.as_str()),
            "agent.rs 残留内联词表字面量 {phrase:?}（唯一真源是 contract/intents.v1.json）"
        );
    }
    assert_eq!(
        understand("什么是 GST"),
        Intent::Chat,
        "sanity: 金句之外的基础 chat 判定被破坏"
    );
}

/// 源码中所有平衡 `[...]` 且首元素为字符串字面量的段（与 parity 脚本同判据）。
fn rust_string_arrays(src: &str) -> Vec<Vec<String>> {
    let bytes = src.as_bytes();
    let mut out = Vec::new();
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] != b'[' {
            i += 1;
            continue;
        }
        let mut j = i + 1;
        while j < bytes.len() && bytes[j].is_ascii_whitespace() {
            j += 1;
        }
        if j < bytes.len() && bytes[j] == b'"' {
            let mut depth = 0i32;
            let mut k = i;
            let mut end = None;
            while k < bytes.len() {
                match bytes[k] {
                    b'[' => depth += 1,
                    b']' => {
                        depth -= 1;
                        if depth == 0 {
                            end = Some(k);
                            break;
                        }
                    }
                    _ => {}
                }
                k += 1;
            }
            if let Some(e) = end {
                out.push(capture_strings(&src[i..=e]));
                i = e + 1;
                continue;
            }
        }
        i += 1;
    }
    out
}

fn capture_strings(seg: &str) -> Vec<String> {
    let mut out = Vec::new();
    let mut chars = seg.chars().peekable();
    while let Some(c) = chars.next() {
        if c != '"' {
            continue;
        }
        let mut s = String::new();
        while let Some(c2) = chars.next() {
            if c2 == '\\' {
                if let Some(esc) = chars.next() {
                    s.push(esc);
                }
            } else if c2 == '"' {
                break;
            } else {
                s.push(c2);
            }
        }
        out.push(s);
    }
    out
}
