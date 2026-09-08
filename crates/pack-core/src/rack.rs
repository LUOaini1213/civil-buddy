//! Fold packing-list pieces into named factory racks (payload FFD).

use crate::parse::Material;
use regex::Regex;
use serde::Serialize;
use std::sync::OnceLock;

#[derive(Debug, Clone, Copy)]
pub struct RackSpec {
    pub label: &'static str,
    pub l_mm: f64,
    pub w_mm: f64,
    pub h_mm: f64,
    pub payload_kg: f64,
    pub tare_kg: f64,
}

impl RackSpec {
    pub fn outer_m3(self) -> f64 {
        self.l_mm * self.w_mm * self.h_mm / 1e9
    }
}

/// Same numbers as knowledge/packing_knowledge_base.json box_types.
pub fn rack_spec(label: &str) -> Option<RackSpec> {
    match label {
        "1.1米铁架" => Some(RackSpec {
            label: "1.1米铁架",
            l_mm: 1100.0,
            w_mm: 1100.0,
            h_mm: 1500.0,
            payload_kg: 1200.0,
            tare_kg: 90.0,
        }),
        "2米铁架" => Some(RackSpec {
            label: "2米铁架",
            l_mm: 2000.0,
            w_mm: 1100.0,
            h_mm: 1750.0,
            payload_kg: 2500.0,
            tare_kg: 120.0,
        }),
        "4米铁架" => Some(RackSpec {
            label: "4米铁架",
            l_mm: 4000.0,
            w_mm: 1100.0,
            h_mm: 1750.0,
            payload_kg: 3500.0,
            tare_kg: 180.0,
        }),
        "6米铁架" => Some(RackSpec {
            label: "6米铁架",
            l_mm: 6000.0,
            w_mm: 1100.0,
            h_mm: 1550.0,
            payload_kg: 4000.0,
            tare_kg: 251.0,
        }),
        _ => None,
    }
}

pub fn detect_rack_type(text: &str) -> Option<&'static str> {
    static PATS: OnceLock<Vec<(Regex, &'static str)>> = OnceLock::new();
    let pats = PATS.get_or_init(|| {
        vec![
            (
                Regex::new(r"1\s*\.?\s*1\s*米\s*(铁架|框)").unwrap(),
                "1.1米铁架",
            ),
            (Regex::new(r"2\s*米\s*(铁架|框)").unwrap(), "2米铁架"),
            (Regex::new(r"4\s*米\s*(铁架|框)").unwrap(), "4米铁架"),
            (Regex::new(r"6\s*米\s*(铁架|框)").unwrap(), "6米铁架"),
        ]
    });
    for (re, name) in pats {
        if re.is_match(text) {
            return Some(*name);
        }
    }
    None
}

#[derive(Debug, Clone, Serialize)]
pub struct FoldedRacks {
    pub rack_type: String,
    pub racks: Vec<Material>,
    pub skipped_incomplete: usize,
    pub note: String,
}

/// Split one titled packing-list group into payload-sized racks.
/// Heavier lines first (FFD) — same as Python rack_fold.
pub fn fold_group(materials: &[Material], rack_type: &str) -> Result<FoldedRacks, String> {
    let spec = rack_spec(rack_type).ok_or_else(|| format!("unknown rack type {rack_type}"))?;
    let mut complete: Vec<&Material> = materials.iter().filter(|m| m.has_lwh()).collect();
    let skipped = materials.len() - complete.len();
    complete.sort_by(|a, b| {
        b.total_kg()
            .partial_cmp(&a.total_kg())
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    let mut bins: Vec<Vec<&Material>> = Vec::new();
    let mut bin_w: Vec<f64> = Vec::new();
    for m in complete {
        let w = m.total_kg();
        let mut placed = false;
        for (i, rw) in bin_w.iter_mut().enumerate() {
            if *rw + w <= spec.payload_kg + 1e-6 {
                bins[i].push(m);
                *rw += w;
                placed = true;
                break;
            }
        }
        if !placed {
            bins.push(vec![m]);
            bin_w.push(w);
        }
    }
    let racks: Vec<Material> = bins
        .iter()
        .enumerate()
        .map(|(i, pieces)| seal_rack(pieces, spec, i + 1))
        .collect();
    Ok(FoldedRacks {
        rack_type: rack_type.to_string(),
        note: format!(
            "{}: {} lines → {} racks (dropped_incomplete={})",
            rack_type,
            materials.len(),
            racks.len(),
            skipped
        ),
        skipped_incomplete: skipped,
        racks,
    })
}

fn seal_rack(pieces: &[&Material], spec: RackSpec, index: usize) -> Material {
    let net: f64 = pieces.iter().map(|p| p.total_kg()).sum();
    let _content_m3: f64 = pieces.iter().map(|p| p.cbm()).sum();
    Material {
        id: format!("RACK-{}-{index:02}", spec.label),
        name: spec.label.to_string(),
        qty: 1,
        length_mm: spec.l_mm,
        width_mm: spec.w_mm,
        height_mm: spec.h_mm,
        weight_kg: net + spec.tare_kg,
        total_weight_kg: net + spec.tare_kg,
        stackable: true,
        prefer_bottom: net >= 2000.0 || spec.l_mm >= 4000.0,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn piece(id: &str, kg: f64) -> Material {
        Material {
            id: id.into(),
            name: "tube".into(),
            qty: 1,
            length_mm: 1400.0,
            width_mm: 250.0,
            height_mm: 250.0,
            weight_kg: kg,
            total_weight_kg: kg,
            stackable: true,
            prefer_bottom: false,
        }
    }

    #[test]
    fn detect_vmu_titles() {
        assert_eq!(
            detect_rack_type("1.1米铁架1号 4-8P 远东"),
            Some("1.1米铁架")
        );
        assert_eq!(detect_rack_type("2米铁架1号 远东"), Some("2米铁架"));
        assert_eq!(detect_rack_type("1.1米框1"), Some("1.1米铁架"));
        assert_eq!(detect_rack_type("PACKING LIST"), None);
    }

    #[test]
    fn ffd_splits_on_payload() {
        let mats = vec![piece("a", 800.0), piece("b", 700.0), piece("c", 500.0)];
        // 800+700 > 1200 → two or three 1.1m racks; 800+500=1300>1200; 700+500=1200 ok
        let folded = fold_group(&mats, "1.1米铁架").unwrap();
        assert!(folded.racks.len() >= 2);
        let net: f64 = folded.racks.iter().map(|r| r.total_kg() - 90.0).sum();
        assert!((net - 2000.0).abs() < 1e-6);
        assert!(folded.racks.iter().all(|r| r.total_kg() - 90.0 <= 1200.0 + 1e-6));
    }
}
