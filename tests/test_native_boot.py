import hashlib
import struct
import unittest
import uuid

from forge.manifest import ForgeError
from forge.native_boot import ROUNDS, partition_id, provisioning


FORGE = "11111111-2222-4333-8444-555555555555"
WINDOWS = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


class NativeBootTests(unittest.TestCase):
    def test_partuuid_is_not_confused_with_filesystem_uuid_or_device(self):
        for value in (None, "", "ABCD-1234", "/dev/nvme0n1p1", "0"*32, "00000000-0000-0000-0000-000000000000", FORGE + "\n"):
            with self.subTest(value=value), self.assertRaises(ForgeError):
                partition_id(value)
        self.assertEqual(partition_id(FORGE).bytes_le, uuid.UUID(FORGE).bytes_le)

    def test_binary_provisioning_matches_rust_and_has_no_plaintext(self):
        password, salt = "a-separate-boot-password", bytes(range(32))
        result = provisioning(password, FORGE, WINDOWS, salt)
        self.assertEqual(len(result), 104)
        self.assertEqual(result[:8], b"FGX1" + struct.pack("<I", ROUNDS))
        self.assertEqual(result[8:24], uuid.UUID(FORGE).bytes_le)
        self.assertEqual(result[40:72], salt)
        self.assertEqual(result[72:], hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ROUNDS, 32))
        self.assertNotIn(password.encode(), result)

    def test_salts_are_random_and_invalid_passwords_are_refused(self):
        self.assertNotEqual(provisioning("a-separate-boot-password", FORGE, WINDOWS), provisioning("a-separate-boot-password", FORGE, WINDOWS))
        for password in ("short", "x" * 129, "a-password-with-\n", "a-password-with-é"):
            with self.subTest(password=password), self.assertRaises(ForgeError):
                provisioning(password, FORGE, WINDOWS)
