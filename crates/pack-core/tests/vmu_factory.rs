//! VMU factory ticket: 1.1m + 2m racks → 2×40HQ.
//! Mirrors scripts/test_rack_fold_vmu.py.

use pack_core::inspect_file;
use std::path::PathBuf;

fn vmu_path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .join("data")
        .join("samples")
        .join("vmu-fst-iron-sample.xlsx")
}

#[test]
fn vmu_two_cabinets_after_rack_fold() {
    let path = vmu_path();
    assert!(path.is_file(), "missing {}", path.display());
    let r = inspect_file(&path).expect("inspect VMU");
    assert!(r.folded, "expected rack titles on 装货单 sheets");
    let n11 = r.rack_n("1.1米铁架");
    let n2 = r.rack_n("2米铁架");
    eprintln!("racks 1.1m={n11} 2m={n2} notes={:?}", r.notes);
    assert!((12..=36).contains(&n11), "1.1m racks {n11}");
    assert!((4..=14).contains(&n2), "2m racks {n2}");
    let b = r.booking.expect("N0 after fold");
    eprintln!("{}", b.note);
    assert_eq!(b.n_weight, 2, "weight cabinets vs factory 2: {b:?}");
    assert!(b.n_geom_slot < 20, "slot exploded: {b:?}");
    assert_eq!(b.n0, 2, "N0* should match factory 2 cabinets: {b:?}");
}
