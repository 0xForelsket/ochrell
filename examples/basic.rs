use ochrell::{Color, PigmentMixer};
fn main() {
    let mixer = PigmentMixer::default();
    let a = Color::srgb8(255, 220, 0);
    let b = Color::srgb8(20, 70, 255);
    println!("{:?}", mixer.mix(a, b, 0.5).to_srgb8());
}
