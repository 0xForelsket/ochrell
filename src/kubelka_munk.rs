//! Infinite-thickness two-flux Kubelka–Munk, dimensionless K/S.
/// Stable rationalized inverse. Preconditions: finite q >= 0.
pub fn reflectance(q: f64) -> f64 {
    if q == 0. {
        1.
    } else {
        1. / (1. + q + q.sqrt() * (q + 2.).sqrt())
    }
}
/// Reflectance -> K/S. R=0 maps to +infinity; domain is 0 <= R <= 1.
pub fn ks(r: f64) -> f64 {
    (1. - r).powi(2) / (2. * r)
}
