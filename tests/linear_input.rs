use ochrell::{Color, FastPigmentMixer, MixError, ReferenceSpectralMixer};

fn colors() -> impl Iterator<Item = Color> {
    (0..4096u32)
        .map(|i| {
            Color::srgb8(
                (i % 16 * 17) as u8,
                (i / 16 % 16 * 17) as u8,
                (i / 256 * 17) as u8,
            )
        })
        .chain((0..997u32).map(|i| {
            let v = |k: u32| ((i * k + 7) % 1000) as f32 / 999.;
            Color::srgb(v(37), v(101), v(263)).unwrap()
        }))
}

#[test]
fn encode_linear_matches_encode_bit_for_bit() {
    for c in colors() {
        let (a, b) = (
            FastPigmentMixer.encode(c),
            FastPigmentMixer.encode_linear(c.linear()).unwrap(),
        );
        assert!(a
            .absorption()
            .iter()
            .chain(a.scattering())
            .chain(&a.residual())
            .map(|v| v.to_bits())
            .eq(b
                .absorption()
                .iter()
                .chain(b.scattering())
                .chain(&b.residual())
                .map(|v| v.to_bits())));
        let (a, b) = (
            ReferenceSpectralMixer.encode(c),
            ReferenceSpectralMixer.encode_linear(c.linear()).unwrap(),
        );
        assert!(a
            .absorption()
            .iter()
            .chain(a.scattering())
            .chain(&a.residual())
            .map(|v| v.to_bits())
            .eq(b
                .absorption()
                .iter()
                .chain(b.scattering())
                .chain(&b.residual())
                .map(|v| v.to_bits())));
    }
}

#[test]
fn encode_linear_checks_its_input() {
    assert_eq!(
        FastPigmentMixer
            .encode_linear([0.5, f64::NAN, 0.2])
            .unwrap_err(),
        MixError::NonFinite
    );
    assert_eq!(
        FastPigmentMixer.encode_linear([0.5, 1.2, 0.2]).unwrap_err(),
        MixError::OutOfRange
    );
    assert_eq!(
        ReferenceSpectralMixer
            .encode_linear([-0.1, 0.0, 0.0])
            .unwrap_err(),
        MixError::OutOfRange
    );
    assert!(FastPigmentMixer.encode_linear([0.0, 1.0, 0.25]).is_ok());
}
