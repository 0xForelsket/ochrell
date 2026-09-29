use ochrell::legacy::{PigmentMixer, ReferenceSpectralMixer};
use ochrell::*;
fn distance(a: Color, b: Color) -> f32 {
    a.channels()
        .iter()
        .zip(b.channels())
        .map(|(x, y)| (x - y).abs())
        .fold(0., f32::max)
}
#[test]
fn transfer_roundtrip() {
    for i in 0..10001 {
        let x = i as f64 / 10000.;
        assert!((conversion::linear_to_srgb(conversion::srgb_to_linear(x)) - x).abs() < 2e-15)
    }
}
#[test]
fn km_inverse() {
    for i in 1..10000 {
        let r = i as f64 / 10000.;
        assert!((kubelka_munk::reflectance(kubelka_munk::ks(r)) - r).abs() < 1e-12)
    }
    assert_eq!(kubelka_munk::reflectance(0.), 1.);
    assert!(kubelka_munk::reflectance(1e200).is_finite())
}
#[test]
fn neutral_spectrum() {
    for p in [0, 7] {
        let mut w = [0.; 8];
        w[p] = 1.;
        let c = spectrum::forward(&w);
        assert!((c[0] - c[1]).abs() < 1e-12);
        assert!((c[1] - c[2]).abs() < 1e-12)
    }
}
#[test]
fn color_validation() {
    assert_eq!(Color::srgb(f32::NAN, 0., 0.), Err(MixError::NonFinite));
    assert_eq!(Color::srgb(2., 0., 0.), Err(MixError::OutOfRange));
}
#[test]
fn oklab_known() {
    let lab = conversion::oklab([1., 0., 0.]);
    assert!((lab[0] - 0.62795536).abs() < 1e-7);
    let x = conversion::oklab_to_linear(lab);
    assert!((x[0] - 1.).abs() < 2e-7);
    assert!(x[1].abs() < 2e-7)
}
#[test]
fn gamut_identity_and_bounded() {
    for a in [[0., 0.5, 1.], [-0.1, 0.8, 1.3], [4., -2., 0.]] {
        let b = conversion::gamut_map(a);
        assert!(b.iter().all(|v| (0. ..=1.).contains(v)));
        if a == [0., 0.5, 1.] {
            assert_eq!(a, b)
        }
    }
}
#[test]
fn lut_validation() {
    assert!(lut::Lut::from_bytes(b"invalid").is_err());
    let l = PigmentMixer::default();
    assert!(l.lut().resolution() >= 17);
    let b = l.lut().to_bytes();
    assert_eq!(lut::Lut::from_bytes(&b).unwrap().to_bytes(), b);
    let mut c = b;
    c[8..12].copy_from_slice(&f32::NAN.to_le_bytes());
    assert!(lut::Lut::from_bytes(&c).is_err())
}
#[test]
fn endpoints_identity_symmetry() {
    let m = PigmentMixer::default();
    let a = Color::srgb8(255, 220, 0);
    let b = Color::srgb8(20, 70, 255);
    assert_eq!(m.mix(a, b, 0.), a);
    assert_eq!(m.mix(a, b, 1.), b);
    assert_eq!(m.mix(a, b, f32::NAN), a);
    assert!(m.try_mix(a, b, f32::NAN).is_err());
    for i in 0..101 {
        let t = i as f32 / 100.;
        assert!(distance(m.mix(a, b, t), m.mix(b, a, 1. - t)) < 2e-5);
        assert_eq!(m.mix(a, a, t), a)
    }
}
#[test]
fn reconstruction_grid() {
    let m = PigmentMixer::default();
    for r in 0..=10 {
        for g in 0..=10 {
            for b in 0..=10 {
                let c = Color::srgb(r as f32 / 10., g as f32 / 10., b as f32 / 10.).unwrap();
                let z = m.encode(c);
                assert!((z.concentrations().iter().sum::<f32>() - 1.).abs() < 2e-6);
                assert!(z.concentrations().iter().all(|x| *x >= 0.));
                assert!(distance(c, m.decode(z)) < 1e-5)
            }
        }
    }
}
#[test]
fn weighted() {
    let m = PigmentMixer::default();
    let a = Color::srgb8(255, 220, 0);
    let b = Color::srgb8(20, 70, 255);
    assert!(
        distance(
            m.mix(a, b, 0.5),
            m.mix_weighted(&[(a, 2.), (b, 2.)]).unwrap()
        ) < 1e-5
    );
    assert!(m.mix_weighted(&[]).is_err());
    assert!(m.mix_weighted(&[(a, -1.)]).is_err());
    assert!(m.mix_weighted(&[(a, 0.)]).is_err());
    assert!(m.mix_weighted(&[(a, f32::NAN)]).is_err())
}
#[test]
fn canonical_hues() {
    let m = PigmentMixer::default();
    let y = Color::srgb8(255, 220, 0);
    let b = Color::srgb8(20, 70, 255);
    let c = m.mix(y, b, 0.5).channels();
    assert!(c[1] > c[0] && c[1] > c[2], "yellow-blue {c:?}");
    let c = m.mix(Color::srgb8(230, 30, 40), b, 0.5).channels();
    assert!(c[0] > c[1] && c[2] > c[1], "red-blue {c:?}");
}
#[test]
fn continuity() {
    let m = PigmentMixer::default();
    let a = Color::srgb8(255, 220, 0);
    let b = Color::srgb8(20, 70, 255);
    let mut prev = m.mix(a, b, 0.);
    for i in 1..=2000 {
        let c = m.mix(a, b, i as f32 / 2000.);
        assert!(c.channels().iter().all(|x| x.is_finite()));
        assert!(conversion::delta_e_ok100(c.linear(), prev.linear()) < 1.0);
        prev = c
    }
    for endpoint in [0.0f32, 1.0] {
        let base = m.mix(a, b, endpoint);
        let mut last = 1.0;
        for eps in [1e-4f32, 1e-5, 1e-6] {
            let t = if endpoint == 0.0 { eps } else { 1.0 - eps };
            let err = distance(base, m.mix(a, b, t));
            assert!(
                err < last * 0.3,
                "nonconvergent endpoint: {err} after {last}"
            );
            last = err;
        }
    }
    // Adjacent RGB inputs across every LUT cell face.
    for i in 1..m.lut().resolution() - 1 {
        let x = i as f32 / (m.lut().resolution() - 1) as f32;
        let a = Color::srgb(x - 1e-6, 0.41, 0.72).unwrap();
        let b = Color::srgb(x + 1e-6, 0.41, 0.72).unwrap();
        assert!(m
            .lut()
            .lookup(a)
            .iter()
            .zip(m.lut().lookup(b))
            .all(|(a, b)| (a - b).abs() < 0.002));
    }
}
#[test]
fn reference_reconstruction() {
    let m = ReferenceSpectralMixer;
    for c in [
        Color::srgb8(255, 0, 0),
        Color::srgb8(3, 12, 251),
        Color::srgb8(0, 0, 0),
    ] {
        assert!(distance(c, m.decode(m.encode(c))) < 1e-6)
    }
}

