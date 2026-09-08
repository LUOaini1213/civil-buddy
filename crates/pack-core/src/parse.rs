use crate::dim::{parse_dim_cell, to_mm};
use calamine::{open_workbook_auto, Data, Reader};
use serde::Serialize;
use std::path::Path;

#[derive(Debug, Clone, Serialize)]
pub struct Material {
    pub id: String,
    pub name: String,
    pub qty: u32,
    pub length_mm: f64,
    pub width_mm: f64,
    pub height_mm: f64,
    pub weight_kg: f64,
    pub total_weight_kg: f64,
    #[serde(default = "default_true")]
    pub stackable: bool,
    #[serde(default)]
    pub prefer_bottom: bool,
}

#[allow(dead_code)]
fn default_true() -> bool {
    true
}

impl Material {
    pub fn has_lwh(&self) -> bool {
        self.length_mm > 0.0 && self.width_mm > 0.0 && self.height_mm > 0.0
    }

    pub fn total_kg(&self) -> f64 {
        if self.total_weight_kg > 0.0 {
            self.total_weight_kg
        } else {
            self.weight_kg * self.qty.max(1) as f64
        }
    }

    pub fn cbm(&self) -> f64 {
        if !self.has_lwh() {
            return 0.0;
        }
        self.length_mm * self.width_mm * self.height_mm * self.qty.max(1) as f64 / 1e9
    }

    pub fn explode(&self) -> Vec<Material> {
        let q = self.qty.max(1);
        let unit = if self.weight_kg > 0.0 {
            self.weight_kg
        } else {
            self.total_kg() / q as f64
        };
        (0..q)
            .map(|i| Material {
                id: if q > 1 {
                    format!("{}-{:03}", self.id, i + 1)
                } else {
                    self.id.clone()
                },
                name: self.name.clone(),
                qty: 1,
                length_mm: self.length_mm,
                width_mm: self.width_mm,
                height_mm: self.height_mm,
                weight_kg: unit,
                total_weight_kg: unit,
                stackable: self.stackable,
                prefer_bottom: self.prefer_bottom,
            })
            .collect()
    }
}

fn cell_text(v: &Data) -> String {
    match v {
        Data::Empty => String::new(),
        Data::String(s) => s.trim().to_string(),
        Data::Float(f) => {
            if f.fract() == 0.0 {
                format!("{}", *f as i64)
            } else {
                f.to_string()
            }
        }
        Data::Int(i) => i.to_string(),
        Data::Bool(b) => b.to_string(),
        Data::DateTime(dt) => format!("{dt:?}"),
        Data::DateTimeIso(s) | Data::DurationIso(s) => s.clone(),
        Data::Error(e) => format!("{e:?}"),
    }
}

fn cell_num(v: &Data) -> Option<f64> {
    match v {
        Data::Float(f) => Some(*f),
        Data::Int(i) => Some(*i as f64),
        Data::String(s) => {
            let cleaned: String = s.chars().filter(|c| c.is_ascii_digit() || *c == '.' || *c == '-').collect();
            if cleaned.is_empty() || cleaned == "-" || cleaned == "." {
                None
            } else {
                cleaned.parse().ok()
            }
        }
        _ => None,
    }
}

fn norm(s: &str) -> String {
    s.to_lowercase()
        .replace('\n', " ")
        .replace("&amp;", "&")
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
}

fn is_header_row(cells: &[String]) -> bool {
    let blob = cells.join(" ").to_lowercase();
    if blob.len() < 8 {
        return false;
    }
    let has_name = ["description", "content", "品名", "货物", "sku", "名称"]
        .iter()
        .any(|k| blob.contains(k));
    let has_dim = ["dimension", "l (cm)", "l cm", "length", "measurement", "长", "lwh"]
        .iter()
        .any(|k| blob.contains(k));
    let has_wt = ["weight", "gross", "净重", "毛重", "kg", "单重"]
        .iter()
        .any(|k| blob.contains(k));
    let has_qty = ["qty", "quantity", "packages", "cartons", "数量", "箱数", "件数"]
        .iter()
        .any(|k| blob.contains(k));
    has_name && (has_dim || (has_wt && has_qty))
}

#[derive(Default)]
struct Cols {
    id: Option<usize>,
    name: Option<usize>,
    qty: Option<usize>,
    length: Option<usize>,
    width: Option<usize>,
    height: Option<usize>,
    dimension: Option<usize>,
    weight: Option<usize>,
    total_weight: Option<usize>,
    weight_hdr: String,
    length_hdr: String,
}

