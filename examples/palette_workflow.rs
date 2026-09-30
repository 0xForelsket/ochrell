//! Demonstrate target matching and create/load an independently defined package.
use ochrell::{
    palette::{synthetic_four, AmountBasis, Palette, PaletteMetadata},
    palette_lut::PaletteLut,
    palette_match::ColorMatcher,
    Color,
};
use std::{path::PathBuf, time::Instant};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let dir = std::env::args_os()
        .nth(1)
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("target/palette-workflow"));
    std::fs::create_dir_all(&dir)?;
    let original = synthetic_four();
    let mut k = *original.absorption();
    let mut s = *original.scattering();
    for i in 0..81 {
        k[i][3] *= 2.;
        s[i][3] *= 2.;
    }
    let custom=Palette::from_optics(PaletteMetadata{id:"synthetic-strong-white-v1",paint_names:original.paint_names(),amount_basis:AmountBasis::Relative,provenance:"Ochrell example: Synthetic Four with doubled white strength. Synthetic data; CIE projection CC BY-SA 4.0."},k,s)?;
    for (name, palette) in [("synthetic-four", original), ("strong-white", &custom)] {
        let bytes = palette.to_bytes();
        std::fs::write(dir.join(format!("{name}.opp")), &bytes)?;
        let loaded = Palette::from_bytes(&std::fs::read(dir.join(format!("{name}.opp")))?)?;
        let matcher = ColorMatcher::new(&loaded)?;
        let mut rng = 271828_u64;
        let mut max_error: f64 = 0.;
        let mut evaluations = 0;
        let start = Instant::now();
        let mut rows = String::from("index,error_ok100,evaluations\n");
        for index in 0..1024 {
            let mut amounts = std::array::from_fn(|_| {
                rng ^= rng << 13;
                rng ^= rng >> 7;
                rng ^= rng << 17;
                (rng >> 11) as f64 / (1_u64 << 53) as f64
            });
            if index % 3 == 0 {
                amounts[index % 4] = 0.;
            }
            let target = loaded.recipe(amounts)?.decode();
            let found = matcher.match_color(target)?;
            max_error = max_error.max(found.error_ok100);
            evaluations += found.evaluations;
            rows.push_str(&format!(
                "{index},{:.12},{}\n",
                found.error_ok100, found.evaluations
            ));
        }
        println!("{name} fresh seed 271828, 1024 reachable targets: max error {max_error:.8}, mean evaluations {:.1}, total {:.2} ms",evaluations as f64/1024.,start.elapsed().as_secs_f64()*1000.);
        std::fs::write(dir.join(format!("{name}-holdout.csv")), rows)?;
        assert!(max_error <= 0.10, "fresh matching acceptance failed");
        let lut = PaletteLut::build(&loaded, 65)?;
        std::fs::write(dir.join(format!("{name}.opl")), lut.to_bytes())?;
        for target in [Color::srgb8(80, 170, 120), Color::srgb8(0, 0, 0)] {
            let start = Instant::now();
            let result = matcher.match_color(target)?;
            println!("{} target {:?}, achieved {:?}, recipe {:?}, error {:.6} OKLab*100, {} evaluations, {:.2} ms",loaded.id(),target.to_srgb8(),result.color().to_srgb8(),result.recipe.proportions(),result.error_ok100,result.evaluations,start.elapsed().as_secs_f64()*1000.);
        }
    }
    Ok(())
}
