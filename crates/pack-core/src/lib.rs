//! Packing-list parse + rack fold + N0* booking lower bound.
//!
//! Tools compute. This crate does not talk to an LLM.

pub mod booking;
pub mod dim;
pub mod parse;
pub mod rack;

pub use booking::{compute_n0, Booking, ContainerSpec, HQ40};
pub use dim::{parse_dim_cell, to_mm, Dim};
pub use parse::{extract_all_sheets, extract_workbook, Material};
pub use rack::{detect_rack_type, fold_group, rack_spec};

use crate::rack::FoldedRacks;
use std::path::Path;

/// Open a workbook: every cargo sheet, fold titled racks, then N0* for 40HQ.
pub fn inspect_file(path: impl AsRef<Path>) -> Result<InspectReport, String> {
    let path = path.as_ref();
    let sheets = extract_all_sheets(path)?;
    let mut sheet_reports: Vec<SheetReport> = Vec::new();
    let mut folds: Vec<FoldedRacks> = Vec::new();

    for sh in &sheets {
        let rtype = detect_rack_type(&sh.title_blob).or_else(|| detect_rack_type(&sh.sheet));
        sheet_reports.push(SheetReport {
            sheet: sh.sheet.clone(),
            header_row: sh.header_row,
            lines: sh.materials.len(),
            packages: sh.materials.iter().map(|m| m.qty.max(1)).sum(),
            weight_kg: sh.materials.iter().map(|m| m.total_kg()).sum(),
            cbm: sh.materials.iter().map(|m| m.cbm()).sum(),
            complete_lwh: sh.materials.iter().filter(|m| m.has_lwh()).count(),
            rack_type: rtype.map(|s| s.to_string()),
        });
        if let Some(rt) = rtype {
            folds.push(fold_group(&sh.materials, rt)?);
        }
    }

    // Factory ticket: named rack sheets only. Web carton lists have no title → all sheets.
    let folded = !folds.is_empty();
    let cargo: Vec<&parse::Extracted> = if folded {
        sheets
            .iter()
            .filter(|sh| {
                detect_rack_type(&sh.title_blob)
                    .or_else(|| detect_rack_type(&sh.sheet))
                    .is_some()
            })
            .collect()
    } else {
        sheets.iter().collect()
    };
    let all_lines: Vec<Material> = cargo.iter().flat_map(|sh| sh.materials.iter().cloned()).collect();
    let boxes: Vec<Material> = if folded {
        folds.iter().flat_map(|f| f.racks.iter().cloned()).collect()
    } else {
        all_lines.iter().flat_map(|m| m.explode()).collect()
    };

    let booking = if boxes.iter().any(|b| b.has_lwh()) {
        Some(compute_n0(&boxes, HQ40))
    } else {
        None
    };

    let mut rack_counts: Vec<RackCount> = Vec::new();
    for f in &folds {
        rack_counts.push(RackCount {
            rack_type: f.rack_type.clone(),
            n: f.racks.len(),
            note: f.note.clone(),
        });
    }

    Ok(InspectReport {
        path: path.display().to_string(),
        sheets: sheet_reports,
        lines: all_lines.len(),
        packages: all_lines.iter().map(|m| m.qty.max(1)).sum(),
        weight_kg: if folded {
            boxes.iter().map(|b| b.total_kg()).sum()
        } else {
            all_lines.iter().map(|m| m.total_kg()).sum()
        },
        cbm: if folded {
            boxes.iter().map(|b| b.cbm()).sum()
        } else {
            all_lines.iter().map(|m| m.cbm()).sum()
        },
        complete_lwh: all_lines.iter().filter(|m| m.has_lwh()).count(),
        folded,
        rack_counts,
        n_boxes: boxes.len(),
        materials: all_lines,
        boxes,
        booking,
        notes: folds.iter().map(|f| f.note.clone()).collect(),
    })
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct SheetReport {
    pub sheet: String,
    pub header_row: usize,
    pub lines: usize,
    pub packages: u32,
    pub weight_kg: f64,
    pub cbm: f64,
    pub complete_lwh: usize,
    pub rack_type: Option<String>,
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct RackCount {
    pub rack_type: String,
    pub n: usize,
    pub note: String,
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct InspectReport {
    pub path: String,
    pub sheets: Vec<SheetReport>,
    pub lines: usize,
    pub packages: u32,
    pub weight_kg: f64,
    pub cbm: f64,
    pub complete_lwh: usize,
    pub folded: bool,
    pub rack_counts: Vec<RackCount>,
    pub n_boxes: usize,
    pub materials: Vec<Material>,
    pub boxes: Vec<Material>,
    pub booking: Option<Booking>,
    pub notes: Vec<String>,
}

impl InspectReport {
    pub fn rack_n(&self, label: &str) -> usize {
        self.rack_counts
            .iter()
            .filter(|r| r.rack_type == label)
            .map(|r| r.n)
            .sum()
    }
}

