use crate::parse::Material;
use serde::Serialize;

#[derive(Debug, Clone, Copy)]
pub struct ContainerSpec {
    pub name: &'static str,
    pub l_mm: f64,
    pub w_mm: f64,
    pub h_mm: f64,
    pub max_kg: f64,
    pub fill_ratio: f64,
    pub eta_floor: f64,
}

pub const HQ40: ContainerSpec = ContainerSpec {
    name: "40HQ",
    l_mm: 12032.0,
    w_mm: 2352.0,
    h_mm: 2698.0,
    max_kg: 28610.0,
    fill_ratio: 0.82,
    eta_floor: 0.88,
};

#[derive(Debug, Clone, Serialize)]
pub struct Booking {
    pub container: String,
    pub n0: u32,
    pub n_weight: u32,
    pub n_volume: u32,
    pub n_geom_floor: u32,
    pub n_geom_slot: u32,
    pub binding: String,
    pub note: String,
    pub volume_m3: f64,
    pub usable_m3: f64,
    pub weight_kg: f64,
}

fn ceil_div(num: f64, den: f64) -> u32 {
    if num <= 0.0 || den <= 0.0 {
        0
    } else {
        ((num / den) - 1e-9).ceil().max(1.0) as u32
    }
}

/// N0* = max(N_weight, N_volume, N_geom_floor, N_geom_slot).
pub fn compute_n0(boxes: &[Material], spec: ContainerSpec) -> Booking {
    let weight_kg: f64 = boxes.iter().map(|b| b.total_kg()).sum();
    let volume_m3: f64 = boxes.iter().map(|b| b.cbm()).sum();
    let usable = spec.l_mm * spec.w_mm * spec.h_mm / 1e9 * spec.fill_ratio;
    let n_weight = ceil_div(weight_kg, spec.max_kg);
    let n_volume = ceil_div(volume_m3, usable);

    let mut foot = 0.0;
    let mut floor_items = 0.0;
    let mut lengths = Vec::new();
    let mut widths = Vec::new();
    for b in boxes {
        if !b.has_lwh() {
            continue;
        }
        foot += b.length_mm * b.width_mm;
        lengths.push(b.length_mm);
        widths.push(b.width_mm);
        if !b.stackable
            || b.prefer_bottom
            || b.length_mm >= 4000.0
            || b.height_mm > 1500.0
            || b.weight_kg >= 2000.0
        {
            floor_items += 1.0;
        } else {
            floor_items += 0.45;
        }
    }
    let floor_area = (spec.l_mm * spec.w_mm * spec.eta_floor).max(1.0);
    let n_geom_floor = if foot > 0.0 {
        ceil_div(foot, floor_area)
    } else {
        0
    };

    lengths.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let mid_l = if lengths.is_empty() {
        2000.0
    } else {
        lengths[lengths.len() / 2]
    };
    let n_along = (spec.l_mm / mid_l.max(500.0)).floor().max(1.0);
    let half_ok = widths.iter().filter(|w| **w <= spec.w_mm * 0.5 + 80.0).count();
    let n_across = if widths.is_empty() || half_ok >= ((0.55 * widths.len() as f64) as usize).max(1) {
        2.0
    } else {
        1.0
    };
    let cap_floor = (n_along * n_across).max(1.0);
    let n_gs_raw = if floor_items > 0.0 {
        ceil_div(floor_items, cap_floor)
    } else {
        0
    };
    let base_geo = n_weight.max(n_volume).max(n_geom_floor).max(1);
    let n_gs_cap = base_geo.max(((base_geo as f64) * 1.30 + 2.0).ceil() as u32);
    let n_geom_slot = if n_gs_raw > 0 {
        n_gs_raw.min(n_gs_cap)
    } else {
        0
    };

    let n0 = n_weight.max(n_volume).max(n_geom_floor).max(n_geom_slot).max(1);
    let comps = [
        ("weight", n_weight),
        ("volume", n_volume),
        ("geom_floor", n_geom_floor),
        ("geom_slot", n_geom_slot),
    ];
    let top = comps.iter().max_by_key(|(_, v)| *v).unwrap();
    let ties = comps.iter().filter(|(_, v)| *v == top.1).count();
    let binding = if ties > 1 {
        "multi".to_string()
    } else {
        top.0.to_string()
    };

    Booking {
        container: spec.name.to_string(),
        n0,
        n_weight,
        n_volume,
        n_geom_floor,
        n_geom_slot,
        binding,
        note: format!(
            "N0*=max(wt={n_weight},vol={n_volume},floor={n_geom_floor},slot={n_geom_slot})={n0}"
        ),
        volume_m3,
        usable_m3: usable,
        weight_kg,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parse::Material;

    fn carton(l: f64, w: f64, h: f64, kg: f64, qty: u32) -> Material {
        Material {
            id: "c".into(),
            name: "carton".into(),
            qty,
            length_mm: l,
            width_mm: w,
            height_mm: h,
            weight_kg: kg,
            total_weight_kg: kg * qty as f64,
            stackable: true,
            prefer_bottom: false,
        }
    }

    #[test]
    fn dpx_two_books_one_hq() {
        let boxes = vec![
            carton(200.0, 300.0, 250.0, 4.5, 1),
            carton(150.0, 150.0, 300.0, 3.5, 1),
        ];
        let b = compute_n0(&boxes, HQ40);
        assert_eq!(b.n0, 1);
    }

    #[test]
    fn forty_totes_one_hq() {
        let exploded: Vec<_> = carton(600.0, 400.0, 350.0, 12.4, 40).explode();
        let b = compute_n0(&exploded, HQ40);
        assert_eq!(b.n0, 1);
        assert!((b.volume_m3 - 3.36).abs() < 0.01);
    }
}
