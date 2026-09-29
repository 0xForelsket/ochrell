//! Constrained inversion and persistent latent paint recipes.
use crate::{conversion::*, generated::*, spectrum};
#[derive(Debug, Clone, Copy)]
pub struct Latent {
    pub(crate) weights: [f32; 8],
    pub(crate) residual: [f32; 3],
}
impl Latent {
    pub fn concentrations(&self) -> [f32; 8] {
        self.weights
    }
    pub fn residual(&self) -> [f32; 3] {
        self.residual
    }
    /// Convex combination, preserving material state without an RGB round trip.
    pub fn interpolate(self, b: Self, t: f32) -> Self {
        let t = crate::mixing::bounded_t(t);
        Self {
            weights: std::array::from_fn(|i| self.weights[i] * (1. - t) + b.weights[i] * t),
            residual: std::array::from_fn(|i| self.residual[i] * (1. - t) + b.residual[i] * t),
        }
    }
}
#[derive(Debug, Clone, Copy)]
pub struct ReferenceLatent {
    pub(crate) weights: [f64; 8],
    pub(crate) residual: [f64; 3],
}
impl ReferenceLatent {
    pub fn concentrations(&self) -> [f64; 8] {
        self.weights
    }
    pub fn residual(&self) -> [f64; 3] {
        self.residual
    }
    pub fn interpolate(self, b: Self, t: f64) -> Self {
        let t = if t.is_nan() { 0. } else { t.clamp(0., 1.) };
        Self {
            weights: std::array::from_fn(|i| self.weights[i] * (1. - t) + b.weights[i] * t),
            residual: std::array::from_fn(|i| self.residual[i] * (1. - t) + b.residual[i] * t),
        }
    }
}
fn project(v: [f64; 8]) -> [f64; 8] {
    let mut u = v;
    u.sort_by(|a, b| b.total_cmp(a));
    let mut sum = 0.;
    let mut theta = 0.;
    for (i, x) in u.iter().enumerate() {
        sum += x;
        let a = (sum - 1.) / (i + 1) as f64;
        if *x > a {
            theta = a
        }
    }
    v.map(|x| (x - theta).max(0.))
}
fn solve(mut a: [[f64; 8]; 8], mut b: [f64; 8]) -> [f64; 8] {
    for i in 0..8 {
        let mut pivot = i;
        for j in i + 1..8 {
            if a[j][i].abs() > a[pivot][i].abs() {
                pivot = j
            }
        }
        a.swap(i, pivot);
        b.swap(i, pivot);
        let d = a[i][i];
        if d.abs() < 1e-18 {
            return [0.; 8];
        }
        for j in i..8 {
            a[i][j] /= d
        }
        b[i] /= d;
        for k in 0..8 {
            if k != i {
                let m = a[k][i];
                for j in i..8 {
                    a[k][j] -= m * a[i][j]
                }
                b[k] -= m * b[i]
            }
        }
    }
    b
}
/// Deterministic projected Gauss–Newton with backtracking and a simplex prior.
/// This is a local optimizer, not a certificate of the globally best recipe.
/// Low-level precondition: all three encoded sRGB components are finite and in [0,1].
pub fn invert(rgb: [f64; 3]) -> [f64; 8] {
    let p = crate::pigment::prior(rgb);
    let target = oklab(rgb.map(srgb_to_linear));
    let mut w = p;
    let objective = |w: &[f64; 8]| {
        let y = oklab(spectrum::forward(w));
        (0..3).map(|i| (y[i] - target[i]).powi(2)).sum::<f64>()
            + REG[0] * (0..8).map(|i| (w[i] - p[i]).powi(2)).sum::<f64>()
    };
    for _ in 0..SOLVER_ITERATIONS {
        let (y, j) = spectrum::forward_jacobian(&w);
        let lab = oklab(y);
        let lms = mat(LMS, y);
        let mut jac = [[0.; 8]; 3];
        for a in 0..3 {
            for b in 0..3 {
                let d = LAB[a][b] / (3. * lms[b].abs().max(1e-12).powf(2. / 3.));
                for c in 0..3 {
                    for p in 0..8 {
                        jac[a][p] += d * LMS[b][c] * j[c][p]
                    }
                }
            }
        }
        let mut h = [[0.; 8]; 8];
        let mut g = [0.; 8];
        for i in 0..8 {
            for j in 0..8 {
                h[i][j] = (0..3).map(|a| jac[a][i] * jac[a][j]).sum::<f64>();
                if i == j {
                    h[i][j] += REG[0] + 1e-5
                }
            }
            g[i] = -(0..3)
                .map(|a| jac[a][i] * (lab[a] - target[a]))
                .sum::<f64>()
                - REG[0] * (w[i] - p[i]);
        }
        let d = solve(h, g);
        let base = objective(&w);
        let mut scale = 1.;
        let mut accepted = false;
        for _ in 0..16 {
            let v = project(std::array::from_fn(|i| w[i] + scale * d[i]));
            let next = objective(&v);
            if next < base - 1e-13 {
                w = v;
                accepted = true;
                break;
            }
            scale *= 0.5
        }
        if !accepted {
            // Projecting an unconstrained Newton step need not be a descent direction
            // on an active simplex face. A projected-gradient fallback restores descent.
            let mut scale = 8.;
            for _ in 0..24 {
                let v = project(std::array::from_fn(|i| w[i] + scale * g[i]));
                if objective(&v) < base - 1e-13 {
                    w = v;
                    accepted = true;
                    break;
                }
                scale *= 0.5;
            }
        }
        if !accepted {
            break;
        }
    }
    w
}
