//! Optical forward models; stack-only per evaluation.
use crate::generated::*;
/// 81 bands (380–780 nm inclusive, 5 nm), f64 reference.
pub fn forward(w: &[f64; 8]) -> [f64; 3] {
    let mut out = [0.; 3];
    let s = dot(w, &S_REF);
    for j in 0..81 {
        let r = crate::kubelka_munk::reflectance(dot(w, &K_REF[j]) / s);
        for (ch, v) in out.iter_mut().enumerate() {
            *v += r * RGB_REF[j][ch]
        }
    }
    out
}
#[inline]
pub(crate) fn dot(a: &[f64; 8], b: &[f64; 8]) -> f64 {
    a.iter().zip(b).map(|(a, b)| a * b).sum()
}
/// 21 bands (20 nm), f32. Validated against the reference, not real paint.
#[inline]
pub fn forward_fast(w: &[f32; 8]) -> [f32; 3] {
    let s: f32 = w.iter().zip(S_FAST).map(|(a, b)| a * b).sum();
    let mut out = [0.; 3];
    for j in 0..21 {
        let k: f32 = w.iter().zip(K_FAST[j]).map(|(a, b)| a * b).sum();
        let q = k / s;
        let r = 1. / (1. + q + (q * (q + 2.)).sqrt());
        for (ch, v) in out.iter_mut().enumerate() {
            *v += r * RGB_FAST[j][ch]
        }
    }
    out
}
pub(crate) fn forward_jacobian(w: &[f64; 8]) -> ([f64; 3], [[f64; 8]; 3]) {
    let s = dot(w, &S_REF);
    let mut rgb = [0.; 3];
    let mut jac = [[0.; 8]; 3];
    for j in 0..81 {
        let q = dot(w, &K_REF[j]) / s;
        let root = (q * (q + 2.)).sqrt();
        let r = 1. / (1. + q + root);
        for ch in 0..3 {
            rgb[ch] += r * RGB_REF[j][ch];
            for p in 0..8 {
                jac[ch][p] += -r / root * (K_REF[j][p] - q * S_REF[p]) / s * RGB_REF[j][ch]
            }
        }
    }
    (rgb, jac)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn analytic_jacobian_agrees_with_central_differences() {
        let w = [0.125; 8];
        let (_, j) = forward_jacobian(&w);
        let h = 1e-6;
        for pigment in 0..8 {
            let mut plus = w;
            let mut minus = w;
            plus[pigment] += h;
            minus[pigment] -= h;
            let a = forward(&plus);
            let b = forward(&minus);
            for channel in 0..3 {
                let numerical = (a[channel] - b[channel]) / (2. * h);
                assert!((numerical - j[channel][pigment]).abs() < 1e-8);
            }
        }
    }
}
