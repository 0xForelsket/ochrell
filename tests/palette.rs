use ochrell::palette::{synthetic_four, PaletteError, Recipe, RECIPE_BYTES};

fn close(a: [f64; 4], b: [f64; 4], tolerance: f64) {
    for (a, b) in a.into_iter().zip(b) {
        assert!((a - b).abs() <= tolerance, "{a} differs from {b}");
    }
}

#[test]
fn amounts_are_checked_and_normalized_without_overflow() {
    let p = synthetic_four();
    assert_eq!(p.paint_names(), &["yellow", "red", "blue", "white"]);
    assert_eq!(p.paint("missing").unwrap_err(), PaletteError::UnknownPaint);
    for bad in [f64::NAN, f64::INFINITY, f64::NEG_INFINITY, -1.] {
        assert_eq!(
            p.recipe([bad, 1., 1., 1.]).unwrap_err(),
            PaletteError::InvalidAmounts
        );
    }
    assert!(p.recipe([0.; 4]).is_err());
    for magnitude in [f64::from_bits(1), f64::MIN_POSITIVE, 1., f64::MAX] {
        assert_eq!(p.recipe([magnitude; 4]).unwrap().proportions(), [0.25; 4]);
    }
    assert_eq!(
        p.recipe([6., 0., 3., 1.]).unwrap().proportions(),
        p.recipe([60., 0., 30., 10.]).unwrap().proportions()
    );
    let a = p.paint("yellow").unwrap();
    let b = p.paint("blue").unwrap();
    assert_eq!(a.interpolate(b, 0.).unwrap().to_le_bytes(), a.to_le_bytes());
    assert_eq!(a.interpolate(b, 1.).unwrap().to_le_bytes(), b.to_le_bytes());
    for bad in [-0.1, 1.1, f64::NAN, f64::INFINITY] {
        assert_eq!(
            a.interpolate(b, bad).unwrap_err(),
            PaletteError::InvalidFraction
        );
    }
    assert!(Recipe::weighted(&[]).is_err());
    assert!(Recipe::weighted(&[(a, 0.)]).is_err());
    assert!(Recipe::weighted(&[(a, -1.), (b, 2.)]).is_err());
    assert!(Recipe::weighted(&[(a, f64::INFINITY)]).is_err());
    close(
        Recipe::weighted(&[(a, f64::MAX), (b, f64::MAX)])
            .unwrap()
            .proportions(),
        [0.5, 0., 0.5, 0.],
        0.,
    );
}

#[test]
fn grouping_carries_amounts_and_preserves_future_tints() {
    let p = synthetic_four();
    let [a, b, c, white] = ["yellow", "red", "blue", "white"].map(|n| p.paint(n).unwrap());
    let all = Recipe::weighted(&[(a, 2.), (b, 3.), (c, 5.)]).unwrap();
    let ab = Recipe::weighted(&[(a, 2.), (b, 3.)]).unwrap();
    let grouped = Recipe::weighted(&[(ab, 5.), (c, 5.)]).unwrap();
    close(all.proportions(), grouped.proportions(), 2e-16);
    let reversed = Recipe::weighted(&[(c, 5.), (b, 3.), (a, 2.)]).unwrap();
    close(all.proportions(), reversed.proportions(), 2e-16);
    assert_eq!(
        all.interpolate(white, 0.7).unwrap().decode(),
        grouped.interpolate(white, 0.7).unwrap().decode()
    );
    let equal_groups = Recipe::weighted(&[(ab, 1.), (c, 1.)]).unwrap();
    // Equal group votes only work when the groups have equal total amounts.
    close(grouped.proportions(), equal_groups.proportions(), 2e-16);
    let unequal = Recipe::weighted(&[(ab, 5.), (c, 2.)]).unwrap();
    assert!((unequal.proportions()[2] - 2. / 7.).abs() < 1e-15);
    assert!((unequal.proportions()[2] - equal_groups.proportions()[2]).abs() > 0.2);
}

