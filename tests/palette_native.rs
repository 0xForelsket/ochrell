use ochrell::palette::{AmountBasis, PaletteMetadataN, PaletteN};
use ochrell::palette_match::ColorMatcherN;

fn palette<const B: usize>(controls: Vec<[f64; 4]>) -> PaletteN<8, B> {
    PaletteN::from_optics_with_pair_correction(
        PaletteMetadataN {
            id: "native-window-fixture",
            paint_names: ["a", "b", "c", "d", "e", "f", "g", "h"],
            amount_basis: AmountBasis::Mass,
            provenance: "Synthetic analytic optics; no paint measurements",
        },
        [[1.; 8]; B],
        [[1.; 8]; B],
        controls,
    )
    .unwrap()
}

#[test]
fn native_window_and_last_pair_correction_follow_analytic_equation() {
    let base = palette::<31>(Vec::new());
    let mut controls = vec![[0.; 4]; 28];
    controls[27] = [0.4; 4];
    let corrected = palette::<31>(controls);
    assert_eq!(corrected.spectral_grid(), (400, 10, 31));
    let recipe = corrected.recipe([0., 0., 0., 0., 0., 0., 1., 1.]).unwrap();
    let r = 2. - 3_f64.sqrt();
    let expected = 1. / (1. + (-((r / (1. - r)).ln() + 0.4)).exp());
    for value in recipe.reflectance() {
        assert!((value - expected).abs() < 1e-14);
    }
    for name in corrected.paint_names() {
        assert_eq!(
            base.paint(name).unwrap().reflectance(),
            corrected.paint(name).unwrap().reflectance()
        );
    }
    assert_ne!(base.fingerprint(), corrected.fingerprint());
    assert!(base.recipe_from_bytes(&recipe.to_bytes()).is_err());
    let bytes = corrected.to_bytes();
    assert_eq!(&bytes[..4], b"OPP3");
    let loaded = PaletteN::<8, 31>::from_bytes(&bytes).unwrap();
    assert_eq!(bytes, loaded.to_bytes());
    assert_eq!(
        recipe.decode_linear(),
        loaded
            .recipe_from_bytes(&recipe.to_bytes())
            .unwrap()
            .decode_linear()
    );
    assert!(PaletteN::<8>::from_bytes(&bytes).is_err());
    assert!(PaletteN::<7, 31>::from_bytes(&bytes).is_err());
    let matcher = ColorMatcherN::new(&loaded).unwrap();
    assert!(matcher.match_color(recipe.decode()).unwrap().error_ok100 < 0.1);
}

#[test]
fn model_controls_and_supported_grids_are_checked() {
    let make = |controls| {
        PaletteN::<8, 31>::from_optics_with_pair_correction(
            PaletteMetadataN {
                id: "validation",
                paint_names: ["a", "b", "c", "d", "e", "f", "g", "h"],
                amount_basis: AmountBasis::Relative,
                provenance: "Test fixture",
            },
            [[1.; 8]; 31],
            [[1.; 8]; 31],
            controls,
        )
    };
    assert!(make(vec![[0.; 4]; 27]).is_err());
    for bad in [f64::NAN, f64::INFINITY, 0.8001, -0.8001] {
        let mut controls = vec![[0.; 4]; 28];
        controls[27][3] = bad;
        assert!(make(controls).is_err());
    }
    let meta = PaletteMetadataN {
        id: "grid",
        paint_names: ["x"],
        amount_basis: AmountBasis::Relative,
        provenance: "Fixture",
    };
    assert!(PaletteN::<1, 30>::from_optics(meta, [[1.; 1]; 30], [[1.; 1]; 30]).is_err());
    let full = palette::<81>(vec![[0.1; 4]; 28]);
    let bytes = full.to_bytes();
    assert_eq!(bytes, PaletteN::<8>::from_bytes(&bytes).unwrap().to_bytes());
    assert!(PaletteN::<8, 31>::from_bytes(&bytes).is_err());
}
