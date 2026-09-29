use ochrell::{Color, Latent, PigmentMixer, ReferenceLatent, ReferenceSpectralMixer};

#[test]
fn exact_components_survive_storage_and_future_tinting() {
    let m = PigmentMixer::default();
    let a = m.encode(Color::srgb8(255, 220, 0));
    let b = m.encode(Color::srgb8(20, 70, 255));
    let z = a.interpolate(b, 0.4);
    let restored = Latent::try_from_parts(*z.absorption(), *z.scattering(), z.residual()).unwrap();
    let white = m.encode(Color::srgb8(255, 255, 255));
    assert_eq!(
        m.decode(z.interpolate(white, 0.6)),
        m.decode(restored.interpolate(white, 0.6))
    );
    assert_eq!(std::mem::size_of::<Latent>(), 340);
    let r = ReferenceSpectralMixer;
    let z = r.encode(Color::srgb8(220, 10, 150));
    let restored =
        ReferenceLatent::try_from_parts(*z.absorption(), *z.scattering(), z.residual()).unwrap();
    assert_eq!(r.decode(z), r.decode(restored));
}

#[test]
fn invalid_storage_is_rejected() {
    for bad in [f32::NAN, f32::INFINITY, -1.] {
        assert!(Latent::try_from_parts([bad; 41], [1.; 41], [0.; 3]).is_err());
    }
    for bad in [f32::NAN, f32::INFINITY, 0., -1.] {
        assert!(Latent::try_from_parts([0.; 41], [bad; 41], [0.; 3]).is_err());
    }
    assert!(Latent::try_from_parts([0.; 41], [1.; 41], [f32::NAN; 3]).is_err());
}
