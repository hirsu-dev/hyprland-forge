use crate::state::{Phase, State, Target};
use alloc::{vec, vec::Vec};
use font8x8::{BASIC_FONTS, UnicodeFonts};

const BG: u32 = 0x100d16;
const INK: u32 = 0xf4edf5;
const MUTED: u32 = 0xbdaab8;
const YELLOW: u32 = 0xfcee0a;
const CYAN: u32 = 0x74f7ef;
const RED: u32 = 0xff4d61;

pub struct Frame {
    pub pixels: Vec<u32>,
    pub width: usize,
    pub height: usize,
    scale: i32,
    ox: i32,
    oy: i32,
}

impl Frame {
    pub fn new(width: usize, height: usize) -> Option<Self> {
        if width < 640 || height < 480 || width > 1920 || height > 1200 {
            return None;
        }
        let scale = ((width * 1024 / 1920).min(height * 1024 / 1080)) as i32;
        Some(Self {
            pixels: vec![BG; width.checked_mul(height)?],
            width,
            height,
            scale,
            ox: (width as i32 - 1920 * scale / 1024) / 2,
            oy: (height as i32 - 1080 * scale / 1024) / 2,
        })
    }

    fn rect(&mut self, x: i32, y: i32, w: i32, h: i32, color: u32) {
        let left = (self.ox + x * self.scale / 1024).clamp(0, self.width as i32) as usize;
        let top = (self.oy + y * self.scale / 1024).clamp(0, self.height as i32) as usize;
        let right = (self.ox + (x + w) * self.scale / 1024).clamp(0, self.width as i32) as usize;
        let bottom = (self.oy + (y + h) * self.scale / 1024).clamp(0, self.height as i32) as usize;
        if right <= left || bottom <= top {
            return;
        }
        for row in top..bottom {
            self.pixels[row * self.width + left..row * self.width + right].fill(color);
        }
    }

    fn line(&mut self, x1: i32, y1: i32, x2: i32, y2: i32, color: u32) {
        let steps = (x2 - x1).abs().max((y2 - y1).abs()).max(1);
        for n in 0..=steps {
            self.rect(
                x1 + (x2 - x1) * n / steps,
                y1 + (y2 - y1) * n / steps,
                2,
                2,
                color,
            );
        }
    }

    fn text(&mut self, x: i32, y: i32, text: &str, size: i32, color: u32) {
        for (index, character) in text.chars().enumerate() {
            if let Some(glyph) = BASIC_FONTS.get(character) {
                for (row, bits) in glyph.iter().enumerate() {
                    for bit in 0..8 {
                        if bits & (1 << bit) != 0 {
                            self.rect(
                                x + (index as i32 * 9 + bit) * size,
                                y + row as i32 * size,
                                size,
                                size,
                                color,
                            );
                        }
                    }
                }
            }
        }
    }

    fn border(&mut self, x: i32, y: i32, w: i32, h: i32, color: u32) {
        self.rect(x, y, w, 2, color);
        self.rect(x, y + h - 2, w, 2, color);
        self.rect(x, y, 2, h, color);
        self.rect(x + w - 2, y, 2, h, color);
    }

    fn brand(&mut self, x: i32, y: i32) {
        self.rect(x, y, 12, 96, YELLOW);
        self.rect(x, y, 64, 12, YELLOW);
        self.rect(x, y + 42, 52, 12, YELLOW);
        let o = x + 84;
        self.rect(o, y, 64, 96, YELLOW);
        self.rect(o + 12, y + 12, 40, 72, BG);
        for n in 0..10 {
            self.rect(o, y + n, 10 - n, 1, BG);
            self.rect(o + 54 + n, y + n, 10 - n, 1, BG);
            self.rect(o, y + 95 - n, 10 - n, 1, BG);
            self.rect(o + 54 + n, y + 95 - n, 10 - n, 1, BG);
        }
        let r = x + 168;
        self.rect(r, y, 12, 96, YELLOW);
        self.rect(r, y, 64, 54, YELLOW);
        self.rect(r + 12, y + 12, 40, 30, BG);
        for n in 0..12 {
            self.line(r + 32 + n, y + 48, r + 58 + n, y + 94, YELLOW);
        }
        let g = x + 252;
        self.rect(g, y, 12, 96, YELLOW);
        self.rect(g, y, 64, 12, YELLOW);
        self.rect(g, y + 84, 64, 12, YELLOW);
        self.rect(g + 32, y + 42, 32, 12, YELLOW);
        self.rect(g + 52, y + 42, 12, 54, YELLOW);
        let e = x + 336;
        self.rect(e, y, 12, 96, YELLOW);
        self.rect(e, y, 64, 12, YELLOW);
        self.rect(e, y + 42, 52, 12, YELLOW);
        self.rect(e, y + 84, 64, 12, YELLOW);
    }

