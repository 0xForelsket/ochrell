use ochrell::{
    conversion::delta_e_ok100,
    palette::{synthetic_four, AmountBasis, Palette, PaletteMetadataN, PaletteN, MAX_PAINTS},
    palette_match::ColorMatcherN,
    Color,
};

fn fixture<const N: usize>() -> PaletteN<N> {
    let names: [String; N] = std::array::from_fn(|i| format!("paint-{i}"));
    let base = synthetic_four();
    PaletteN::from_optics(
        PaletteMetadataN {
            id: "test-only-many-paints",
            paint_names: std::array::from_fn(|i| names[i].as_str()),
            amount_basis: AmountBasis::Relative,
            provenance: "Synthetic test coefficients; not measured Old Holland paints",
        },
        std::array::from_fn(|b| {
            std::array::from_fn(|i| {
                base.absorption()[b][i % 4] * (1. + 0.4 * (i / 4) as f64) + 0.004 * i as f64
            })
        }),
        std::array::from_fn(|b| {
            std::array::from_fn(|i| base.scattering()[b][i % 4] * (1. + 0.1 * i as f64))
        }),
    )
    .unwrap()
}

#[test]
fn all_eight_materials_contribute_and_grouped_amounts_survive_storage() {
    let p = fixture::<8>();
    assert_eq!(p.paint_count(), 8);
    let amounts = [1., 2., 3., 4., 5., 6., 7., 8.];
    let all = p.recipe(amounts).unwrap();
    // Independently evaluate the defining K-M equation with all eight inputs.
    for (b, r) in all.reflectance().iter().enumerate() {
        let k: f64 = (0..8).map(|i| amounts[i] * p.absorption()[b][i]).sum();
        let s: f64 = (0..8).map(|i| amounts[i] * p.scattering()[b][i]).sum();
        let q = k / s;
        let expected = 1. / (1. + q + (q * q + 2. * q).sqrt());
        assert!((r - expected).abs() < 1e-14);
    }
    let first = p.recipe([1., 2., 3., 4., 0., 0., 0., 0.]).unwrap();
    let last = p.recipe([0., 0., 0., 0., 5., 6., 7., 8.]).unwrap();
    let grouped = ochrell::palette::RecipeN::weighted(&[(first, 10.), (last, 26.)]).unwrap();
    for (a, b) in all.proportions().into_iter().zip(grouped.proportions()) {
        assert!((a - b).abs() < 1e-15);
    }
    for i in 0..8 {
        let pure = p.paint(&format!("paint-{i}")).unwrap();
        assert_eq!(pure.proportions()[i], 1.);
        let expected = all.interpolate(pure, 0.3).unwrap();
        let loaded = p.recipe_from_bytes(&all.to_bytes()).unwrap();
        assert_eq!(
            expected.to_bytes(),
            loaded.interpolate(pure, 0.3).unwrap().to_bytes()
        );
    }
    assert_ne!(first.decode_linear(), last.decode_linear());
}

#[test]
fn package_and_recipe_versions_enforce_count_identity_and_exact_roundtrip() {
    let p = fixture::<8>();
    let package = p.to_bytes();
    assert_eq!(&package[..4], b"OPP2");
    let loaded = PaletteN::<8>::from_bytes(&package).unwrap();
    assert_eq!(package, loaded.to_bytes());
    assert_eq!(p.fingerprint(), loaded.fingerprint());
    assert!(Palette::from_bytes(&package).is_err());
    assert!(PaletteN::<7>::from_bytes(&package).is_err());
    let r = p.recipe([1., 2., 3., 4., 5., 6., 7., 8.]).unwrap();
    let bytes = r.to_bytes();
    assert_eq!(&bytes[..4], b"OPR2");
    assert_eq!(bytes.len(), 104);
    let restored = loaded.recipe_from_bytes(&bytes).unwrap();
    assert_eq!(bytes, restored.to_bytes());
    assert_eq!(r.decode_linear(), restored.decode_linear());
    for size in [0, 4, 39, bytes.len() - 1] {
        assert!(loaded.recipe_from_bytes(&bytes[..size]).is_err());
    }
    for (offset, replacement) in [
        (4, 7_u64.to_le_bytes()),
        (40, f64::NAN.to_le_bytes()),
        (96, (-1_f64).to_le_bytes()),
    ] {
        let mut bad = bytes.clone();
        bad[offset..offset + 8].copy_from_slice(&replacement);
        assert!(loaded.recipe_from_bytes(&bad).is_err());
    }
    let other = fixture::<7>();
    assert!(other.recipe_from_bytes(&bytes).is_err());
    let old = synthetic_four();
    assert_eq!(&old.to_bytes()[..4], b"OPP1");
    let old_recipe = old.recipe([1., 2., 3., 4.]).unwrap();
    assert_eq!(old_recipe.to_bytes(), old_recipe.to_le_bytes());
    assert!(p.recipe_from_bytes(&old_recipe.to_bytes()).is_err());
}

#[test]
fn supported_counts_and_eighth_component_inputs_are_checked() {
    for p in [
        fixture::<1>().paint_count(),
        fixture::<5>().paint_count(),
        fixture::<10>().paint_count(),
        fixture::<16>().paint_count(),
    ] {
        assert!((1..=MAX_PAINTS).contains(&p));
    }
    assert!(PaletteN::<0>::from_optics(
        PaletteMetadataN {
            id: "empty",
            paint_names: [],
            amount_basis: AmountBasis::Relative,
            provenance: "Test",
        },
        [[]; 81],
        [[]; 81]
    )
    .is_err());
    assert!(PaletteN::<17>::from_optics(
        PaletteMetadataN {
            id: "oversized",
            paint_names: ["paint"; 17],
            amount_basis: AmountBasis::Relative,
            provenance: "Test",
        },
        [[1.; 17]; 81],
        [[1.; 17]; 81]
    )
    .is_err());
    let p = fixture::<8>();
    for bad in [f64::NAN, f64::INFINITY, -1.] {
        let mut amounts = [1.; 8];
        amounts[7] = bad;
        assert!(p.recipe(amounts).is_err());
    }
    assert_eq!(p.recipe([f64::MAX; 8]).unwrap().proportions(), [0.125; 8]);
}

#[test]
fn larger_palette_matchers_report_actual_error_and_are_deterministic() {
    matching::<8>();
    matching::<10>();
    matching::<16>();
}

fn matching<const N: usize>() {
    let p = fixture::<N>();
    let matcher = ColorMatcherN::new(&p).unwrap();
    let mut state = 271828_u32;
    let mut targets: Vec<_> = p
        .paint_names()
        .iter()
        .map(|n| p.paint(n).unwrap().decode())
        .collect();
    for _ in 0..64 {
        let amounts = std::array::from_fn(|_| {
            state ^= state << 13;
            state ^= state >> 17;
            state ^= state << 5;
            state as f64 / u32::MAX as f64
        });
        targets.push(p.recipe(amounts).unwrap().decode());
    }
    for target in targets {
        let found = matcher.match_color(target).unwrap();
        assert!(found.error_ok100 < 0.1, "{}", found.error_ok100);
        assert!(found.evaluations <= 24000);
        assert!(
            (found.error_ok100 - delta_e_ok100(found.achieved_linear, target.linear())).abs()
                < 1e-10
        );
        assert_eq!(
            found.recipe.to_bytes(),
            matcher.match_color(target).unwrap().recipe.to_bytes()
        );
    }
    let black = matcher.match_color(Color::srgb8(0, 0, 0)).unwrap();
    assert!(black.error_ok100 > 0.1);
    assert_eq!(black.recipe.palette().paint_count(), N);
}
