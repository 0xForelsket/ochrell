use ochrell::{
    compact::{CompactLatent, BYTES, SAMPLES},
    conversion::delta_e_ok100,
    Color, FastPigmentMixer, Latent,
};
fn de(a: Color, b: Color) -> f64 {
    delta_e_ok100(a.linear(), b.linear())
}

#[test]
fn source_reconstruction_and_exact_serialization() {
    assert_eq!(std::mem::size_of::<CompactLatent>(), 204);
    assert_eq!(BYTES, 204);
    for i in 0..4096u32 {
        let c = Color::srgb8(
            (i % 16 * 17) as u8,
            (i / 16 % 16 * 17) as u8,
            (i / 256 * 17) as u8,
        );
        let z = CompactLatent::encode(c);
        assert!(de(z.decode(), c) < 0.002);
        assert_eq!(z.decode().to_srgb8(), c.to_srgb8());
        let bytes = z.to_le_bytes();
        let restored = CompactLatent::try_from_le_bytes(bytes).unwrap();
        assert_eq!(restored.to_le_bytes(), bytes);
        assert_eq!(
            restored
                .interpolate(CompactLatent::encode(Color::srgb8(255, 255, 255)), 0.3)
                .decode(),
            z.interpolate(CompactLatent::encode(Color::srgb8(255, 255, 255)), 0.3)
                .decode()
        );
    }
}

#[test]
fn grouped_weights_and_tiny_updates_preserve_material() {
    let colors = [
        Color::srgb8(255, 220, 0),
        Color::srgb8(20, 70, 255),
        Color::srgb8(230, 30, 40),
        Color::srgb8(255, 255, 255),
    ];
    let c = colors.map(CompactLatent::encode);
    let f = colors.map(|c| FastPigmentMixer.encode(c));
    let direct =
        CompactLatent::weighted(&[(c[0], 2.), (c[1], 3.), (c[2], 5.), (c[3], 7.)]).unwrap();
    let ab = CompactLatent::weighted(&[(c[0], 2.), (c[1], 3.)]).unwrap();
    let grouped = CompactLatent::weighted(&[(ab, 5.), (c[2], 5.), (c[3], 7.)]).unwrap();
    assert!(de(direct.decode(), grouped.decode()) < 0.002);
    let full = Latent::weighted(&[(f[0], 2.), (f[1], 3.), (f[2], 5.), (f[3], 7.)]).unwrap();
    assert!(de(direct.decode(), FastPigmentMixer.decode(full)) < 0.2);
    let (mut z, mut raw) = (c[0], f[0]);
    for _ in 0..4096 {
        z = z.interpolate(c[1], 0.0001);
        raw = raw.interpolate(f[1], 0.0001);
        z = CompactLatent::try_from_full(z.to_full()).unwrap();
        z = CompactLatent::try_from_le_bytes(z.to_le_bytes()).unwrap();
    }
    assert!(de(z.decode(), FastPigmentMixer.decode(raw)) < 0.2);
    assert!(de(z.decode(), c[0].decode()) > 1.);
}

#[test]
fn positivity_and_validation_include_imported_extremes() {
    for value in [f32::from_bits(1), f32::MIN_POSITIVE, 1., f32::MAX] {
        let z = CompactLatent::try_from_parts([value; SAMPLES], [value; SAMPLES], [0.; 3]).unwrap();
        for t in [0., 0.1, 0.5, 0.9, 1.] {
            let f = z.interpolate(z, t).to_full();
            assert!(f.absorption().iter().all(|v| v.is_finite() && *v >= 0.));
            assert!(f.scattering().iter().all(|v| v.is_finite() && *v > 0.));
        }
    }
    assert!(CompactLatent::try_from_parts([-1.; SAMPLES], [1.; SAMPLES], [0.; 3]).is_err());
    assert!(CompactLatent::try_from_parts([1.; SAMPLES], [0.; SAMPLES], [0.; 3]).is_err());
    assert!(CompactLatent::try_from_parts([1.; SAMPLES], [1.; SAMPLES], [f32::NAN; 3]).is_err());
    let a = CompactLatent::encode(Color::srgb8(255, 255, 255));
    let b = CompactLatent::encode(Color::srgb8(0, 0, 0));
    assert_eq!(a.interpolate(b, f32::NAN), a);
    assert_eq!(a.interpolate(b, f32::INFINITY), b);
    assert!(CompactLatent::weighted(&[]).is_err());
    assert!(CompactLatent::weighted(&[(a, 0.)]).is_err());
    assert!(CompactLatent::weighted(&[(a, -1.)]).is_err());
    assert!(CompactLatent::weighted(&[(a, f32::NAN)]).is_err());
}

#[test]
fn canonical_mixtures_and_tints_stay_within_the_compact_budget() {
    let colors: [Color; 8] = std::array::from_fn(|i| {
        Color::srgb8(
            if i & 1 != 0 { 255 } else { 0 },
            if i & 2 != 0 { 255 } else { 0 },
            if i & 4 != 0 { 255 } else { 0 },
        )
    });
    let full = colors.map(|c| FastPigmentMixer.encode(c));
    let compact = colors.map(CompactLatent::encode);
    let mut errors = Vec::new();
    for (a, b) in [(3, 4), (1, 4), (2, 1), (4, 7), (1, 7), (0, 7), (5, 6)] {
        for i in 0..=1000 {
            let t = i as f32 / 1000.;
            let c = compact[a].interpolate(compact[b], t).decode();
            let f = FastPigmentMixer.decode(full[a].interpolate(full[b], t));
            errors.push(de(c, f));
        }
    }
    errors.sort_by(f64::total_cmp);
    assert!(errors.iter().sum::<f64>() / (errors.len() as f64) < 0.01);
    assert!(errors[errors.len() * 95 / 100] < 0.05);
    assert!(*errors.last().unwrap() < 0.20);
}
