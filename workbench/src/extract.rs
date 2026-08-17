//! Pull facts that are already in the user's tender / brief. Do not invent scores.

use regex::Regex;
use std::sync::OnceLock;

#[derive(Debug, Clone, Default)]
pub struct ScoreRow {
    pub label: String,
    pub weight: String,
    pub source: String,
}

#[derive(Debug, Clone, Default)]
pub struct PriceItem {
    pub line: String,
    pub unit: String,
    pub qty: String,
}

#[derive(Debug, Clone, Default)]
pub struct TenderFacts {
    pub scores: Vec<String>,
    pub quals: Vec<String>,
    pub duration: Vec<String>,
    pub specials: Vec<String>,
    pub score_rows: Vec<ScoreRow>,
    pub workheads: Vec<String>,
    pub envelope: Vec<String>,
    pub price_items: Vec<PriceItem>,
}

pub fn facts_from_text(text: &str) -> TenderFacts {
    let mut facts = TenderFacts::default();
    for unit in units(text) {
        classify(&unit, &mut facts);
        if let Some(row) = parse_score_row(&unit) {
            facts.score_rows.push(row);
        }
        for wh in workheads_in(&unit) {
            facts.workheads.push(wh);
        }
        if is_envelope(&unit) {
            facts.envelope.push(unit.clone());
        }
        if let Some(item) = parse_price_item(&unit) {
            facts.price_items.push(item);
        }
    }
    facts.scores = dedup(facts.scores);
    facts.quals = dedup(facts.quals);
    facts.duration = dedup(facts.duration);
    facts.specials = dedup(facts.specials);
    facts.workheads = dedup(facts.workheads);
    facts.envelope = dedup(facts.envelope);
    facts.score_rows = dedup_score_rows(facts.score_rows);
    facts.price_items = dedup_price(facts.price_items);
    facts
}

fn units(text: &str) -> Vec<String> {
    let mut out = Vec::new();
    for raw in text.split(['\n', '\r', '；', ';', '。']) {
        let t = raw.trim().trim_start_matches(['-', '•', '*', '–']).trim();
        if t.is_empty() {
            continue;
        }
        out.push(t.to_string());
        for piece in t.split("  ") {
            let p = piece.trim();
            if p.len() >= 4 && p != t {
                out.push(p.to_string());
            }
        }
    }
    out
}

fn classify(t: &str, facts: &mut TenderFacts) {
    let low = t.to_ascii_lowercase();
    let score_hit = t.contains('分')
        || t.contains("评分")
        || t.contains("评标")
        || t.contains("技术标")
        || t.contains("商务标")
        || low.contains("score")
        || low.contains("pqm")
        || low.contains("qfm")
        || low.contains("evaluation")
        || quality_price_weight(t);
    if score_hit {
        facts.scores.push(t.to_string());
    }
    if t.contains("资质")
        || t.contains("证书")
        || t.contains("workhead")
        || t.contains("CW01")
        || t.contains("CW02")
        || low.contains("qualif")
        || low.contains("csoc")
        || low.contains("bcss")
    {
        facts.quals.push(t.to_string());
    }
    if t.contains("工期")
        || t.contains("日历天")
        || low.contains("calendar day")
        || low.contains("time for completion")
        || days_re().is_match(&low)
    {
        facts.duration.push(t.to_string());
    }
    if t.contains("专项")
        || t.contains("危大")
        || t.contains("临边")
        || low.contains("method statement")
        || low.contains("working at height")
        || low.contains("work at height")
        || low.contains("work-at-height")
    {
        facts.specials.push(t.to_string());
    }
}

fn quality_price_weight(t: &str) -> bool {
    let low = t.to_ascii_lowercase();
    let has_pct = t.contains('%') || t.contains('％');
    has_pct
        && (low.contains("quality")
            || low.contains("price")
            || t.contains("质量")
            || t.contains("价格")
            || t.contains("商务"))
}

fn parse_score_row(t: &str) -> Option<ScoreRow> {
    if t.contains('|') && t.matches('|').count() >= 2 && !t.contains("---") {
        let cells: Vec<&str> = t.split('|').map(|c| c.trim()).filter(|c| !c.is_empty()).collect();
        if cells.len() >= 2 && (cells[1].contains('%') || cells[1].contains('分') || cells[1].contains('％')) {
            return Some(ScoreRow {
                label: cells[0].to_string(),
                weight: cells[1].to_string(),
                source: t.to_string(),
            });
        }
    }
    let re = score_pair_re();
    if let Some(c) = re.captures(t) {
        let label = c.get(1)?.as_str().trim();
        let weight = c.get(2)?.as_str().trim();
        if label.is_empty() {
            return None;
        }
        return Some(ScoreRow {
            label: label.to_string(),
            weight: weight.to_string(),
            source: t.to_string(),
        });
    }
    None
}

fn score_pair_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(
            r"(?i)(quality|price|技术标|商务标|质量|价格|商务)\s*[:：]?\s*(\d+(?:\.\d+)?\s*[%％分]?)",
        )
        .unwrap()
    })
}

