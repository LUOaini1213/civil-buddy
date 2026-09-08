use regex::Regex;
use std::sync::OnceLock;

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Dim {
    pub l_mm: f64,
    pub w_mm: f64,
    pub h_mm: f64,
}

pub fn to_mm(value: f64, unit: &str) -> f64 {
    match unit.to_ascii_lowercase().as_str() {
        "in" | "inch" | "inches" => value * 25.4,
        "m" => value * 1000.0,
        "mm" => value,
        "cm" => value * 10.0,
        "" => {
            if value <= 300.0 {
                value * 10.0
            } else {
                value
            }
        }
        _ => value * 10.0,
    }
}

fn dim_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(
            r"(?i)(?P<l>\d+(?:\.\d+)?)\s*[xX×*]\s*(?P<w>\d+(?:\.\d+)?)\s*[xX×*]\s*(?P<h>\d+(?:\.\d+)?)\s*(?P<u>cm|mm|m|in|inch|inches)?",
        )
        .expect("dim regex")
    })
}

/// Parse combined cells like `20x30x25 cm` or `15 × 15 × 13 in`.
pub fn parse_dim_cell(text: &str) -> Option<Dim> {
    let cap = dim_re().captures(text)?;
    let l: f64 = cap.name("l")?.as_str().parse().ok()?;
    let w: f64 = cap.name("w")?.as_str().parse().ok()?;
    let h: f64 = cap.name("h")?.as_str().parse().ok()?;
    let mut unit = cap
        .name("u")
        .map(|m| m.as_str().to_ascii_lowercase())
        .unwrap_or_default();
    if unit.is_empty() {
        let low = text.to_ascii_lowercase();
        if low.contains("inch") || low.contains(" in") {
            unit = "in".into();
        } else if low.contains("mm") {
            unit = "mm".into();
        } else if low.contains("cm") {
            unit = "cm".into();
        }
    }
    Some(Dim {
        l_mm: to_mm(l, &unit),
        w_mm: to_mm(w, &unit),
        h_mm: to_mm(h, &unit),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_dpx_cm() {
        let d = parse_dim_cell("20x30x25 cm").unwrap();
        assert!((d.l_mm - 200.0).abs() < 1e-6);
        assert!((d.w_mm - 300.0).abs() < 1e-6);
        assert!((d.h_mm - 250.0).abs() < 1e-6);
    }

    #[test]
    fn parse_inches() {
        let d = parse_dim_cell("15 x 15 x 13 in").unwrap();
        assert!((d.l_mm - 381.0).abs() < 0.1);
    }
}
