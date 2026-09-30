//! Prepare once, optionally save the table, then decode persistent recipes.
use ochrell::{palette::synthetic_four, palette_lut::PaletteLut};
use std::{path::PathBuf, time::Instant};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let palette = synthetic_four();
    let path = std::env::args_os().nth(1).map(PathBuf::from);
    let start = Instant::now();
    let lut = if let Some(file) = path.as_ref().filter(|p| p.exists()) {
        PaletteLut::from_bytes(palette, &std::fs::read(file)?)?
    } else {
        let prepared = PaletteLut::build(palette, 65)?;
        if let Some(file) = &path {
            if let Some(parent) = file.parent().filter(|p| !p.as_os_str().is_empty()) {
                std::fs::create_dir_all(parent)?;
            }
            std::fs::write(file, prepared.to_bytes())?;
        }
        prepared
    };
    println!(
        "{}: {:?}, {} nodes per axis, {} payload bytes, ready in {:.2} ms",
        palette.id(),
        lut.mapping(),
        lut.resolution(),
        lut.payload_bytes(),
        start.elapsed().as_secs_f64() * 1000.
    );
    let green = palette.recipe([1., 0., 1., 0.])?;
    let white = palette.paint("white")?;
    let tint = green.interpolate(white, 0.3)?;
    println!(
        "Green: {:?}; tint: {:?}",
        lut.decode(&green)?.to_srgb8(),
        lut.decode(&tint)?.to_srgb8()
    );
    assert_eq!(
        green.to_le_bytes(),
        palette
            .recipe_from_bytes(&green.to_le_bytes())?
            .to_le_bytes()
    );
    Ok(())
}
