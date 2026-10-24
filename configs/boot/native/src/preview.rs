use forge_startup::{
    state::{CONFIG_SIZE, Config, Key, ROUNDS, State},
    visual::Frame,
};
use pbkdf2::{pbkdf2_hmac, sha2::Sha256};
use std::{
    fs::{self, File},
    io::Write,
    path::Path,
};

fn save(frame: &Frame, path: &Path) {
    let mut file = File::create(path).unwrap();
    write!(file, "P6\n{} {}\n255\n", frame.width, frame.height).unwrap();
    let mut rgb = Vec::with_capacity(frame.pixels.len() * 3);
    for pixel in &frame.pixels {
        rgb.extend_from_slice(&[(pixel >> 16) as u8, (pixel >> 8) as u8, *pixel as u8]);
    }
    file.write_all(&rgb).unwrap();
}

fn main() {
    let destination = std::env::args_os().nth(1).expect("Output folder required");
    let destination = Path::new(&destination);
    fs::create_dir_all(destination).unwrap();
    let mut state = State::default();
    let mut frame = Frame::new(1280, 720).unwrap();
    for index in 0..28 {
        frame.draw(&state);
        save(&frame, &destination.join(format!("intro-{index:03}.ppm")));
        state.tick(40);
    }
    frame.draw(&state);
    save(&frame, &destination.join("password.ppm"));
    for byte in b"ephemeral-preview-password" {
        state.key(Key::Char(*byte));
    }
    frame.draw(&state);
    save(&frame, &destination.join("masked.ppm"));
    let mut bytes = [1; CONFIG_SIZE];
    bytes[..4].copy_from_slice(b"FGX1");
    bytes[4..8].copy_from_slice(&ROUNDS.to_le_bytes());
    pbkdf2_hmac::<Sha256>(
        b"ephemeral-preview-password",
        &[1; 32],
        ROUNDS,
        &mut bytes[72..],
    );
    state.key(Key::Enter);
    state.verify(&Config::parse(&bytes).unwrap());
    state.tick(650);
    frame.draw(&state);
    save(&frame, &destination.join("selector.ppm"));
    state.key(Key::Next);
    frame.draw(&state);
    save(&frame, &destination.join("windows.ppm"));
}
