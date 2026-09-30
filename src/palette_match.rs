//! Bounded target-color search in a four-paint palette. No RGB residual is added.
//!
//! ```
//! use ochrell::{Color, palette::synthetic_four, palette_match::ColorMatcher};
//! let matcher = ColorMatcher::new(synthetic_four()).unwrap();
//! let found = matcher.match_color(Color::srgb8(80, 170, 120)).unwrap();
//! println!("recipe {:?}, error {}", found.recipe.proportions(), found.error_ok100);
//! ```
use crate::{
    conversion,
    palette::{Palette, PaletteError, Recipe},
    Color,
};
use std::borrow::Cow;

const SEED_DIVISIONS: usize = 8;
const STARTS: usize = 6;
const EVALUATIONS_PER_START: usize = 4000;

#[derive(Clone, Copy, Debug)]
struct Seed {
    proportions: [f64; 4],
    metric: [f64; 3],
}

/// Prepare once per palette. Host-supplied cube root permits portable arithmetic
/// without imposing a math dependency on Ochrell. Target search is a cold path.
pub struct ColorMatcher<'a> {
    palette: Cow<'a, Palette>,
    cbrt: fn(f64) -> f64,
    seeds: Vec<Seed>,
}

#[derive(Clone, Copy, Debug)]
pub struct ColorMatch<'a> {
    pub recipe: Recipe<'a>,
    /// Gamut-mapped achieved linear RGB, before any platform sRGB transfer.
    pub achieved_linear: [f64; 3],
    pub error_ok100: f64,
    /// Direct forward evaluations during refinement; excludes cached seed preparation.
    pub evaluations: usize,
}

impl ColorMatch<'_> {
    pub fn color(&self) -> Color {
        Color::from_linear_gamut_mapped(self.achieved_linear)
    }
}

impl<'a> ColorMatcher<'a> {
    pub fn new(palette: &'a Palette) -> Result<Self, PaletteError> {
        Self::with_cbrt(palette, f64::cbrt)
    }

    /// `cbrt` must implement cube root consistently, including negative values.
    /// A renderer can pass its portable implementation and provide linear targets.
    pub fn with_cbrt(palette: &'a Palette, cbrt: fn(f64) -> f64) -> Result<Self, PaletteError> {
        let mut seeds = Vec::new();
        for a in 0..=SEED_DIVISIONS {
            for b in 0..=SEED_DIVISIONS - a {
                for c in 0..=SEED_DIVISIONS - a - b {
                    let recipe = palette.recipe([
                        a as f64,
                        b as f64,
                        c as f64,
                        (SEED_DIVISIONS - a - b - c) as f64,
                    ])?;
                    seeds.push(Seed {
                        proportions: recipe.proportions(),
                        metric: metric(conversion::gamut_map(recipe.decode_linear()), cbrt)?,
                    });
                }
            }
        }
        Ok(Self {
            palette: Cow::Borrowed(palette),
            cbrt,
            seeds,
        })
    }