    fn logo(&mut self, reveal: i32) {
        let points = [
            (1200, 330),
            (1560, 330),
            (1500, 400),
            (1300, 400),
            (1270, 465),
            (1460, 465),
            (1405, 532),
            (1240, 532),
            (1160, 713),
            (1065, 713),
        ];
        for y in 330..=713 {
            if y > 330 + 383 * reveal / 1024 {
                continue;
            }
            let mut intersections = [0; 10];
            let mut count = 0;
            for i in 0..points.len() {
                let (x1, y1) = points[i];
                let (x2, y2) = points[(i + 1) % points.len()];
                if (y1 <= y && y < y2) || (y2 <= y && y < y1) {
                    intersections[count] = x1 + (y - y1) * (x2 - x1) / (y2 - y1);
                    count += 1;
                }
            }
            intersections[..count].sort_unstable();
            for pair in intersections[..count].chunks_exact(2) {
                self.rect(pair[0], y, pair[1] - pair[0], 1, YELLOW);
            }
        }
    }

    pub fn draw(&mut self, state: &State) {
        self.pixels.fill(BG);
        for x in (48..1920).step_by(64) {
            self.line(x, 0, x, 1080, 0x211923);
        }
        for y in (42..1080).step_by(64) {
            self.line(0, y, 1920, y, 0x211923);
        }
        for inset in (0..150).step_by(30) {
            let p = [
                (1140 + inset, 178 + inset),
                (1530 - inset, 178 + inset),
                (1770 - inset, 418),
                (1770 - inset, 742 - inset),
                (1560 - inset, 930 - inset),
                (1170 + inset, 930 - inset),
                (970 + inset, 730 - inset),
                (970 + inset, 340 + inset),
            ];
            for i in 0..p.len() {
                self.line(
                    p[i].0,
                    p[i].1,
                    p[(i + 1) % p.len()].0,
                    p[(i + 1) % p.len()].1,
                    0x50303e,
                );
            }
        }
        let reveal = if state.phase() == Phase::Intro && state.motion() {
            (state.elapsed().min(1000) * 1024 / 1000) as i32
        } else {
            1024
        };
        self.logo(reveal);
        self.line(1000, 796, 1128, 924, CYAN);
        self.line(1128, 924, 1440, 924, CYAN);
        self.line(1540, 496, 1640, 396, RED);
        self.line(1640, 396, 1640, 748, RED);
        self.line(1640, 748, 1495, 893, RED);
        self.text(96, 76, "F / OVERDRIVE SYSTEMS", 2, YELLOW);
        self.text(1440, 76, "NATIVE / UEFI", 2, MUTED);
        self.line(96, 118, 1824, 118, 0x693642);
        self.text(96, 198, "FORGE / LOCAL STARTUP", 2, CYAN);
        let slide = if state.motion() {
            (1024 - reveal) * 32 / 1024
        } else {
            0
        };
        self.brand(96 - slide, 270);
        self.text(96, 400, "YOUR MACHINE. YOUR SIGNAL.", 3, INK);
        self.rect(96, 452, 694, 3, RED);
        self.line(96, 972, 1824, 972, 0x693642);
        self.text(96, 1004, "F2 MOTION / ENTER CONFIRM / ESC CLEAR", 2, MUTED);
        self.text(1410, 1004, "FORGE / EXPERIMENTAL", 2, RED);
        if state.motion() {
            let y = ((state.time() / 9) % 900 + 140) as i32;
            self.rect(96, y, 1730, 1, 0x283b3f);
        }
        match state.phase() {
            Phase::Intro => {
                self.text(96, 526, "INITIALIZING LOCAL INTERFACE", 2, CYAN);
                self.rect(96, 582, 694, 4, 0x693642);
                self.rect(96, 582, 694 * reveal / 1024, 4, CYAN);
                self.text(96, 638, "NO NETWORK / NO OPERATING SYSTEM LOADED", 2, MUTED);
            }
            Phase::Password | Phase::Verifying | Phase::Denied | Phase::Unlocking => {
                self.text(96, 510, "LOCAL ACCESS KEY", 2, CYAN);
                self.rect(96, 556, 730, 110, 0x1d141f);
                let edge = match state.phase() {
                    Phase::Denied => RED,
                    Phase::Unlocking => CYAN,
                    _ => YELLOW,
                };
                self.border(96, 556, 730, 110, edge);
                let count = state.password_length().min(22);
                for index in 0..count {
                    self.text(120 + index as i32 * 28, 598, "*", 3, INK);
                }
                if state.phase() == Phase::Password && (state.time() / 500) % 2 == 0 {
                    self.rect(120 + count as i32 * 28, 593, 3, 30, YELLOW);
                }
                self.rect(96, 710, 730, 66, edge);
                self.text(
                    120,
                    732,
                    match state.phase() {
                        Phase::Denied => "ACCESS DENIED / PLEASE WAIT",
                        Phase::Verifying => "VERIFYING ACCESS...",
                        Phase::Unlocking => "ACCESS GRANTED",
                        _ => "ENTER TO UNLOCK   >",
                    },
                    2,
                    BG,
                );
                self.text(96, 826, "LOCAL ACCESS / OFFLINE", 2, MUTED);
                self.text(96, 874, "UNLOCK TO SELECT YOUR ENVIRONMENT", 2, MUTED);
                if state.phase() == Phase::Unlocking {
                    let width = if state.motion() {
                        (state.elapsed().min(650) * 730 / 650) as i32
                    } else {
                        730
                    };
                    self.rect(96, 790, width, 4, CYAN);
                }
            }
            Phase::Selector | Phase::Launching | Phase::Missing => {
                self.text(96, 510, "CHOOSE YOUR ENVIRONMENT", 2, CYAN);
                for (index, title, detail, target) in [
                    (0, "FORGE OS", "ARCH / HYPRLAND", Target::Forge),
                    (1, "WINDOWS 11", "WINDOWS BOOT MANAGER", Target::Windows),
                ] {
                    let y = 562 + index * 132;
                    let selected = state.target() == target;
                    self.rect(96, y, 730, 106, if selected { YELLOW } else { 0x1d141f });
                    self.border(96, y, 730, 106, if selected { YELLOW } else { 0x693642 });
                    self.text(124, y + 20, title, 3, if selected { BG } else { INK });
                    self.text(124, y + 66, detail, 2, if selected { BG } else { MUTED });
                }
                self.text(
                    96,
                    860,
                    match state.phase() {
                        Phase::Launching => "LAUNCHING / HANDING OFF TO OS...",
                        Phase::Missing => "LOADER UNAVAILABLE / ENTER TO RETURN",
                        _ => "ARROWS SELECT / ENTER LAUNCH / ESC LOCK",
                    },
                    2,
                    if state.phase() == Phase::Missing {
                        RED
                    } else {
                        CYAN
                    },
                );
                if state.phase() == Phase::Launching {
                    self.rect(
                        96,
                        904,
                        (state.elapsed().min(450) * 730 / 450) as i32,
                        4,
                        CYAN,
                    );
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state::Key;

    #[test]
    fn bounded_resolutions_and_motion_frames() {
        assert!(Frame::new(0, 0).is_none());
        assert!(Frame::new(8000, 8000).is_none());
        let mut frame = Frame::new(1280, 720).unwrap();
        let mut state = State::default();
        frame.draw(&state);
        let first = frame.pixels.clone();
        state.tick(500);
        frame.draw(&state);
        assert_ne!(first, frame.pixels);
        state.tick(700);
        state.key(Key::Char(b'x'));
        frame.draw(&state);
        assert_eq!(frame.pixels.len(), 1280 * 720);
    }
}