fn map_headers(headers: &[String]) -> Cols {
    let mut c = Cols::default();
    // Prefer exact 长/宽/高 over 宽度W/高度H (section size, often empty).
    let exact: Vec<String> = headers.iter().map(|h| h.trim().to_string()).collect();
    if let (Some(li), Some(wi), Some(hi)) = (
        exact.iter().position(|h| h == "长"),
        exact.iter().position(|h| h == "宽"),
        exact.iter().position(|h| h == "高"),
    ) {
        c.length = Some(li);
        c.width = Some(wi);
        c.height = Some(hi);
        c.length_hdr = "长".into();
    }
    for (i, raw) in headers.iter().enumerate() {
        let h = norm(raw);
        if h.is_empty() {
            continue;
        }
        if h.contains("qty per carton") || h.contains("quantity per carton") || h.contains("units per")
        {
            continue;
        }
        if matches!(h.as_str(), "cartons" | "packages" | "箱数" | "件数")
            || h.starts_with("kind & no")
        {
            c.qty = Some(i);
            continue;
        }
        if matches!(h.as_str(), "qty" | "qty." | "q'ty" | "quantity" | "数量") && c.qty.is_none() {
            c.qty = Some(i);
            continue;
        }
        if [
            "description of goods",
            "goods description",
            "content",
            "description",
            "品名",
            "货物名称",
            "名称",
        ]
        .iter()
        .any(|k| h == *k || h.contains(k))
        {
            c.name.get_or_insert(i);
            continue;
        }
        if matches!(
            h.as_str(),
            "sku" | "item" | "s.no." | "s.no" | "package no." | "package no" | "carton no." | "序号"
        ) {
            c.id.get_or_insert(i);
            continue;
        }
        if matches!(
            h.as_str(),
            "l cm" | "l (cm)" | "l(cm)" | "length" | "length (cm)" | "长" | "长度"
        ) {
            if c.length.is_none() {
                c.length = Some(i);
                c.length_hdr = h;
            }
            continue;
        }
        if matches!(
            h.as_str(),
            "w cm" | "w (cm)" | "w(cm)" | "width" | "width (cm)" | "宽" | "宽度"
        ) {
            c.width.get_or_insert(i);
            continue;
        }
        if matches!(
            h.as_str(),
            "h cm" | "h (cm)" | "h(cm)" | "height" | "height (cm)" | "高" | "高度"
        ) {
            c.height.get_or_insert(i);
            continue;
        }
        if h.contains("dimension") || h.contains("measurement") {
            c.dimension.get_or_insert(i);
            continue;
        }
        if [
            "gross kg / carton",
            "gross kg/carton",
            "gross wt",
            "gross weight",
            "毛重",
            "单重",
            "单件重量",
            "重量",
        ]
        .iter()
        .any(|k| h.contains(k))
        {
            c.weight.get_or_insert(i);
            c.weight_hdr = h;
            continue;
        }
        if h.contains("total gross") || h.contains("总重") {
            c.total_weight.get_or_insert(i);
        }
    }
    c
}

fn is_summary(id: &str, name: &str) -> bool {
    let a = id.to_lowercase();
    let b = name.to_lowercase();
    ["total", "totals", "合计", "总计", "小计", "汇总"]
        .iter()
        .any(|k| a == *k || b == *k)
}