#[test]
fn tiny_updates_survive_every_reload_and_match_closed_form() {
    let p = synthetic_four();
    let a = p.paint("yellow").unwrap();
    let b = p.paint("blue").unwrap();
    let white = p.paint("white").unwrap();
    let (mut direct, mut saved) = (a, a);
    let t = 0.0001;
    for _ in 0..4096 {
        direct = direct.interpolate(b, t).unwrap();
        saved = saved.interpolate(b, t).unwrap();
        let bytes = saved.to_le_bytes();
        saved = p.recipe_from_bytes(&bytes).unwrap();
        assert_eq!(saved.to_le_bytes(), bytes);
    }
    let remaining = (1_f64 - t).powi(4096);
    close(
        direct.proportions(),
        [remaining, 0., 1. - remaining, 0.],
        2e-12,
    );
    assert_eq!(direct.proportions(), saved.proportions());
    assert_eq!(
        direct.interpolate(white, 0.6).unwrap().decode(),
        saved.interpolate(white, 0.6).unwrap().decode()
    );
    assert!(saved.proportions()[2] > 0.3);
}

#[test]
fn persistence_rejects_bad_formats_palettes_and_components() {
    let p = synthetic_four();
    let recipe = p.recipe([2., 3., 4., 5.]).unwrap();
    let original = recipe.to_le_bytes();
    assert_eq!(original.len(), RECIPE_BYTES);
    for length in 0..RECIPE_BYTES {
        assert_eq!(
            p.recipe_from_bytes(&original[..length]).unwrap_err(),
            PaletteError::InvalidFormat
        );
    }
    let mut extra = original.to_vec();
    extra.push(0);
    assert!(p.recipe_from_bytes(&extra).is_err());
    let mut changed = original;
    changed[3] = b'2';
    assert_eq!(
        p.recipe_from_bytes(&changed).unwrap_err(),
        PaletteError::InvalidFormat
    );
    changed = original;
    changed[4] ^= 1;
    assert_eq!(
        p.recipe_from_bytes(&changed).unwrap_err(),
        PaletteError::PaletteMismatch
    );
    for value in [f64::NAN, f64::INFINITY, -0.1, 1.1, 0.9] {
        changed = original;
        changed[36..44].copy_from_slice(&value.to_le_bytes());
        assert_eq!(
            p.recipe_from_bytes(&changed).unwrap_err(),
            PaletteError::InvalidRecipe
        );
    }
    changed = original;
    changed[36..].fill(0);
    assert!(p.recipe_from_bytes(&changed).is_err());
}

#[test]
fn simplex_grid_is_finite_with_exact_storage_and_neutral_white() {
    let p = synthetic_four();
    let white = p.paint("white").unwrap();
    for value in white.reflectance() {
        assert!((value - 0.94).abs() < 1e-15);
    }
    for value in white.decode_linear() {
        assert!((value - 0.94).abs() < 2e-15);
    }
    for y in 0..=16 {
        for r in 0..=16 - y {
            for b in 0..=16 - y - r {
                let recipe = p
                    .recipe([y as f64, r as f64, b as f64, (16 - y - r - b) as f64])
                    .unwrap();
                assert!(recipe
                    .reflectance()
                    .iter()
                    .all(|v| v.is_finite() && *v > 0. && *v <= 1.));
                assert!(recipe.decode_linear().iter().all(|v| v.is_finite()));
                assert!(recipe
                    .decode()
                    .channels()
                    .iter()
                    .all(|v| v.is_finite() && (0. ..=1.).contains(v)));
                assert_eq!(
                    p.recipe_from_bytes(&recipe.to_le_bytes())
                        .unwrap()
                        .proportions(),
                    recipe.proportions()
                );
            }
        }
    }
}

#[test]
fn canonical_mixtures_and_tints_do_not_repeat_legacy_failures() {
    let p = synthetic_four();
    let [yellow, red, blue, white] =
        ["yellow", "red", "blue", "white"].map(|n| p.paint(n).unwrap());
    let [r, g, b] = yellow.interpolate(blue, 0.5).unwrap().decode().channels();
    assert!(
        g > r && g > b + 0.1,
        "yellow/blue should be green rather than cyan"
    );
    let [r, g, b] = red.interpolate(blue, 0.5).unwrap().decode().channels();
    assert!(r > g && b > g, "red/blue should remain purple");
    let [r, g, b] = red.interpolate(white, 0.5).unwrap().decode().channels();
    assert!(r > b && b > g, "red tint should be pink rather than peach");
    let dark = p.recipe([1., 1., 1., 0.]).unwrap();
    for base in [yellow, red, blue, dark] {
        let mut previous = 0.;
        for step in 0..=1000 {
            let tint = base.interpolate(white, step as f64 / 1000.).unwrap();
            let linear = tint.decode_linear();
            let luminance = linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
            assert!(luminance >= previous - 1e-14);
            previous = luminance;
        }
    }
}
