#![no_main]
#![no_std]

extern crate alloc;

use alloc::{vec, vec::Vec};
use core::time::Duration;
use forge_startup::state::{Action, Config, Key, State, Target};
use forge_startup::visual::Frame;
use uefi::{
    Error, Guid, Result, Status,
    boot::{self, BootPolicy, EventType, LoadImageSource, TimerTrigger, Tpl},
    cstr16, entry,
    proto::{
        console::{
            gop::{BltOp, BltPixel, BltRegion, GraphicsOutput},
            text::{Key as FirmwareKey, ScanCode},
        },
        device_path::{
            DevicePath,
            build::{DevicePathBuilder, media::FilePath},
        },
        media::{fs::SimpleFileSystem, partition::PartitionInfo},
    },
};

fn trace(state: &State) {
    #[cfg(feature = "firmware-test")]
    if let Ok(handle) = boot::get_handle_for_protocol::<uefi::proto::console::serial::Serial>() {
        if let Ok(mut serial) =
            boot::open_protocol_exclusive::<uefi::proto::console::serial::Serial>(handle)
        {
            let text: &[u8] = match state.phase() {
                forge_startup::state::Phase::Password => b"FORGE:LOCKED\r\n",
                forge_startup::state::Phase::Denied => b"FORGE:DENIED\r\n",
                forge_startup::state::Phase::Selector => b"FORGE:SELECTOR\r\n",
                forge_startup::state::Phase::Missing => b"FORGE:MISSING\r\n",
                _ => b"FORGE:TRANSITION\r\n",
            };
            let _ = serial.write(text);
        }
    }
    #[cfg(not(feature = "firmware-test"))]
    let _ = state;
}

fn mapped(key: FirmwareKey) -> Option<Key> {
    match key {
        FirmwareKey::Printable(character) => match u16::from(character) {
            13 => Some(Key::Enter),
            8 => Some(Key::Backspace),
            9 => Some(Key::Next),
            32..=126 => Some(Key::Char(u16::from(character) as u8)),
            _ => None,
        },
        FirmwareKey::Special(code) => match code {
            ScanCode::ESCAPE => Some(Key::Escape),
            ScanCode::FUNCTION_2 => Some(Key::Motion),
            ScanCode::UP | ScanCode::DOWN | ScanCode::LEFT | ScanCode::RIGHT => Some(Key::Next),
            _ => None,
        },
    }
}

fn interface(state: &mut State, config: &Config) -> Result<Target> {
    let handle = boot::get_handle_for_protocol::<GraphicsOutput>()?;
    let mut output = boot::open_protocol_exclusive::<GraphicsOutput>(handle)?;
    let preferred = output
        .modes()
        .filter(|mode| {
            let (w, h) = mode.info().resolution();
            w <= 1920 && h <= 1200 && w >= 640 && h >= 480
        })
        .max_by_key(|mode| {
            let (w, h) = mode.info().resolution();
            (w == 1920 && h == 1080, w * h)
        });
    if let Some(mode) = preferred {
        if mode.info().resolution() != output.current_mode_info().resolution() {
            output.set_mode(&mode)?;
        }
    }
    let (width, height) = output.current_mode_info().resolution();
    let mut frame = Frame::new(width, height).ok_or(Error::from(Status::UNSUPPORTED))?;
    let mut pixels = vec![BltPixel::new(0, 0, 0); width * height];
    let timer = unsafe { boot::create_event(EventType::TIMER, Tpl::APPLICATION, None, None)? };
    boot::set_timer(&timer, TimerTrigger::Periodic(Duration::from_millis(33)))?;
    let keyboard = uefi::system::with_stdin(|input| input.wait_for_key_event())?;
    let events = [keyboard, timer];
    let mut action = Action::None;
    let mut last_phase = None;
    loop {
        frame.draw(state);
        for (destination, color) in pixels.iter_mut().zip(&frame.pixels) {
            *destination = BltPixel::from(*color);
        }
        output.blt(BltOp::BufferToVideo {
            buffer: &pixels,
            src: BltRegion::Full,
            dest: (0, 0),
            dims: (width, height),
        })?;
        if last_phase != Some(state.phase()) {
            trace(state);
            last_phase = Some(state.phase());
        }
        match action {
            Action::Verify => {
                state.verify(config);
                action = Action::None;
                continue;
            }
            Action::Launch(target) => {
                boot::close_event(events[1].clone())?;
                return Ok(target);
            }
            Action::None => {}
        }
        let event = boot::wait_for_event(&events).map_err(|error| Error::from(error.status()))?;
        if event == 1 {
            action = state.tick(33);
        } else if let Some(key) =
            uefi::system::with_stdin(|input| input.read_key())?.and_then(mapped)
        {
            action = state.key(key);
        }
    }
}

fn launch(config: &Config, target: Target) -> Result {
    let expected = Guid::from_bytes(if target == Target::Forge {
        config.forge
    } else {
        config.windows
    });
    let filename = if target == Target::Forge {
        cstr16!("\\EFI\\systemd\\systemd-bootx64.efi")
    } else {
        cstr16!("\\EFI\\Microsoft\\Boot\\bootmgfw.efi")
    };
    let handles = boot::find_handles::<SimpleFileSystem>()?;
    let mut selected = None;
    for handle in handles {
        if let Ok(info) = boot::open_protocol_exclusive::<PartitionInfo>(handle) {
            if info.is_system()
                && info
                    .gpt_partition_entry()
                    .is_some_and(|partition| partition.unique_partition_guid == expected)
            {
                if selected.is_some() {
                    return Err(Status::SECURITY_VIOLATION.into());
                }
                selected = Some(handle);
            }
        }
    }
    let handle = selected.ok_or(Error::from(Status::NOT_FOUND))?;
    let path = boot::open_protocol_exclusive::<DevicePath>(handle)?;
    let mut bytes = Vec::new();
    let mut builder = DevicePathBuilder::with_vec(&mut bytes);
    for node in path.node_iter() {
        builder = builder
            .push(&node)
            .map_err(|_| Error::from(Status::INVALID_PARAMETER))?;
    }
    let full = builder
        .push(&FilePath {
            path_name: filename,
        })
        .map_err(|_| Error::from(Status::INVALID_PARAMETER))?
        .finalize()
        .map_err(|_| Error::from(Status::INVALID_PARAMETER))?;
    let image = boot::load_image(
        boot::image_handle(),
        LoadImageSource::FromDevicePath {
            device_path: full,
            boot_policy: BootPolicy::ExactMatch,
        },
    )?;
    drop(path);
    boot::set_watchdog_timer(300, 0x10000, None)?;
    let result = boot::start_image(image);
    let _ = boot::set_watchdog_timer(0, 0x10000, None);
    let _ = boot::unload_image(image);
    result
}

fn stopped(message: &str) -> ! {
    uefi::println!(
        "Forge startup stopped: {}. No OS was started. Use your firmware boot menu for recovery.",
        message
    );
    loop {
        boot::stall(Duration::from_millis(500));
    }
}

#[entry]
fn main() -> Status {
    if uefi::helpers::init().is_err() {
        return Status::ABORTED;
    }
    let _ = boot::set_watchdog_timer(0, 0x10000, None);
    let config = Config::parse(include_bytes!(env!("FORGE_BOOT_CONFIG")))
        .unwrap_or_else(|| stopped("invalid provisioning"));
    let mut state = State::default();
    loop {
        let target = interface(&mut state, &config)
            .unwrap_or_else(|_| stopped("graphics or input unavailable"));
        let _ = launch(&config, target);
        state.launch_failed();
    }
}
