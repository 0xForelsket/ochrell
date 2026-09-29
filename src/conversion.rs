//! Published sRGB and OKLab transforms; matrices attributed in docs/math.md.
pub fn srgb_to_linear(x: f64) -> f64 {
    if x <= 0.04045 {
        x / 12.92
    } else {
        ((x + 0.055) / 1.055).powf(2.4)
    }
}
pub fn linear_to_srgb(x: f64) -> f64 {
    if x <= 0.0031308 {
        12.92 * x
    } else {
        1.055 * x.powf(1. / 2.4) - 0.055
    }
}
pub const LMS: [[f64; 3]; 3] = [
    [0.4122214708, 0.5363325363, 0.0514459929],
    [0.2119034982, 0.6806995451, 0.1073969566],
    [0.0883024619, 0.2817188376, 0.6299787005],
];
pub const LAB: [[f64; 3]; 3] = [
    [0.2104542553, 0.7936177850, -0.0040720468],
    [1.9779984951, -2.4285922050, 0.4505937099],
    [0.0259040371, 0.7827717662, -0.8086757660],
];
pub fn mat(m: [[f64; 3]; 3], x: [f64; 3]) -> [f64; 3] {
    m.map(|r| r[0] * x[0] + r[1] * x[1] + r[2] * x[2])
}
pub fn oklab(x: [f64; 3]) -> [f64; 3] {
    mat(LAB, mat(LMS, x).map(f64::cbrt))
}
pub fn oklab_to_linear(x: [f64; 3]) -> [f64; 3] {
    let l = x[0] + 0.3963377774 * x[1] + 0.2158037573 * x[2];
    let m = x[0] - 0.1055613458 * x[1] - 0.0638541728 * x[2];
    let s = x[0] - 0.0894841775 * x[1] - 1.2914855480 * x[2];
    mat(
        [
            [4.0767416621, -3.3077115913, 0.2309699292],
            [-1.2684380046, 2.6097574011, -0.3413193965],
            [-0.0041960863, -0.7034186147, 1.7076147010],
        ],
        [l * l * l, m * m * m, s * s * s],
    )
}
pub fn delta_e_ok100(a: [f64; 3], b: [f64; 3]) -> f64 {
    let a = oklab(a);
    let b = oklab(b);
    100. * ((a[0] - b[0]).powi(2) + (a[1] - b[1]).powi(2) + (a[2] - b[2]).powi(2)).sqrt()
}
/// Continuous neutral-axis compression in linear RGB, identity inside gamut.
/// Preserves Rec.709 luminance when it lies in [0,1], but not perceptual hue.
pub fn gamut_map(x: [f64; 3]) -> [f64; 3] {
    if !x.iter().all(|x| x.is_finite()) {
        return [0.; 3];
    }
    if x.iter().all(|x| (0. ..=1.).contains(x)) {
        return x;
    }
    let y = (0.2126 * x[0] + 0.7152 * x[1] + 0.0722 * x[2]).clamp(0., 1.);
    let mut a: f64 = 1.;
    for v in x {
        let d = v - y;
        if d > 0. {
            a = a.min((1. - y) / d)
        } else if d < 0. {
            a = a.min(-y / d)
        }
    }
    x.map(|v| (y + a * (v - y)).clamp(0., 1.))
}
