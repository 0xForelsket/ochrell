//! Machine-readable actual Rust reference outputs for tools/check_palette.py.
use ochrell::palette::synthetic_four;

fn main() {
    let p = synthetic_four();
    let emit = |amounts| {
        let recipe = p.recipe(amounts).unwrap();
        let mut values = recipe.proportions().to_vec();
        values.extend(recipe.reflectance());
        values.extend(recipe.decode_linear());
        values.extend(recipe.decode().channels().map(|v| v as f64));
        println!(
            "{}",
            values
                .iter()
                .map(|v| format!("{v:.17e}"))
                .collect::<Vec<_>>()
                .join(",")
        );
    };
    for paint in 0..4 {
        let mut amounts = [0.; 4];
        amounts[paint] = 1.;
        emit(amounts);
    }
    for a in 0..4 {
        for b in a + 1..4 {
            for step in 0..=64 {
                let mut amounts = [0.; 4];
                amounts[a] = 1. - step as f64 / 64.;
                amounts[b] = step as f64 / 64.;
                emit(amounts);
            }
        }
    }
    let mut rng = 1907_u64;
    for _ in 0..1024 {
        emit(std::array::from_fn(|_| {
            rng ^= rng << 13;
            rng ^= rng >> 7;
            rng ^= rng << 17;
            (rng >> 11) as f64 / (1_u64 << 53) as f64
        }));
    }
}
