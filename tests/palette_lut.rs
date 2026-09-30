use ochrell::{
    palette::{synthetic_four, Recipe},
    palette_lut::{LutError, LutMapping, PaletteLut},
};

#[test]
fn nodes_and_endpoints_reproduce_reference_with_only_f32_quantization() {
    let p = synthetic_four();
    for mapping in [LutMapping::Uniform, LutMapping::RecipeSqrt] {
        let lut = PaletteLut::build_with_mapping(p, 17, mapping).unwrap();
        assert_eq!(lut.payload_bytes(), 17 * 17 * 17 * 12 + 17 * 8);
        for a in 0..=16 {
            for b in 0..=16 - a {
                for c in 0..=16 - a - b {
                    let mut amounts = [a as f64, b as f64, c as f64, (16 - a - b - c) as f64];
                    if mapping == LutMapping::RecipeSqrt {
                        amounts = amounts.map(|v| v * v);
                    }
                    let r = p.recipe(amounts).unwrap();
                    let actual = lut.decode_linear(&r).unwrap();
                    for (x, y) in actual.into_iter().zip(r.decode_linear()) {
                        assert!((x - y).abs() < 2e-7);
                    }
                }
            }
        }
        // Out-of-gamut raw channels must not be clipped in table construction.
        let blue = p.paint("blue").unwrap();
        assert!(blue.decode_linear()[0] < 0.);
        assert!(lut.decode_linear(&blue).unwrap()[0] < 0.);
    }
}

#[test]
fn selected_mapping_meets_budgets_on_boundary_and_interior_probes() {
    let p = synthetic_four();
    let lut = PaletteLut::build(p, 65).unwrap();
    assert_eq!(lut.mapping(), LutMapping::RecipeSqrt);
    let mut errors = Vec::new();
    let mut rng = 8675309_u64;
    for index in 0..4096 {
        let mut amounts = std::array::from_fn(|_| {
            rng ^= rng << 13;
            rng ^= rng >> 7;
            rng ^= rng << 17;
            (rng >> 11) as f64 / (1_u64 << 53) as f64
        });
        if index % 2 == 0 {
            amounts[index % 4] = 0.;
        }
        if index % 7 == 0 {
            amounts[(index + 1) % 4] *= 1e-6;
        }
        let recipe = p.recipe(amounts).unwrap();
        let raw = lut.decode_linear(&recipe).unwrap();
        assert!(raw
            .into_iter()
            .zip(recipe.decode_linear())
            .all(|(a, b)| (a - b).abs() <= 0.01));
        errors.push(ochrell::conversion::delta_e_ok100(
            lut.decode(&recipe).unwrap().linear(),
            recipe.decode().linear(),
        ));
    }
    errors.sort_by(f64::total_cmp);
    assert!(errors.iter().sum::<f64>() / errors.len() as f64 <= 0.03);
    assert!(errors[(errors.len() - 1) * 95 / 100] <= 0.10);
    assert!(*errors.last().unwrap() <= 0.50);
}

#[test]
fn table_roundtrip_preserves_decodes_and_never_changes_material_history() {
    let p = synthetic_four();
    let lut = PaletteLut::build(p, 17).unwrap();
    let bytes = lut.to_bytes();
    let loaded = PaletteLut::from_bytes(p, &bytes).unwrap();
    assert_eq!(bytes, loaded.to_bytes());
    let mut a = p.paint("yellow").unwrap();
    let mut b = a;
    let blue = p.paint("blue").unwrap();
    for _ in 0..4096 {
        a = a.interpolate(blue, 0.0001).unwrap();
        b = b.interpolate(blue, 0.0001).unwrap();
        let before = b.to_le_bytes();
        assert_eq!(lut.decode(&b).unwrap(), loaded.decode(&b).unwrap());
        assert_eq!(before, b.to_le_bytes());
        b = p.recipe_from_bytes(&before).unwrap();
    }
    assert_eq!(a.to_le_bytes(), b.to_le_bytes());
    let white = p.paint("white").unwrap();
    assert_eq!(
        Recipe::weighted(&[(a, 2.), (white, 3.)]).unwrap().decode(),
        Recipe::weighted(&[(b, 2.), (white, 3.)]).unwrap().decode()
    );
}

#[test]
fn invalid_sizes_identity_format_and_corruption_are_rejected() {
    let p = synthetic_four();
    for resolution in [0, 1, 130, usize::MAX] {
        assert_eq!(
            PaletteLut::build(p, resolution).unwrap_err(),
            LutError::InvalidResolution
        );
    }
    let bytes = PaletteLut::build(p, 2).unwrap().to_bytes();
    for n in 0..bytes.len() {
        assert!(PaletteLut::from_bytes(p, &bytes[..n]).is_err());
    }
    let mut bad = bytes.clone();
    bad.push(0);
    assert_eq!(
        PaletteLut::from_bytes(p, &bad).unwrap_err(),
        LutError::InvalidFormat
    );
    bad = bytes.clone();
    bad[0] = b'X';
    assert_eq!(
        PaletteLut::from_bytes(p, &bad).unwrap_err(),
        LutError::InvalidFormat
    );
    bad = bytes.clone();
    bad[4] ^= 1;
    assert_eq!(
        PaletteLut::from_bytes(p, &bad).unwrap_err(),
        LutError::PaletteMismatch
    );
    bad = bytes.clone();
    bad[36..40].copy_from_slice(&u32::MAX.to_le_bytes());
    assert_eq!(
        PaletteLut::from_bytes(p, &bad).unwrap_err(),
        LutError::InvalidResolution
    );
    bad = bytes;
    bad[45] ^= 1;
    assert_eq!(
        PaletteLut::from_bytes(p, &bad).unwrap_err(),
        LutError::InvalidChecksum
    );
}

#[test]
fn shared_cells_and_tetrahedral_faces_are_continuous() {
    let p = synthetic_four();
    let lut = PaletteLut::build(p, 17).unwrap();
    // Equal proportions cross grid planes; the other points cross fractional
    // coordinate ties, including a simplex face with one absent ingredient.
    for amounts in [
        [0.25, 0.25, 0.25, 0.25],
        [0.21, 0.25, 0.25, 0.29],
        [0., 0.31, 0.25, 0.44],
    ] {
        for i in 0..3 {
            if amounts[i] == 0. {
                continue;
            }
            let mut left = amounts;
            let mut right = amounts;
            left[i] -= 1e-9;
            left[3] += 1e-9;
            right[i] += 1e-9;
            right[3] -= 1e-9;
            let x = lut.decode_linear(&p.recipe(left).unwrap()).unwrap();
            let y = lut.decode_linear(&p.recipe(right).unwrap()).unwrap();
            for (x, y) in x.into_iter().zip(y) {
                assert!((x - y).abs() < 1e-6);
            }
        }
    }
}
