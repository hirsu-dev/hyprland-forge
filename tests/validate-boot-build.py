import struct
import tempfile
from pathlib import Path

from forge.boot import build, password_hash


with tempfile.TemporaryDirectory(prefix="forge-boot-native-") as directory:
    output = build(Path(directory) / "package", "1234-ABCD", "5678-EF01", password_hash("ephemeral-native-test-password"))
    assert (output / "EFI/Forge/forge-x64.efi").read_bytes().startswith(b"MZ")
    data = (output / "grub/terminal.pf2").read_bytes()
    fields, offset = {}, 0
    while offset + 8 <= len(data):
        name, size = data[offset:offset + 4], int.from_bytes(data[offset + 4:offset + 8], "big")
        offset += 8
        fields[name] = data[offset:offset + size]
        if name == b"DATA":
            break
        offset += size
    width = struct.unpack(">H", fields[b"MAXW"])[0]
    height = struct.unpack(">H", fields[b"MAXH"])[0]
    assert width * 80 + 6 <= 730, (width, height)
    assert height * 24 + 6 <= 442, (width, height)
    print("Arch GRUB build and target-font terminal fit verified:", width, height)
