use crate::glyph::glyph;
use crate::state::{Phase, State, Target};
use alloc::{vec, vec::Vec};

const BG: u32 = 0x080d16;
const INK: u32 = 0xe9f4f5;
const MUTED: u32 = 0x839ba8;
const CYAN: u32 = 0x74f7df;
const RED: u32 = 0xff4264;
const BLUE: u32 = 0x80bcff;
const TRACK: u32 = 0x263b48;
const ORBIT: [(i32, i32); 16] = [
    (0, -1024),
    (392, -946),
    (724, -724),
    (946, -392),
    (1024, 0),
    (946, 392),
    (724, 724),
    (392, 946),
    (0, 1024),
    (-392, 946),
    (-724, 724),
    (-946, 392),
    (-1024, 0),
    (-946, -392),
    (-724, -724),
    (-392, -946),
];

fn ease(elapsed: u32, start: u32, duration: u32) -> i32 {
    let p = (elapsed.saturating_sub(start).min(duration) * 1024 / duration) as i32;
    1024 - (1024 - p).pow(3) / 1_048_576
}

fn mix(a: u32, b: u32, amount: i32) -> u32 {
    let amount = amount.clamp(0, 1024) as u32;
    let mut result = 0;
    for shift in [0, 8, 16] {
        result |=
            (((a >> shift & 255) * (1024 - amount) + (b >> shift & 255) * amount) / 1024) << shift;
    }
    result
}

