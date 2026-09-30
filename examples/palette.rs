//! Inspect the synthetic reference with `cargo run --release --example palette`.
use ochrell::palette::{synthetic_four, Recipe};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let palette = synthetic_four();
    println!("{} (synthetic reference, no LUT)", palette.id());
    println!(
        "Reference recipe: {} bytes in memory, {} bytes serialized",
        std::mem::size_of::<Recipe<'_>>(),
        ochrell::palette::RECIPE_BYTES
    );
    for name in palette.paint_names() {
        println!("{name}: {:?}", palette.paint(name)?.decode().to_srgb8());
    }
    let yellow = palette.paint("yellow")?;
    let red = palette.paint("red")?;
    let blue = palette.paint("blue")?;
    let white = palette.paint("white")?;
    for (label, recipe) in [
        ("yellow + blue", yellow.interpolate(blue, 0.5)?),
        ("red + blue", red.interpolate(blue, 0.5)?),
        ("red + white", red.interpolate(white, 0.5)?),
        (
            "four paints",
            Recipe::weighted(&[(yellow, 2.), (red, 1.), (blue, 1.), (white, 3.)])?,
        ),
    ] {
        let restored = palette.recipe_from_bytes(&recipe.to_le_bytes())?;
        assert_eq!(recipe.proportions(), restored.proportions());
        println!(
            "{label}: {:?}, recipe {:?}",
            restored.decode().to_srgb8(),
            restored.proportions()
        );
    }
    Ok(())
}