#[test]
fn both_lut_interpolators_reproduce_affine_fields() {
    let mut bytes = b"PMX1".to_vec();
    bytes.extend(3u32.to_le_bytes());
    for r in 0..3 {
        for g in 0..3 {
            for b in 0..3 {
                let w = [
                    r as f32 / 6.,
                    g as f32 / 6.,
                    b as f32 / 6.,
                    0.,
                    0.,
                    0.,
                    0.,
                    1. - (r + g + b) as f32 / 6.,
                ];
                for x in w {
                    bytes.extend(x.to_le_bytes());
                }
            }
        }
    }
    let lut = lut::Lut::from_bytes(&bytes).unwrap();
    for x in [
        [0.13, 0.91, 0.42],
        [0.91, 0.13, 0.42],
        [0.42, 0.91, 0.13],
        [0.42, 0.13, 0.91],
        [0.13, 0.42, 0.91],
        [0.91, 0.42, 0.13],
        [0., 0., 0.],
        [1., 1., 1.],
        [0.5, 0.5, 0.5],
    ] {
        let c = Color::srgb(x[0], x[1], x[2]).unwrap();
        for got in [lut.lookup(c), lut.lookup_trilinear(c)] {
            for i in 0..3 {
                assert!((got[i] - x[i] / 3.).abs() < 1e-7);
            }
            assert!((got.iter().sum::<f32>() - 1.).abs() < 2e-7);
        }
    }
}
