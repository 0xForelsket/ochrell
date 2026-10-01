//! Check a native 31-band, eight-paint package against external recipe probes.
use ochrell::palette::PaletteN;
use std::{error::Error, fs};

fn main() -> Result<(), Box<dyn Error>> {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    if args.len() != 3 {
        return Err("Expected palette.opp recipes.f64 predictions.f64".into());
    }
    let bytes = fs::read(&args[0])?;
    let palette = PaletteN::<8, 31>::from_bytes(&bytes)?;
    assert_eq!(bytes, palette.to_bytes());
    assert_eq!(palette.spectral_grid(), (400, 10, 31));
    let input = fs::read(&args[1])?;
    if input.len() % 64 != 0 {
        return Err("Expected groups of eight little-endian f64 amounts".into());
    }
    let mut output = Vec::new();
    for record in input.chunks_exact(64) {
        let amounts = std::array::from_fn(|i| {
            f64::from_le_bytes(record[i * 8..(i + 1) * 8].try_into().unwrap())
        });
        let recipe = palette.recipe(amounts)?;
        let restored = palette.recipe_from_bytes(&recipe.to_bytes())?;
        assert_eq!(recipe.to_bytes(), restored.to_bytes());
        for name in palette.paint_names() {
            let pure = palette.paint(name)?;
            assert_eq!(
                recipe.interpolate(pure, 0.13)?.decode_linear(),
                restored.interpolate(pure, 0.13)?.decode_linear()
            );
        }
        for value in recipe
            .reflectance()
            .into_iter()
            .chain(recipe.decode_linear())
        {
            output.extend_from_slice(&value.to_le_bytes());
        }
    }
    fs::write(&args[2], output)?;
    println!(
        "{} recipes, {} pair controls; exact package/recipe replay",
        input.len() / 64,
        palette.pair_controls().len()
    );
    Ok(())
}
