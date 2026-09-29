use ochrell::{FastPigmentMixer, Latent, ReferenceLatent, ReferenceSpectralMixer};

// Component import accepts finite nonnegative K and positive S at any scale.
// Changing their shared scale does not change opaque KM reflectance. This also
// catches algebraic rewrites whose K*K intermediates overflow or underflow.
#[test]
fn imported_optics_retain_scale_invariance_at_extreme_finite_magnitudes() {
    let k = std::array::from_fn::<_, 41, _>(|i| 1. + i as f32 / 32.);
    let s = std::array::from_fn::<_, 41, _>(|i| 0.5 + i as f32 / 128.);
    let residual = [0.01, -0.01, 0.02];
    let m = FastPigmentMixer;
    let expected = m.decode(Latent::try_from_parts(k, s, residual).unwrap());
    for exponent in [-100, 0, 100] {
        let scale = 2_f32.powi(exponent);
        let z =
            Latent::try_from_parts(k.map(|v| v * scale), s.map(|v| v * scale), residual).unwrap();
        assert_eq!(m.decode(z), expected, "f32 shared scale 2^{exponent}");
    }

    let k = std::array::from_fn::<_, 81, _>(|i| 1. + i as f64 / 32.);
    let s = std::array::from_fn::<_, 81, _>(|i| 0.5 + i as f64 / 128.);
    let residual = [0.01, -0.01, 0.02];
    let m = ReferenceSpectralMixer;
    let expected = m.decode(ReferenceLatent::try_from_parts(k, s, residual).unwrap());
    for exponent in [-600, 0, 600] {
        let scale = 2_f64.powi(exponent);
        let z =
            ReferenceLatent::try_from_parts(k.map(|v| v * scale), s.map(|v| v * scale), residual)
                .unwrap();
        assert_eq!(m.decode(z), expected, "f64 shared scale 2^{exponent}");
    }
}
