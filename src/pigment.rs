//! Synthetic pigment identities. No claim of correspondence to a measured paint.
pub const PIGMENT_COUNT: usize = 8;
pub const NAMES: [&str; 8] = [
    "white", "cyan", "magenta", "yellow", "red", "green", "blue", "black",
];
/// Piecewise-linear simplex initializer in encoded sRGB.
pub fn prior([r, g, b]: [f64; 3]) -> [f64; 8] {
    let mut w = [0.; 8];
    w[0] = r.min(g).min(b);
    w[7] = 1. - r.max(g).max(b);
    if r <= g && r <= b {
        w[1] = g.min(b) - r;
        w[if g > b { 5 } else { 6 }] = (g - b).abs()
    } else if g <= r && g <= b {
        w[2] = r.min(b) - g;
        w[if r > b { 4 } else { 6 }] = (r - b).abs()
    } else {
        w[3] = r.min(g) - b;
        w[if r > g { 4 } else { 5 }] = (r - g).abs()
    }
    w
}
