use pbkdf2::{pbkdf2_hmac, sha2::Sha256};
use subtle::ConstantTimeEq;
use zeroize::Zeroize;

pub const ROUNDS: u32 = 600_000;
pub const CONFIG_SIZE: usize = 104;

pub struct Config {
    pub forge: [u8; 16],
    pub windows: [u8; 16],
    salt: [u8; 32],
    digest: [u8; 32],
}

impl Config {
    pub fn parse(bytes: &[u8]) -> Option<Self> {
        if bytes.len() != CONFIG_SIZE || &bytes[..4] != b"FGX1" {
            return None;
        }
        if u32::from_le_bytes(bytes[4..8].try_into().ok()?) != ROUNDS {
            return None;
        }
        let result = Self {
            forge: bytes[8..24].try_into().ok()?,
            windows: bytes[24..40].try_into().ok()?,
            salt: bytes[40..72].try_into().ok()?,
            digest: bytes[72..104].try_into().ok()?,
        };
        if [
            &result.forge[..],
            &result.windows[..],
            &result.salt[..],
            &result.digest[..],
        ]
        .iter()
        .any(|part| part.iter().all(|byte| *byte == 0))
        {
            return None;
        }
        Some(result)
    }

    pub fn verify(&self, password: &[u8]) -> bool {
        let mut derived = [0; 32];
        pbkdf2_hmac::<Sha256>(password, &self.salt, ROUNDS, &mut derived);
        let matches = bool::from(derived.ct_eq(&self.digest));
        derived.zeroize();
        matches
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Phase {
    Intro,
    Password,
    Verifying,
    Denied,
    Unlocking,
    Selector,
    Launching,
    Missing,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Target {
    Forge,
    Windows,
}

#[derive(Clone, Copy)]
pub enum Key {
    Char(u8),
    Backspace,
    Enter,
    Escape,
    Next,
    Motion,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Action {
    None,
    Verify,
    Launch(Target),
}

pub struct State {
    phase: Phase,
    selected: Target,
    password: [u8; 128],
    length: usize,
    elapsed: u32,
    time: u32,
    failed: u8,
    authenticated: bool,
    motion: bool,
}

impl Default for State {
    fn default() -> Self {
        Self {
            phase: Phase::Intro,
            selected: Target::Forge,
            password: [0; 128],
            length: 0,
            elapsed: 0,
            time: 0,
            failed: 0,
            authenticated: false,
            motion: true,
        }
    }
}

impl State {
    pub fn phase(&self) -> Phase {
        self.phase
    }
    pub fn target(&self) -> Target {
        self.selected
    }
    pub fn password_length(&self) -> usize {
        self.length
    }
    pub fn elapsed(&self) -> u32 {
        self.elapsed
    }
    pub fn time(&self) -> u32 {
        self.time
    }
    pub fn motion(&self) -> bool {
        self.motion
    }

    fn change(&mut self, phase: Phase) {
        self.phase = phase;
        self.elapsed = 0;
    }
    fn clear(&mut self) {
        self.password.zeroize();
        self.length = 0;
    }

    pub fn tick(&mut self, milliseconds: u32) -> Action {
        self.elapsed = self.elapsed.saturating_add(milliseconds);
        self.time = self.time.wrapping_add(milliseconds);
        match self.phase {
            Phase::Intro if self.elapsed >= if self.motion { 2200 } else { 0 } => {
                self.change(Phase::Password)
            }
            Phase::Denied if self.elapsed >= (1000u32 << self.failed.min(5)) => {
                self.change(Phase::Password)
            }
            Phase::Unlocking if self.elapsed >= if self.motion { 650 } else { 0 } => {
                self.change(Phase::Selector)
            }
            Phase::Launching
                if self.authenticated && self.elapsed >= if self.motion { 450 } else { 0 } =>
            {
                return Action::Launch(self.selected);
            }
            _ => {}
        }
        Action::None
    }

    pub fn key(&mut self, key: Key) -> Action {
        if let Key::Motion = key {
            self.motion = !self.motion;
            return Action::None;
        }
        match self.phase {
            Phase::Intro => {
                if let Key::Enter = key {
                    self.change(Phase::Password);
                }
            }
            Phase::Password => match key {
                Key::Char(byte)
                    if (32..=126).contains(&byte) && self.length < self.password.len() =>
                {
                    self.password[self.length] = byte;
                    self.length += 1;
                }
                Key::Backspace if self.length > 0 => {
                    self.length -= 1;
                    self.password[self.length] = 0;
                }
                Key::Escape => self.clear(),
                Key::Enter if self.length > 0 => {
                    self.change(Phase::Verifying);
                    return Action::Verify;
                }
                _ => {}
            },
            Phase::Selector if self.authenticated => match key {
                Key::Next => {
                    self.selected = if self.selected == Target::Forge {
                        Target::Windows
                    } else {
                        Target::Forge
                    }
                }
                Key::Enter => self.change(Phase::Launching),
                Key::Escape => {
                    self.authenticated = false;
                    self.clear();
                    self.change(Phase::Password);
                }
                _ => {}
            },
            Phase::Missing => {
                if let Key::Enter = key {
                    self.change(Phase::Selector);
                }
            }
            _ => {}
        }
        Action::None
    }

    pub fn verify(&mut self, config: &Config) {
        if self.phase != Phase::Verifying {
            return;
        }
        let valid = config.verify(&self.password[..self.length]);
        self.clear();
        self.authenticated = valid;
        if valid {
            self.failed = 0;
            self.change(Phase::Unlocking);
        } else {
            self.failed = self.failed.saturating_add(1);
            self.change(Phase::Denied);
        }
    }

    pub fn launch_failed(&mut self) {
        if self.authenticated && self.phase == Phase::Launching {
            self.change(Phase::Missing);
        }
    }
}

impl Drop for State {
    fn drop(&mut self) {
        self.clear();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn config() -> Config {
        let mut bytes = [1; CONFIG_SIZE];
        bytes[..4].copy_from_slice(b"FGX1");
        bytes[4..8].copy_from_slice(&ROUNDS.to_le_bytes());
        let mut digest = [0; 32];
        pbkdf2_hmac::<Sha256>(b"ephemeral-test-password", &[1; 32], ROUNDS, &mut digest);
        bytes[72..].copy_from_slice(&digest);
        Config::parse(&bytes).unwrap()
    }

    fn password(state: &mut State, text: &[u8]) {
        for byte in text {
            state.key(Key::Char(*byte));
        }
    }

    #[test]
    fn configuration_is_strict_and_never_has_a_default_credential() {
        assert!(Config::parse(&[]).is_none());
        assert!(Config::parse(&[0; CONFIG_SIZE]).is_none());
        let mut bytes = [1; CONFIG_SIZE];
        bytes[..4].copy_from_slice(b"FGX1");
        bytes[4..8].copy_from_slice(&1u32.to_le_bytes());
        assert!(Config::parse(&bytes).is_none());
    }

    #[test]
    fn locked_input_cannot_launch_or_reveal_selection() {
        let mut state = State::default();
        state.key(Key::Enter);
        for _ in 0..10 {
            state.key(Key::Next);
            state.key(Key::Enter);
        }
        assert_eq!(state.phase(), Phase::Password);
        assert_eq!(state.tick(100_000), Action::None);
    }

    #[test]
    fn passwords_are_bounded_filtered_and_cleared() {
        let mut state = State::default();
        state.key(Key::Enter);
        for _ in 0..256 {
            state.key(Key::Char(b'a'));
        }
        assert_eq!(state.password_length(), 128);
        state.key(Key::Backspace);
        assert_eq!(state.password[127], 0);
        state.key(Key::Escape);
        state.key(Key::Char(0));
        state.key(Key::Char(255));
        assert_eq!(state.password_length(), 0);
        assert!(state.password.iter().all(|byte| *byte == 0));
    }

    #[test]
    fn failed_authentication_has_backoff_and_clears_secret() {
        let mut state = State::default();
        state.key(Key::Enter);
        password(&mut state, b"wrong-password");
        assert_eq!(state.key(Key::Enter), Action::Verify);
        state.verify(&config());
        assert_eq!(state.phase(), Phase::Denied);
        assert_eq!(state.password_length(), 0);
        state.key(Key::Next);
        state.key(Key::Enter);
        state.tick(1999);
        assert_eq!(state.phase(), Phase::Denied);
        state.tick(1);
        assert_eq!(state.phase(), Phase::Password);
    }

    #[test]
    fn successful_authentication_allows_both_targets_and_relock() {
        let mut state = State::default();
        state.key(Key::Enter);
        password(&mut state, b"ephemeral-test-password");
        state.key(Key::Enter);
        state.verify(&config());
        assert_eq!(state.phase(), Phase::Unlocking);
        state.tick(650);
        assert_eq!(state.phase(), Phase::Selector);
        assert_eq!(state.password_length(), 0);
        state.key(Key::Next);
        assert_eq!(state.target(), Target::Windows);
        state.key(Key::Enter);
        assert_eq!(state.tick(450), Action::Launch(Target::Windows));
        state.launch_failed();
        state.key(Key::Enter);
        state.key(Key::Escape);
        assert_eq!(state.phase(), Phase::Password);
        assert!(!state.authenticated);
    }
}
