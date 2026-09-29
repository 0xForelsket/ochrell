use ochrell::{conversion::*, *};
fn error(a: Color, b: Color) -> f64 {
    a.channels()
        .iter()
        .zip(b.channels())
        .map(|(x, y)| (*x as f64 - y as f64).abs())
        .fold(0., f64::max)
}
#[test]
fn endpoints_reconstruction_and_positive_optics() {
    let m = PigmentMixer::default();
    let r = ReferenceSpectralMixer;
    for i in 0..4096u32 {
        let c = Color::srgb8(
            ((i % 16) * 17) as u8,
            ((i / 16 % 16) * 17) as u8,
            ((i / 256) * 17) as u8,
        );
        let z = m.encode(c);
        let rz = r.encode(c);
        // sRGB gamma and gamut compression amplify sub-ulp optical error at
        // cube faces. Require exact RGB8 and a tight perceptual tolerance.
        assert_eq!(c.to_srgb8(), m.decode(z).to_srgb8());
        assert!(delta_e_ok100(c.linear(), m.decode(z).linear()) < 0.001);
        assert!(error(c, r.decode(rz)) < 2e-6);
        assert!(z.absorption().iter().all(|v| v.is_finite() && *v >= 0.));
        assert!(z.scattering().iter().all(|v| v.is_finite() && *v > 0.));
        let b = Color::srgb8(0, 33, 133);
        assert_eq!(m.mix(c, b, 0.), c);
        assert_eq!(m.mix(c, b, 1.), b);
        assert_eq!(m.mix(c, c, 0.73), c);
    }
}
#[test]
fn canonical_mixtures() {
    let m = PigmentMixer::default();
    for (a, b) in [
        (Color::srgb8(255, 220, 0), Color::srgb8(20, 70, 255)),
        (Color::srgb8(252, 210, 0), Color::srgb8(0, 33, 133)),
        (Color::srgb8(255, 255, 0), Color::srgb8(0, 0, 255)),
    ] {
        let [r, g, b] = m.mix(a, b, 0.5).channels();
        assert!(g > r && g > b);
    }
    let purple = m
        .mix(Color::srgb8(230, 30, 40), Color::srgb8(20, 70, 255), 0.5)
        .channels();
    assert!(purple[0] > purple[1] && purple[2] > purple[1]);
    let blue = m
        .mix(Color::srgb8(0, 190, 210), Color::srgb8(220, 0, 160), 0.5)
        .channels();
    assert!(blue[2] > blue[0] && blue[2] > blue[1]);
    let pink = m
        .mix(Color::srgb8(230, 30, 40), Color::srgb8(255, 255, 255), 0.5)
        .channels();
    assert!(pink[0] > pink[1] && pink[2] > pink[1]);
}
#[test]
fn weighted_material_state_and_symmetry() {
    let m = PigmentMixer::default();
    let a = Color::srgb8(230, 30, 40);
    let b = Color::srgb8(20, 70, 255);
    let c = Color::srgb8(255, 255, 255);
    let (a, b, c) = (m.encode(a), m.encode(b), m.encode(c));
    let all = Latent::weighted(&[(a, 2.), (b, 3.), (c, 5.)]).unwrap();
    let ab = Latent::weighted(&[(a, 2.), (b, 3.)]).unwrap();
    let grouped = Latent::weighted(&[(ab, 5.), (c, 5.)]).unwrap();
    assert!(error(m.decode(all), m.decode(grouped)) < 2e-6);
    assert!(
        error(
            m.decode(a.interpolate(b, 0.3)),
            m.decode(b.interpolate(a, 0.7))
        ) < 2e-6
    );
    assert!(Latent::weighted(&[]).is_err());
    assert!(Latent::weighted(&[(a, f32::NAN)]).is_err());
    assert!(m.mix_weighted(&[(m.decode(a), 0.)]).is_err());
    assert!(m.try_mix(m.decode(a), m.decode(b), f32::INFINITY).is_err());
}
#[test]
fn channel_order_boundaries_are_continuous() {
    let m = PigmentMixer::default();
    let b = Color::srgb8(0, 33, 133);
    for i in 1..100 {
        let v = i as f32 / 100.;
        for order in 0..3 {
            let mut a = [v, v, 0.23];
            let mut c = a;
            a[order] -= 1e-6;
            c[order] += 1e-6;
            let x = Color::srgb(a[0], a[1], a[2]).unwrap();
            let y = Color::srgb(c[0], c[1], c[2]).unwrap();
            assert!(delta_e_ok100(m.mix(x, b, 0.5).linear(), m.mix(y, b, 0.5).linear()) < 0.005);
        }
    }
}
#[test]
fn sampled_tint_luminance() {
    let m = PigmentMixer::default();
    let white = Color::srgb8(255, 255, 255);
    for i in 0..256u16 {
        let a = Color::srgb8(i as u8, (i * 37) as u8, (i * 131) as u8);
        let mut y0 = a
            .linear()
            .iter()
            .zip([0.2126, 0.7152, 0.0722])
            .map(|(v, w)| v * w)
            .sum::<f64>();
        for j in 1..1001 {
            let c = m.mix(a, white, j as f32 / 1000.);
            let x = c.linear();
            let y = x
                .iter()
                .zip([0.2126, 0.7152, 0.0722])
                .map(|(v, w)| v * w)
                .sum::<f64>();
            assert!(y >= y0 - 2e-6);
            assert!(x.iter().all(|v| v.is_finite() && *v >= 0. && *v <= 1.));
            y0 = y;
        }
    }
}
#[test]
fn f32_decoder_against_promoted_f64() {
    let m = PigmentMixer::default();
    for i in 0..1024u32 {
        let a = m.encode(Color::srgb8(i as u8, (i * 53) as u8, (i * 179) as u8));
        let b = m.encode(Color::srgb8(
            (i * 101) as u8,
            (i * 71) as u8,
            (i * 19) as u8,
        ));
        let z = a.interpolate(b, 0.371);
        for (x, y) in m.decode_linear(z).iter().zip(optical::decode_fast_f64(z)) {
            assert!((*x - y).abs() < 2e-6);
        }
    }
}

#[test]
fn black_endpoint_converges_despite_cuberoot_metric() {
    let m = PigmentMixer::default();
    let a = Color::srgb8(0, 0, 0);
    let b = Color::srgb8(255, 255, 255);
    let mut prev = 100.;
    for t in [1e-3, 1e-4, 1e-5, 1e-6] {
        let d = delta_e_ok100(a.linear(), m.mix(a, b, t).linear());
        assert!(d < prev);
        prev = d;
    }
}