fn extract_sheet(sheet_name: &str, rows: &[Vec<Data>]) -> Option<Extracted> {
    let texts: Vec<Vec<String>> = rows
        .iter()
        .map(|r| r.iter().map(cell_text).collect())
        .collect();
    let hdr_i = texts.iter().take(40).position(|r| is_header_row(r))?;
    let headers = &texts[hdr_i];
    let cols = map_headers(headers);
    let mut materials = Vec::new();
    for row in rows.iter().skip(hdr_i + 1) {
        let at = |idx: Option<usize>| idx.and_then(|i| row.get(i));
        let name = at(cols.name).map(cell_text).unwrap_or_default();
        let id = at(cols.id).map(cell_text).unwrap_or_default();
        if is_summary(&id, &name) {
            break;
        }
        if name.is_empty() {
            continue;
        }
        let qty_n = at(cols.qty).and_then(cell_num);
        let wt = at(cols.weight).and_then(cell_num);
        let tw = at(cols.total_weight).and_then(cell_num);
        let has_dim_val = cols
            .dimension
            .and_then(|i| row.get(i))
            .map(|c| !cell_text(c).is_empty())
            .unwrap_or(false)
            || at(cols.length).and_then(cell_num).unwrap_or(0.0) > 0.0;
        if !has_dim_val && wt.unwrap_or(0.0) <= 0.0 && tw.unwrap_or(0.0) <= 0.0 && qty_n.unwrap_or(0.0) <= 0.0
        {
            continue;
        }

        let mut lwh = None;
        if let (Some(li), Some(wi), Some(hi)) = (cols.length, cols.width, cols.height) {
            if let (Some(l), Some(w), Some(h)) = (
                row.get(li).and_then(cell_num),
                row.get(wi).and_then(cell_num),
                row.get(hi).and_then(cell_num),
            ) {
                if l > 0.0 && w > 0.0 && h > 0.0 {
                    let hdr = cols.length_hdr.as_str();
                    let unit = if hdr.contains("cm") && !hdr.contains("mm") {
                        "cm"
                    } else if hdr.contains("mm") || hdr == "长" || hdr == "长度" {
                        "mm"
                    } else if hdr.contains("inch") {
                        "in"
                    } else {
                        // no unit in header: mid<=25 → m, else mm (same as table_mapper)
                        if l <= 25.0 && w <= 25.0 && h <= 25.0 {
                            "m"
                        } else {
                            "mm"
                        }
                    };
                    lwh = Some((to_mm(l, unit), to_mm(w, unit), to_mm(h, unit)));
                }
            }
        }
        if lwh.is_none() {
            if let Some(idx) = cols.dimension {
                if let Some(d) = row.get(idx).map(cell_text).as_deref().and_then(parse_dim_cell) {
                    lwh = Some((d.l_mm, d.w_mm, d.h_mm));
                }
            }
        }
        let (length_mm, width_mm, height_mm) = lwh.unwrap_or((0.0, 0.0, 0.0));
        let qty = qty_n.filter(|q| *q > 0.0).map(|q| q as u32).unwrap_or(1);
        let per_piece = cols.weight_hdr.contains("per carton")
            || cols.weight_hdr.contains("/ carton")
            || cols.weight_hdr.contains("/carton")
            || cols.weight_hdr.contains("单重");
        let (weight_kg, total_weight_kg) = match (wt, tw) {
            (Some(u), Some(t)) => (u, t),
            (Some(u), None) if per_piece || qty == 1 => (u, u * qty as f64),
            (Some(u), None) => (u / qty as f64, u),
            (None, Some(t)) => (t / qty as f64, t),
            _ => (0.0, 0.0),
        };
        materials.push(Material {
            id: format!("{}-{:03}", sanitize_sheet(sheet_name), materials.len() + 1),
            name,
            qty,
            length_mm,
            width_mm,
            height_mm,
            weight_kg,
            total_weight_kg,
            stackable: true,
            prefer_bottom: false,
        });
    }
    if materials.is_empty() {
        return None;
    }
    let title_blob = {
        let mut blob = sheet_name.to_string();
        blob.push(' ');
        for row in texts.iter().take(8) {
            blob.push_str(&row.join(" "));
            blob.push(' ');
        }
        blob
    };
    Some(Extracted {
        sheet: sheet_name.to_string(),
        header_row: hdr_i + 1,
        title_blob,
        materials,
    })
}

fn sanitize_sheet(name: &str) -> String {
    name.chars()
        .map(|c| if c.is_whitespace() { '-' } else { c })
        .collect()
}

#[derive(Debug, Clone)]
pub struct Extracted {
    pub sheet: String,
    pub header_row: usize,
    pub title_blob: String,
    pub materials: Vec<Material>,
}

/// Every worksheet that looks like a packing list (not just the densest one).
pub fn extract_all_sheets(path: &Path) -> Result<Vec<Extracted>, String> {
    let mut wb = open_workbook_auto(path).map_err(|e| format!("open {}: {e}", path.display()))?;
    let names = wb.sheet_names().to_vec();
    let mut out = Vec::new();
    for name in names {
        let Ok(range) = wb.worksheet_range(&name) else {
            continue;
        };
        let rows: Vec<Vec<Data>> = range.rows().map(|r| r.to_vec()).collect();
        if let Some(got) = extract_sheet(&name, &rows) {
            out.push(got);
        }
    }
    if out.is_empty() {
        Err(format!("no packing-list table in {}", path.display()))
    } else {
        Ok(out)
    }
}

pub fn extract_workbook(path: &Path) -> Result<Extracted, String> {
    let mut all = extract_all_sheets(path)?;
    all.sort_by_key(|g| {
        std::cmp::Reverse(g.materials.iter().filter(|m| m.has_lwh()).count() * 10 + g.materials.len())
    });
    Ok(all.remove(0))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn header_detects_dpx() {
        let row = vec![
            "Package No.".into(),
            "Content".into(),
            "Dimension".into(),
            "Gross Weight (kg)".into(),
        ];
        assert!(is_header_row(&row));
    }
}