    pub fn into_owned(self) -> ColorMatcher<'static> {
        ColorMatcher {
            palette: Cow::Owned(self.palette.into_owned()),
            cbrt: self.cbrt,
            seeds: self.seeds,
        }
    }
    pub fn palette(&self) -> &Palette {
        &self.palette
    }
    pub fn match_color(&self, target: Color) -> Result<ColorMatch<'_>, PaletteError> {
        self.match_linear(target.linear())
    }

    /// Best recipe found by a stable bounded multistart search in displayed
    /// OKLab. Unreachable colors return their achieved color and nonzero error.
    /// This does not assert a unique inverse or a certified global optimum.
    pub fn match_linear(&self, target: [f64; 3]) -> Result<ColorMatch<'_>, PaletteError> {
        if target
            .iter()
            .any(|v| !v.is_finite() || !(0. ..=1.).contains(v))
        {
            return Err(PaletteError::InvalidTarget);
        }
        let wanted = metric(target, self.cbrt)?;
        let mut ranked: Vec<_> = self
            .seeds
            .iter()
            .enumerate()
            .map(|(i, s)| (distance(s.metric, wanted), i))
            .collect();
        if ranked.iter().any(|(v, _)| !v.is_finite()) {
            return Err(PaletteError::InvalidMetric);
        }
        ranked.sort_by(|a, b| a.0.total_cmp(&b.0).then(a.1.cmp(&b.1)));
        let (mut best_score, index) = ranked[0];
        let mut best = self.seeds[index].proportions;
        let mut evaluations = 0;
        for &(initial_score, index) in ranked.iter().take(STARTS) {
            if best_score <= 1e-18 {
                break;
            }
            let mut current = self.seeds[index].proportions;
            let mut score = initial_score;
            let mut step: f64 = 0.125;
            let start_count = evaluations;
            // Simultaneous directions can cross gamut-map creases where a
            // sequence of individual component transfers stalls.
            for _ in 0..48 {
                let value = metric(
                    conversion::gamut_map(self.palette.recipe(current)?.decode_linear()),
                    self.cbrt,
                )?;
                evaluations += 1;
                let mut jac = [[0.; 4]; 3];
                for axis in 0..4 {
                    let mut shifted = current;
                    shifted[axis] += 1e-5;
                    let other = metric(
                        conversion::gamut_map(self.palette.recipe(shifted)?.decode_linear()),
                        self.cbrt,
                    )?;
                    evaluations += 1;
                    for ch in 0..3 {
                        jac[ch][axis] = (other[ch] - value[ch]) / 1e-5;
                    }
                }
                let mut normal = [[0.; 4]; 4];
                let mut rhs = [0.; 4];
                for i in 0..4 {
                    for j in 0..4 {
                        normal[i][j] = (0..3).map(|ch| jac[ch][i] * jac[ch][j]).sum();
                    }
                    normal[i][i] += 1e-9;
                    rhs[i] = (0..3).map(|ch| jac[ch][i] * (wanted[ch] - value[ch])).sum();
                }
                let direction = solve(normal, rhs);
                let largest = direction.iter().copied().map(f64::abs).fold(0., f64::max);
                if !largest.is_finite() {
                    break;
                }
                let mut scale = if largest > 0.5 { 0.5 / largest } else { 1. };
                let mut improved = false;
                for _ in 0..20 {
                    let trial =
                        std::array::from_fn(|i| (current[i] + scale * direction[i]).max(0.));
                    if let Ok(recipe) = self.palette.recipe(trial) {
                        let candidate = distance(
                            metric(conversion::gamut_map(recipe.decode_linear()), self.cbrt)?,
                            wanted,
                        );
                        evaluations += 1;
                        if !candidate.is_finite() {
                            return Err(PaletteError::InvalidMetric);
                        }
                        if candidate < score - 1e-22 {
                            current = recipe.proportions();
                            score = candidate;
                            improved = true;
                            break;
                        }
                    }
                    scale *= 0.5;
                }
                if score < best_score {
                    best = current;
                    best_score = score;
                }
                if !improved || best_score <= 1e-18 {
                    break;
                }
            }
            while step >= 1e-8 && evaluations - start_count < EVALUATIONS_PER_START {
                let mut next = current;
                let mut next_score = score;
                for from in 0..4 {
                    let delta = step.min(current[from]);
                    if delta == 0. {
                        continue;
                    }
                    for to in 0..4 {
                        if evaluations - start_count >= EVALUATIONS_PER_START {
                            break;
                        }
                        if from == to {
                            continue;
                        }
                        let mut trial = current;
                        trial[from] -= delta;
                        trial[to] += delta;
                        let recipe = self.palette.recipe(trial)?;
                        let rgb = conversion::gamut_map(recipe.decode_linear());
                        let candidate = distance(metric(rgb, self.cbrt)?, wanted);
                        evaluations += 1;
                        if !candidate.is_finite() {
                            return Err(PaletteError::InvalidMetric);
                        }
                        if candidate < next_score - 1e-22 {
                            next_score = candidate;
                            next = recipe.proportions();
                        }
                    }
                }
                if next_score < score {
                    current = next;
                    score = next_score;
                } else {
                    step *= 0.5;
                }
                if score < best_score {
                    best = current;
                    best_score = score;
                }
                if best_score <= 1e-18 {
                    break;
                }
            }
        }
        let recipe = self.palette.recipe(best)?;
        let achieved_linear = conversion::gamut_map(recipe.decode_linear());
        let error_ok100 = 100. * distance(metric(achieved_linear, self.cbrt)?, wanted).sqrt();
        Ok(ColorMatch {
            recipe,
            achieved_linear,
            error_ok100,
            evaluations,
        })
    }
}

fn metric(linear: [f64; 3], cbrt: fn(f64) -> f64) -> Result<[f64; 3], PaletteError> {
    let value = conversion::mat(
        conversion::LAB,
        conversion::mat(conversion::LMS, linear).map(cbrt),
    );
    if value.iter().all(|v| v.is_finite()) {
        Ok(value)
    } else {
        Err(PaletteError::InvalidMetric)
    }
}
fn distance(a: [f64; 3], b: [f64; 3]) -> f64 {
    a.into_iter()
        .zip(b)
        .map(|(a, b)| {
            let d = a - b;
            d * d
        })
        .sum()
}

fn solve(mut a: [[f64; 4]; 4], mut b: [f64; 4]) -> [f64; 4] {
    for i in 0..4 {
        let mut pivot = i;
        for j in i + 1..4 {
            if a[j][i].abs() > a[pivot][i].abs() {
                pivot = j;
            }
        }
        a.swap(i, pivot);
        b.swap(i, pivot);
        let scale = a[i][i];
        if scale.abs() < 1e-24 {
            return [0.; 4];
        }
        for j in i..4 {
            a[i][j] /= scale;
        }
        b[i] /= scale;
        for row in 0..4 {
            if row == i {
                continue;
            }
            let factor = a[row][i];
            for column in i..4 {
                a[row][column] -= factor * a[i][column];
            }
            b[row] -= factor * b[i];
        }
    }
    b
}