fn workhead_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"\b((?:CW|CR|ME|MW|SY|RW)\d{2})\b").unwrap())
}

fn workheads_in(t: &str) -> Vec<String> {
    workhead_re()
        .captures_iter(t)
        .filter_map(|c| c.get(1).map(|m| format!("{} · {}", m.as_str(), t)))
        .collect()
}

fn is_envelope(t: &str) -> bool {
    let low = t.to_ascii_lowercase();
    low.contains("two envelope")
        || low.contains("two-envelope")
        || t.contains("双信封")
        || t.contains("技术方案与报价分投")
}

fn parse_price_item(t: &str) -> Option<PriceItem> {
    let low = t.to_ascii_lowercase();
    let looks = low.contains("item")
        || t.contains("工程量")
        || low.contains("qty")
        || low.starts_with("boq")
        || (low.contains("drainage") && t.chars().any(|c| c.is_ascii_digit()));
    if !looks {
        return None;
    }
    if is_envelope(t) || quality_price_weight(t) {
        return None;
    }
    let unit = unit_in(t).unwrap_or_else(|| "[A001]".into());
    let qty = qty_in(t).unwrap_or_else(|| "[A001]".into());
    Some(PriceItem {
        line: t.to_string(),
        unit,
        qty,
    })
}

fn unit_in(t: &str) -> Option<String> {
    let re = Regex::new(r"(?i)\b(m2|m3|lm|nr|no\.?|lot|sum|kg|ton|m|项|米|立方米)\b").ok()?;
    re.find(t).map(|m| m.as_str().to_string())
}

fn qty_in(t: &str) -> Option<String> {
    let re = Regex::new(r"\b(\d+(?:\.\d+)?)\b").ok()?;
    let nums: Vec<_> = re.find_iter(t).map(|m| m.as_str()).collect();
    nums.last().map(|s| s.to_string())
}

fn dedup_score_rows(rows: Vec<ScoreRow>) -> Vec<ScoreRow> {
    let mut seen = std::collections::HashSet::new();
    let mut out = Vec::new();
    for r in rows {
        let key = format!("{}|{}", r.label.to_ascii_lowercase(), r.weight);
        if seen.insert(key) {
            out.push(r);
        }
    }
    out
}

fn dedup_price(items: Vec<PriceItem>) -> Vec<PriceItem> {
    let mut seen = std::collections::HashSet::new();
    let mut out = Vec::new();
    for i in items {
        if seen.insert(i.line.clone()) {
            out.push(i);
        }
    }
    out
}

fn days_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"(?i)\b\d+\s*(?:calendar\s*)?days?\b").unwrap())
}

fn dedup(items: Vec<String>) -> Vec<String> {
    let mut seen = std::collections::HashSet::new();
    let mut out = Vec::new();
    for i in items {
        if seen.insert(i.clone()) {
            out.push(i);
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn itt_table_weights_and_method_statement() {
        let t = "\
INVITATION TO TENDER\n\
Evaluation criteria (PQM):\n\
- Quality 40%\n\
- Price 60%\n\
Tenderers shall submit a method statement for working at height and a 临边防护专项方案.\n\
Time for Completion: 180 days\n\
BCA workhead CW01";
        let f = facts_from_text(t);
        assert!(
            f.scores.iter().any(|s| s.contains("Quality 40%")),
            "{:?}",
            f.scores
        );
        assert!(
            f.scores.iter().any(|s| s.contains("Price 60%")),
            "{:?}",
            f.scores
        );
        assert!(
            f.specials.iter().any(|s| s.contains("临边防护专项方案")),
            "{:?}",
            f.specials
        );
        assert!(
            f.duration.iter().any(|s| s.contains("180")),
            "{:?}",
            f.duration
        );
        assert!(f.quals.iter().any(|s| s.contains("CW01")), "{:?}", f.quals);
        assert!(
            f.score_rows.iter().any(|r| r.label.to_ascii_lowercase() == "quality" && r.weight.contains("40")),
            "{:?}",
            f.score_rows
        );
        assert!(f.workheads.iter().any(|w| w.contains("CW01")), "{:?}", f.workheads);
    }

    #[test]
    fn structured_envelope_workhead_and_boq_line() {
        let t = "\
Two Envelope: technical and price separately\n\
BCA workhead CW01 required\n\
Item 1 Drainage m 120\n\
Quality 40%";
        let f = facts_from_text(t);
        assert!(f.envelope.iter().any(|s| s.contains("Two Envelope")), "{:?}", f.envelope);
        assert!(f.workheads.iter().any(|w| w.contains("CW01")), "{:?}", f.workheads);
        assert!(
            f.price_items.iter().any(|p| p.line.contains("Drainage") && p.qty.contains("120")),
            "{:?}",
            f.price_items
        );
        assert!(f.score_rows.iter().any(|r| r.weight.contains("40")), "{:?}", f.score_rows);
    }
}