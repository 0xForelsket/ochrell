use ochrell::{
    conversion::delta_e_ok100,
    palette::{synthetic_four, AmountBasis, Palette, PaletteError, PaletteMetadata},
    palette_lut::PaletteLut,
    palette_match::ColorMatcher,
    Color,
};

fn custom() -> Palette {
    let p = synthetic_four();
    let mut k = *p.absorption();
    let mut s = *p.scattering();
    for i in 0..81 {
        k[i][3] *= 2.;
        s[i][3] *= 2.;
    }
    Palette::from_optics(
        PaletteMetadata {
            id: "strong-white-demo",
            paint_names: p.paint_names(),
            amount_basis: AmountBasis::Relative,
            provenance: "Synthetic test palette with doubled white optical strength",
        },
        k,
        s,
    )
    .unwrap()
}

#[test]
fn packages_preserve_builtin_identity_and_custom_behavior() {
    let original = synthetic_four();
    let loaded = Palette::from_bytes(&original.to_bytes()).unwrap();
    assert_eq!(original.fingerprint(), loaded.fingerprint());
    let paint = original.recipe([1., 2., 3., 4.]).unwrap();
    assert_eq!(
        paint.to_le_bytes(),
        loaded
            .recipe_from_bytes(&paint.to_le_bytes())
            .unwrap()
            .to_le_bytes()
    );
    let lut = PaletteLut::build(original, 17).unwrap().into_owned();
    assert_eq!(
        lut.decode(&paint).unwrap(),
        lut.decode(&loaded.recipe([1., 2., 3., 4.]).unwrap())
            .unwrap()
    );
    assert!(paint
        .interpolate(loaded.paint("white").unwrap(), 0.3)
        .is_ok());
    let altered = custom();
    let roundtrip = Palette::from_bytes(&altered.to_bytes()).unwrap();
    assert_eq!(altered.to_bytes(), roundtrip.to_bytes());
    assert_ne!(original.fingerprint(), altered.fingerprint());
    assert_eq!(
        original.paint("white").unwrap().decode(),
        altered.paint("white").unwrap().decode()
    );
    assert_ne!(
        original.recipe([1., 0., 0., 1.]).unwrap().decode(),
        altered.recipe([1., 0., 0., 1.]).unwrap().decode()
    );
    assert_eq!(
        altered.recipe_from_bytes(&paint.to_le_bytes()).unwrap_err(),
        PaletteError::PaletteMismatch
    );
    assert!(lut.decode(&altered.paint("yellow").unwrap()).is_err());
}

#[test]
fn invalid_optics_metadata_and_packages_are_rejected() {
    let p = synthetic_four();
    let create = |k, s, names| {
        Palette::from_optics(
            PaletteMetadata {
                id: "test",
                paint_names: names,
                amount_basis: AmountBasis::Mass,
                provenance: "Test-only optical coefficients",
            },
            k,
            s,
        )
    };
    for bad in [f64::NAN, f64::INFINITY, -1., 1e101] {
        let mut k = *p.absorption();
        k[0][0] = bad;
        assert!(create(k, *p.scattering(), p.paint_names()).is_err());
    }
    for bad in [0., -1., f64::NAN, 1e101, 1e-101] {
        let mut s = *p.scattering();
        s[0][0] = bad;
        assert!(create(*p.absorption(), s, p.paint_names()).is_err());
    }
    assert!(create(*p.absorption(), *p.scattering(), ["a", "a", "b", "c"]).is_err());
    let mut bytes = p.to_bytes();
    for n in [0, 4, 51, 100, bytes.len() - 1] {
        assert!(Palette::from_bytes(&bytes[..n]).is_err());
    }
    bytes[200] ^= 1;
    assert_eq!(
        Palette::from_bytes(&bytes).unwrap_err(),
        PaletteError::InvalidChecksum
    );
    assert!(Palette::from_bytes(&vec![0; 20_000]).is_err());
}

#[test]
fn pure_targets_and_unreachable_colors_report_honest_errors() {
    let p = synthetic_four();
    let m = ColorMatcher::new(p).unwrap();
    for name in p.paint_names() {
        let target = p.paint(name).unwrap().decode();
        let result = m.match_color(target).unwrap();
        assert!(result.error_ok100 < 0.001, "{name}: {}", result.error_ok100);
        assert!(result.evaluations <= 24_000);
    }
    for target in [
        Color::srgb8(0, 0, 0),
        Color::srgb8(255, 255, 255),
        Color::srgb8(255, 0, 255),
    ] {
        let a = m.match_color(target).unwrap();
        let b = m.match_color(target).unwrap();
        assert_eq!(a.recipe.to_le_bytes(), b.recipe.to_le_bytes());
        assert_eq!(a.error_ok100, b.error_ok100);
        assert!(a.error_ok100 > 0.01);
        assert!((a.error_ok100 - delta_e_ok100(a.achieved_linear, target.linear())).abs() < 1e-10);
        assert_eq!(
            a.achieved_linear,
            ochrell::conversion::gamut_map(a.recipe.decode_linear())
        );
    }
    assert!(m.match_linear([f64::NAN, 0., 0.]).is_err());
    assert!(m.match_linear([-0.1, 0., 0.]).is_err());
    assert!(ColorMatcher::with_cbrt(p, |_| f64::NAN).is_err());
}

#[test]
fn reachable_holdout_targets_match_in_builtin_and_custom_palettes() {
    let c = custom();
    let m = ColorMatcher::new(synthetic_four()).unwrap();
    let other = ColorMatcher::new(&c).unwrap();
    let mut rng = 314159_u64;
    for index in 0..256 {
        let mut amounts = std::array::from_fn(|_| {
            rng ^= rng << 13;
            rng ^= rng >> 7;
            rng ^= rng << 17;
            (rng >> 11) as f64 / (1_u64 << 53) as f64
        });
        if index % 3 == 0 {
            amounts[index % 4] = 0.;
        }
        for matcher in [&m, &other] {
            let target = matcher.palette().recipe(amounts).unwrap().decode();
            let result = matcher.match_color(target).unwrap();
            assert!(
                result.error_ok100 <= 0.10,
                "recipe {amounts:?}: {} after {}",
                result.error_ok100,
                result.evaluations
            );
        }
    }
}