pub struct Frame {
    pub pixels: Vec<u32>,
    pub width: usize,
    pub height: usize,
    scale: i32,
    ox: i32,
    oy: i32,
    gate_clip: Option<(bool, i32)>,
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
            gate_clip: None,
        })
    }

    fn rect(&mut self, x: i32, y: i32, w: i32, h: i32, color: u32) {
        if w <= 0 || h <= 0 {
            return;
        }
        let left = (self.ox + x * self.scale / 1024).clamp(0, self.width as i32) as usize;
        let top = (self.oy + y * self.scale / 1024).clamp(0, self.height as i32) as usize;
        let right = (self.ox + (x + w) * self.scale / 1024).clamp(0, self.width as i32) as usize;
        let bottom = (self.oy + (y + h) * self.scale / 1024).clamp(0, self.height as i32) as usize;
        if right <= left || bottom <= top {
            return;
        }
        for row in top..bottom {
            let (mut a, mut b) = (left, right);
            if let Some((first, offset)) = self.gate_clip {
                let y = (row as i32 - self.oy) * 1024 / self.scale;
                let seam = (self.ox + (1344 - y * 768 / 1080 + offset) * self.scale / 1024)
                    .clamp(0, self.width as i32) as usize;
                if first {
                    b = b.min(seam);
                } else {
                    a = a.max(seam);
                }
            }
            if b > a {
                self.pixels[row * self.width + a..row * self.width + b].fill(color);
            }
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

    fn glow(&mut self, x1: i32, y1: i32, x2: i32, y2: i32, color: u32) {
        for (offset, amount) in [(-4, 90), (-2, 210), (2, 210), (4, 90), (0, 1024)] {
            self.line(x1 + offset, y1, x2 + offset, y2, mix(BG, color, amount));
        }
    }

    fn text(&mut self, x: i32, y: i32, text: &str, size: i32, color: u32) {
        for (index, character) in text.chars().enumerate() {
            for (row, bits) in glyph(character).iter().enumerate() {
                for bit in 0..5 {
                    if bits & (1 << (4 - bit)) != 0 {
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

    fn polygon(&mut self, points: &[(i32, i32)], color: u32) {
        let top = points.iter().map(|p| p.1).min().unwrap_or(0).max(0);
        let bottom = points.iter().map(|p| p.1).max().unwrap_or(0).min(1080);
        for y in top..bottom {
            let mut hits = [0; 32];
            let mut count = 0;
            for i in 0..points.len() {
                let (x1, y1) = points[i];
                let (x2, y2) = points[(i + 1) % points.len()];
                if (y1 <= y && y < y2) || (y2 <= y && y < y1) {
                    hits[count] = x1 + (y - y1) * (x2 - x1) / (y2 - y1);
                    count += 1;
                }
            }
            hits[..count].sort_unstable();
            for pair in hits[..count].chunks_exact(2) {
                self.rect(pair[0], y, pair[1] - pair[0], 2, color);
            }
        }
    }

    fn panel(&mut self, x: i32, y: i32, w: i32, h: i32, fill: u32, edge: u32) {
        let cut = 20;
        let points = [
            (x + cut, y),
            (x + w, y),
            (x + w, y + h - cut),
            (x + w - cut, y + h),
            (x, y + h),
            (x, y + cut),
        ];
        self.polygon(&points, fill);
        for i in 0..points.len() {
            let (a, b) = (points[i], points[(i + 1) % points.len()]);
            self.line(a.0, a.1, b.0, b.1, edge);
        }
    }

    fn brand(&mut self, x: i32, y: i32, color: u32) {
        self.rect(x, y, 12, 96, color);
        self.rect(x, y, 64, 12, color);
        self.rect(x, y + 42, 52, 12, color);
        let o = x + 84;
        self.rect(o, y, 64, 96, color);
        self.rect(o + 12, y + 12, 40, 72, BG);
        for n in 0..10 {
            self.rect(o, y + n, 10 - n, 1, BG);
            self.rect(o + 54 + n, y + n, 10 - n, 1, BG);
            self.rect(o, y + 95 - n, 10 - n, 1, BG);
            self.rect(o + 54 + n, y + 95 - n, 10 - n, 1, BG);
        }
        let r = x + 168;
        self.rect(r, y, 12, 96, color);
        self.rect(r, y, 64, 54, color);
        self.rect(r + 12, y + 12, 40, 30, BG);
        for n in 0..12 {
            self.line(r + 32 + n, y + 48, r + 58 + n, y + 94, color);
        }
        let g = x + 252;
        self.rect(g, y, 12, 96, color);
        self.rect(g, y, 64, 12, color);
        self.rect(g, y + 84, 64, 12, color);
        self.rect(g + 32, y + 42, 32, 12, color);
        self.rect(g + 52, y + 42, 12, 54, color);
        let e = x + 336;
        self.rect(e, y, 12, 96, color);
        self.rect(e, y, 64, 12, color);
        self.rect(e, y + 42, 52, 12, color);
        self.rect(e, y + 84, 64, 12, color);
    }

    fn hero(&mut self, x: i32, y: i32, color: u32) {
        for (a, b, w, h) in [
            (0, 0, 12, 96),
            (0, 0, 64, 12),
            (0, 42, 52, 12),
            (84, 10, 12, 76),
            (136, 10, 12, 76),
            (94, 0, 44, 12),
            (94, 84, 44, 12),
            (168, 0, 12, 96),
            (168, 0, 64, 12),
            (220, 0, 12, 54),
            (168, 42, 64, 12),
            (252, 0, 12, 96),
            (252, 0, 64, 12),
            (252, 84, 64, 12),
            (284, 42, 32, 12),
            (304, 42, 12, 54),
            (336, 0, 12, 96),
            (336, 0, 64, 12),
            (336, 42, 52, 12),
            (336, 84, 64, 12),
        ] {
            self.rect(x + a * 2, y + b * 2, w * 2, h * 2, color);
        }
        for n in 0..24 {
            self.line(x + 400 + n, y + 96, x + 452 + n, y + 188, color);
        }
        for (a, b, c, d) in [
            (84, 10, 94, 0),
            (136, 0, 148, 10),
            (84, 86, 94, 96),
            (136, 96, 148, 86),
        ] {
            self.glow(x + a * 2, y + b * 2, x + c * 2, y + d * 2, color);
        }
    }

    fn emblem(&mut self, x: i32, y: i32, size: i32, color: u32) {
        let shape = [
            (80, 0),
            (360, 0),
            (310, 60),
            (130, 60),
            (104, 120),
            (280, 120),
            (230, 180),
            (78, 180),
            (0, 360),
            (-76, 360),
        ];
        let points: [(i32, i32); 10] =
            core::array::from_fn(|i| (x + shape[i].0 * size / 360, y + shape[i].1 * size / 360));
        self.polygon(&points, color);
    }

    fn orbit(&mut self, cx: i32, cy: i32, rx: i32, ry: i32, clock: u32, color: u32, motion: bool) {
        let points: [(i32, i32); 16] =
            core::array::from_fn(|i| (cx + ORBIT[i].0 * rx / 1024, cy + ORBIT[i].1 * ry / 1024));
        for i in 0..16 {
            let (a, b) = (points[i], points[(i + 1) % 16]);
            self.line(a.0, a.1, b.0, b.1, TRACK);
        }
        let cursor = if motion {
            (clock % 16384) as usize
        } else {
            2100
        };
        for trail in 0..3 {
            let position = (cursor + 16384 - trail * 220) % 16384;
            let edge = position / 1024;
            let step = (position % 1024) as i32;
            let (a, b) = (points[edge], points[(edge + 1) % 16]);
            let end = (step + 190).min(1024);
            self.glow(
                a.0 + (b.0 - a.0) * step / 1024,
                a.1 + (b.1 - a.1) * step / 1024,
                a.0 + (b.0 - a.0) * end / 1024,
                a.1 + (b.1 - a.1) * end / 1024,
                mix(TRACK, color, 1024 - trail as i32 * 270),
            );
        }
    }

    fn background(&mut self, state: &State) {
        self.pixels.fill(BG);
        for y in (0..1080).step_by(4) {
            self.rect(0, y, 1920, 1, 0x0c121c);
        }
        for x in (64..1920).step_by(96) {
            self.line(x, 128, x, 944, 0x12222e);
        }
        for y in (176..944).step_by(96) {
            self.line(64, y, 1856, y, 0x12222e);
        }
        let clock = if state.motion() { state.time() } else { 0 };
        for n in 0..4 {
            self.orbit(
                1392,
                548,
                242 + n * 36,
                278 + n * 33,
                clock
                    .wrapping_mul(2 + n as u32)
                    .wrapping_add(n as u32 * 1300),
                if n % 2 == 0 { CYAN } else { RED },
                state.motion(),
            );
        }
        self.emblem(1280, 378, 300, 0x14363d);
        self.emblem(1274, 372, 300, CYAN);
        self.line(1220, 754, 1290, 824, CYAN);
        self.line(1290, 824, 1510, 824, CYAN);
        self.text(1250, 862, "FORGE / GHOSTWIRE", 2, MUTED);
        for n in 0..28 {
            let step = (clock / 55 + n as u32 * 37) % 96;
            let height = 8 + (if step < 48 { step } else { 96 - step }) as i32 / 2;
            self.rect(
                1190 + n * 16,
                920 - height,
                5,
                height,
                if n % 7 == 0 { RED } else { 0x346268 },
            );
        }
        for n in 0..12 {
            let progress = ((clock / 5 + n as u32 * 277) % 2048) as i32;
            let x = 1050 + progress * 700 / 2048;
            let y = 215 + (n * 61) % 650;
            self.rect(x, y, 10 + n % 4 * 5, 2, mix(TRACK, CYAN, 300));
        }
        self.line(96, 118, 1824, 118, TRACK);
        self.line(96, 972, 1824, 972, TRACK);
        self.rect(96, 116, 118, 4, RED);
        self.rect(1706, 970, 118, 4, CYAN);
        for (x, y, dx, dy) in [
            (40, 38, 1, 1),
            (1880, 38, -1, 1),
            (40, 1042, 1, -1),
            (1880, 1042, -1, -1),
        ] {
            self.line(x, y, x + dx * 36, y, MUTED);
            self.line(x, y, x, y + dy * 24, MUTED);
        }
        self.text(96, 72, "F / OVERDRIVE SYSTEMS", 2, CYAN);
        self.text(1464, 72, "LOCAL / OFFLINE", 2, MUTED);
        self.text(96, 1006, "F2 MOTION / ENTER CONFIRM / ESC CLEAR", 2, MUTED);
        self.text(1410, 1006, "FORGE / EXPERIMENTAL", 2, RED);
        self.text(96, 196, "01 / LOCAL STARTUP", 2, CYAN);
        self.brand(96, 266, INK);
        self.text(96, 400, "YOUR MACHINE. YOUR SIGNAL.", 3, MUTED);
        self.rect(96, 454, 716, 2, TRACK);
        let marker = if state.motion() {
            (clock / 8 % 570) as i32
        } else {
            0
        };
        self.rect(96 + marker, 454, 146, 2, CYAN);
    }

    fn access(&mut self, state: &State) {
        let denied = state.phase() == Phase::Denied;
        let unlocking = state.phase() == Phase::Unlocking;
        let shake = if denied && state.motion() && state.elapsed() < 350 {
            let direction = if (state.elapsed() / 45) % 2 == 0 {
                1
            } else {
                -1
            };
            direction * (350 - state.elapsed()) as i32 * 9 / 350
        } else {
            0
        };
        let x = 96 + shake;
        let edge = if denied { RED } else { CYAN };
        self.text(96, 510, "IDENTITY / LOCAL ACCESS KEY", 2, MUTED);
        let pulse = if state.motion() {
            1024 - ease(state.input_age(), 0, 220)
        } else {
            0
        };
        self.panel(
            x,
            558,
            716,
            108,
            0x101c27,
            mix(TRACK, edge, 600 + pulse / 3),
        );
        self.rect(x + 20, 578, 3, 68, edge);
        for index in 0..state.password_length().min(22) {
            self.text(x + 48 + index as i32 * 28, 600, "*", 3, INK);
        }
        if state.phase() == Phase::Password
            && (!state.motion() || state.input_age() < 450 || state.time() / 500 % 2 == 0)
        {
            self.rect(
                x + 48 + state.password_length().min(22) as i32 * 28,
                596,
                3,
                30,
                CYAN,
            );
        }
        self.panel(
            96,
            708,
            716,
            66,
            if denied { 0x341a2a } else { 0x123639 },
            edge,
        );
        self.text(
            120,
            732,
            match state.phase() {
                Phase::Denied => "ACCESS DENIED / PLEASE WAIT",
                Phase::Verifying => "VERIFYING LOCAL KEY...",
                Phase::Unlocking => "ACCESS GRANTED / LINK ESTABLISHED",
                _ => "UNLOCK YOUR ENVIRONMENT    >",
            },
            2,
            if denied { RED } else { CYAN },
        );
        self.text(96, 832, "PASSWORD FIRST. ENVIRONMENT NEXT.", 2, MUTED);
        self.text(96, 878, "FORGE OS  /  WINDOWS 11", 2, MUTED);
        if unlocking {
            let p = if state.motion() {
                ease(state.elapsed(), 0, 650)
            } else {
                1024
            };
            self.rect(96, 800, 716 * p / 1024, 3, CYAN);
            self.glow(
                1070,
                300 + (600 * p / 1024),
                1720,
                300 + (600 * p / 1024),
                mix(TRACK, CYAN, 700),
            );
            for n in 0..8 {
                self.rect(
                    96 + n * 92,
                    684,
                    60 * ease(state.elapsed(), n as u32 * 40, 160) / 1024,
                    3,
                    CYAN,
                );
            }
        }
    }

    fn selector(&mut self, state: &State) {
        self.text(96, 510, "02 / CHOOSE YOUR ENVIRONMENT", 2, CYAN);
        let position = state.selection_position();
        for index in 0..2 {
            self.panel(96, 558 + index * 132, 716, 106, 0x101c27, TRACK);
        }
        let y = 558 + 132 * position / 1024;
        let color = mix(CYAN, BLUE, position);
        self.panel(96, y, 716, 106, mix(0x101c27, color, 120), color);
        self.rect(96, y + 25, 4, 56, color);
        for (index, title, detail, target) in [
            (0, "FORGE OS", "ARCH / HYPRLAND", Target::Forge),
            (1, "WINDOWS 11", "WINDOWS BOOT MANAGER", Target::Windows),
        ] {
            let base = 558 + index * 132;
            let selected = state.target() == target;
            let accent = if index == 0 { CYAN } else { BLUE };
            self.text(128, base + 20, title, 3, if selected { INK } else { MUTED });
            self.text(
                128,
                base + 66,
                detail,
                2,
                if selected { accent } else { MUTED },
            );
            if index == 0 {
                self.emblem(752, base + 26, 52, if selected { accent } else { TRACK });
            } else {
                for (dx, dy) in [(0, 0), (24, 0), (0, 24), (24, 24)] {
                    self.rect(
                        724 + dx,
                        base + 28 + dy,
                        19,
                        19,
                        if selected { accent } else { TRACK },
                    );
                }
            }
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
                MUTED
            },
        );
        self.text(96, 906, "LOCAL KEY ACCEPTED / READY", 2, color);
        if state.phase() == Phase::Selector && state.motion() {
            let entrance = 1024 - ease(state.elapsed(), 0, 360);
            if entrance > 0 {
                self.rect(96, 550, 724, 400 * entrance / 1024, BG);
            }
        }
    }

    fn redline(&mut self, elapsed: u32) {
        let open = ease(elapsed, 1450, 750);
        let split = open * 1920 / 1024;
        let beam = ease(elapsed, 580, 600) * 1080 / 1024;
        for y in 0..1080 {
            let seam = 1344 - y * 768 / 1080;
            let stripe = if y % 5 == 0 { 0x1c101d } else { 0x120c17 };
            self.rect(0, y, seam - split, 2, stripe);
            self.rect(seam + split, y, 1920 - seam - split, 2, 0x090d16);
            if y < beam {
                for (width, color) in [
                    (32, 0x2b1525),
                    (16, 0x572037),
                    (7, 0xa73350),
                    (3, RED),
                    (1, INK),
                ] {
                    self.rect(seam - split - width, y, width, 2, color);
                    self.rect(seam + split, y, width, 2, color);
                }
            }
        }
        let arrival = ease(elapsed, 100, 650);
        let offset = (1024 - arrival) * 180 / 1024;
        for first in [true, false] {
            let direction = if first { -1 } else { 1 };
            self.gate_clip = Some((first, direction * split));
            let x = 560 + direction * (split + offset);
            let y = 416 + direction * offset / 12;
            self.hero(x + direction * 4, y, mix(BG, RED, arrival / 4));
            self.hero(x, y, mix(0x2b1525, RED, arrival));
        }
        self.gate_clip = None;
        if elapsed < 1450 {
            self.text(
                676,
                620,
                "REDLINE / OPEN THE SIGNAL",
                2,
                mix(BG, INK, arrival),
            );
            for n in 0..8 {
                let y = 180 + n * 97;
                let seam = 1344 - y * 768 / 1080;
                let length = 40 + (elapsed as i32 / 8 + n * 37) % 130;
                self.rect(seam - length - 32, y, length, 2, 0x77334b);
                self.rect(seam + 32, y + 12, length / 2, 2, 0x30555c);
            }
            let stage = if elapsed < 580 {
                "01 / FORM THE WORDMARK"
            } else if elapsed < 1180 {
                "02 / CUT THE SIGNAL"
            } else {
                "03 / SPLIT THE GATE"
            };
            self.text(96, 74, "F / REDLINE STARTUP", 2, INK);
            self.text(96, 880, stage, 2, RED);
            self.text(96, 1006, "ENTER SKIP / F2 REDUCED MOTION", 2, MUTED);
            self.rect(96, 934, 1728, 3, 0x332030);
            self.rect(96, 934, 1728 * elapsed.min(1450) as i32 / 1450, 3, RED);
            if (1180..1450).contains(&elapsed) {
                let pulse = 1024 - ease(elapsed, 1180, 270);
                for n in 0..3 {
                    let y = 410 + n * 59;
                    let shift = pulse * (n * 7 + 3) / 1024;
                    self.rect(540 - shift, y, 820 + shift, 2, mix(0x211324, RED, pulse));
                }
            }
        }
        if elapsed >= 1180 {
            for n in 0..72 {
                let delay = (n % 8) * 12;
                let travel = ease(elapsed, 1180 + delay, 900 - delay);
                let y = 72 + (n as i32 * 137) % 920;
                let seam = 1344 - y * 768 / 1080;
                let sign = if n % 2 == 0 { -1 } else { 1 };
                let x = seam + sign * travel * (100 + n as i32 * 13) / 1024;
                let dy = ((n as i32 * 31) % 170 - 85) * travel / 1024;
                let length = 8 + (n as i32 % 7) * 5;
                let color = mix(
                    if n % 5 == 0 { INK } else { RED },
                    BG,
                    ease(elapsed, 1600, 600),
                );
                self.glow(x, y + dy, x + sign * length, y + dy - 5, color);
            }
        }
    }

    fn handoff(&mut self, state: &State) {
        if !state.motion() {
            return;
        }
        let close = ease(state.elapsed(), 60, 390);
        let accent = if state.target() == Target::Forge {
            CYAN
        } else {
            BLUE
        };
        for y in 0..1080 {
            let seam = 1344 - y * 768 / 1080;
            let gap = (1024 - close) * 1920 / 1024;
            self.rect(0, y, seam - gap, 2, BG);
            self.rect(seam + gap, y, 1920 - seam - gap, 2, BG);
            if close > 0 && close < 1024 {
                self.rect(seam - gap - 3, y, 3, 2, accent);
                self.rect(seam + gap, y, 3, 2, accent);
            }
        }
        if close > 600 {
            self.text(
                772,
                480,
                if state.target() == Target::Forge {
                    "FORGE OS"
                } else {
                    "WINDOWS 11"
                },
                4,
                mix(BG, accent, ease(state.elapsed(), 210, 160)),
            );
            self.text(
                772,
                548,
                "OPENING YOUR ENVIRONMENT",
                2,
                mix(BG, MUTED, ease(state.elapsed(), 240, 160)),
            );
        }
    }

    pub fn draw(&mut self, state: &State) {
        self.background(state);
        match state.phase() {
            Phase::Intro
            | Phase::Password
            | Phase::Verifying
            | Phase::Denied
            | Phase::Unlocking => self.access(state),
            Phase::Selector | Phase::Launching | Phase::Missing => self.selector(state),
        }
        if state.phase() == Phase::Intro && state.motion() {
            self.redline(state.elapsed());
        }
        if state.phase() == Phase::Launching {
            self.handoff(state);
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
        for (width, height) in [(640, 480), (1280, 720), (1920, 1080), (1920, 1200)] {
            let mut frame = Frame::new(width, height).unwrap();
            let mut state = State::default();
            frame.draw(&state);
            let first = frame.pixels.clone();
            state.tick(500);
            frame.draw(&state);
            assert_ne!(first, frame.pixels);
            assert_eq!(frame.pixels.len(), width * height);
        }
    }

    #[test]
    fn reduced_motion_is_static_and_intro_can_be_skipped() {
        let mut frame = Frame::new(640, 480).unwrap();
        let mut state = State::default();
        state.key(Key::Motion);
        state.tick(1);
        assert_eq!(state.phase(), Phase::Password);
        frame.draw(&state);
        let first = frame.pixels.clone();
        state.tick(777);
        frame.draw(&state);
        assert_eq!(first, frame.pixels);
        let mut skip = State::default();
        skip.key(Key::Enter);
        assert_eq!(skip.phase(), Phase::Password);
    }

    #[test]
    fn redline_is_deterministic_and_opens_into_password() {
        let mut frame = Frame::new(1280, 720).unwrap();
        let mut state = State::default();
        let mut previous = Vec::new();
        for _ in 0..11 {
            frame.draw(&state);
            assert_ne!(frame.pixels, previous);
            previous = frame.pixels.clone();
            frame.draw(&state);
            assert_eq!(frame.pixels, previous);
            state.tick(200);
        }
        assert_eq!(state.phase(), Phase::Password);
        state.tick(u32::MAX);
        frame.draw(&state);
        assert_eq!(frame.pixels.len(), 1280 * 720);
    }
}
