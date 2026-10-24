import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import wave
import zipfile
from pathlib import Path

from PIL import Image


assert "--disposable-vm" in sys.argv
assert subprocess.check_output(["systemd-detect-virt", "--vm"], text=True).strip() == "oracle"
assert os.geteuid() != 0 and os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
results = {}


def clients():
    return json.loads(subprocess.check_output(["hyprctl", "-j", "clients"], text=True, timeout=10))


def close(address):
    subprocess.run(["hyprctl", "dispatch", "hl.dsp.window.close({window=" + json.dumps("address:" + address) + "})"], capture_output=True, timeout=10)


with tempfile.TemporaryDirectory(prefix="forge-everyday-vm-") as directory:
    root = Path(directory)
    text = root / "forge-everyday.txt"
    text.write_text("Forge everyday validation\nText editing, files and archives.\n")
    picture = Image.new("RGB", (800, 480), (252, 238, 10))
    picture.save(root / "forge-everyday.png")
    picture.save(root / "forge-everyday.pdf", "PDF")
    with zipfile.ZipFile(root / "forge-everyday.zip", "w") as archive:
        archive.write(text, text.name)
    with wave.open(str(root / "forge-everyday.wav"), "wb") as audio:
        audio.setnchannels(2)
        audio.setsampwidth(2)
        audio.setframerate(48000)
        audio.writeframes(bytes(48000 * 2 * 2))
    page = root / "forge-everyday.html"
    page.write_text('<!doctype html><title>Forge Everyday Validation</title><style>body{background:#100d16;color:#fcee0a;font:32px sans-serif;padding:60px}</style><h1>Forge Everyday Validation</h1><p>Browser rendering on the installed desktop.</p>')
    profile = root / "browser"
    profile.mkdir()
    (profile / "user.js").write_text('user_pref("browser.shell.checkDefaultBrowser", false);\nuser_pref("browser.aboutwelcome.enabled", false);\nuser_pref("browser.startup.homepage_override.mstone", "ignore");\nuser_pref("datareporting.policy.dataSubmissionEnabled", false);\n')
    applications = [
        ("files", ["thunar", str(root)], ("thunar",), None),
        ("text", ["mousepad", str(text)], ("mousepad", "org.xfce.mousepad"), None),
        ("image", ["ristretto", str(root / "forge-everyday.png")], ("ristretto",), None),
        ("pdf", ["evince", str(root / "forge-everyday.pdf")], ("evince", "org.gnome.evince"), None),
        ("archive", ["xarchiver", str(root / "forge-everyday.zip")], ("xarchiver",), None),
        ("media", ["mpv", "--no-config", "--force-window=yes", "--keep-open=yes", str(root / "forge-everyday.wav")], ("mpv",), None),
        ("browser", ["firefox", "--no-remote", "--profile", str(profile), "--new-window", page.as_uri()], ("firefox",), "Forge Everyday Validation"),
    ]
    for name, command, classes, title in applications:
        baseline = {item["address"] for item in clients()}
        process = None
        with tempfile.TemporaryFile(mode="w+t") as errors:
            try:
                process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=errors, start_new_session=True)
                deadline = time.monotonic() + 45
                matched = None
                while time.monotonic() < deadline:
                    matched = next((item for item in clients() if item["address"] not in baseline and item.get("class", "").lower() in classes and (title is None or title in item.get("title", "")) and all(value > 0 for value in item.get("size", []))), None)
                    if matched:
                        break
                    time.sleep(0.2)
                if not matched:
                    errors.seek(0)
                    raise AssertionError({"app": name, "clients": clients(), "error": errors.read()[-4000:]})
                time.sleep(0.5)
                screenshot = Path.home() / "Pictures/Forge" / ("qualification-" + name + ".png")
                screenshot.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(["grim", str(screenshot)], capture_output=True, check=True, timeout=15)
                assert screenshot.read_bytes().startswith(b"\x89PNG")
                results[name] = {"opened": True, "title": matched.get("title"), "screenshot": str(screenshot)}
            finally:
                for item in clients():
                    if item["address"] not in baseline and item.get("class", "").lower() in classes:
                        close(item["address"])
                if process is not None:
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGTERM)
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid, signal.SIGKILL)
                            process.wait(timeout=5)
    print(json.dumps({"scope": "virtual-machine", "applications": results, "physical_hardware_qualified": False}, indent=2))
