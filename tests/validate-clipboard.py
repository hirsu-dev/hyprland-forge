import io
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from forge.clipboard import choose


with tempfile.TemporaryDirectory(prefix="forge-clipboard-test-") as directory:
    database = str(Path(directory) / "history.db")
    cancel = False
    def runner(command, **kwargs):
        if command[0] == "fuzzel":
            selection = kwargs["input"].splitlines()[0] + b"\n"
            return subprocess.CompletedProcess(command, 1 if cancel else 0, selection)
        if command[0] == "cliphist":
            command = ["cliphist", "-db-path", database, *command[1:]]
        return subprocess.run(command, **kwargs)
    image = io.BytesIO()
    Image.new("RGB", (16, 16), (181, 201, 168)).save(image, format="PNG")
    try:
        for content in (b"  Forge clipboard\nsecond line\n\n", image.getvalue()):
            runner(["cliphist", "store"], input=content, capture_output=True, check=True, timeout=10)
            assert choose(runner)
            actual = subprocess.run(["wl-paste", "--no-newline"], capture_output=True, check=True, timeout=10).stdout
            assert actual == content
        cancel = True
        assert not choose(runner)
        assert subprocess.run(["wl-paste", "--no-newline"], capture_output=True, check=True, timeout=10).stdout == image.getvalue()
    finally:
        subprocess.run(["wl-copy", "--clear"], check=False, timeout=10)
print("Native text and PNG clipboard round trips and cancellation verified")
