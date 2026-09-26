"""Wire compatibility checks; requires protoc and Python protobuf."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from google.protobuf import descriptor_pb2, descriptor_pool, message_factory


class CustomVersionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        schema = (Path(__file__).resolve().parents[1] / "proto/zmk/custom.proto").read_text()
        cls.types = []
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            for source in (schema, schema.replace("    uint32 version = 4;", "")):
                (path / "custom.proto").write_text(source)
                subprocess.run([
                    "protoc", f"--proto_path={path}",
                    f"--descriptor_set_out={path / 'schema.pb'}", "custom.proto",
                ], check=True)
                descriptors = descriptor_pb2.FileDescriptorSet.FromString(
                    (path / "schema.pb").read_bytes())
                pool = descriptor_pool.DescriptorPool()
                pool.Add(descriptors.file[0])
                descriptor = pool.FindMessageTypeByName("zmk.custom.CustomSubsystemInfo")
                cls.types.append(message_factory.GetMessageClass(descriptor))
        cls.current, cls.legacy = cls.types

    def test_versions_round_trip(self):
        for version in (0, 1, 2**32 - 1):
            with self.subTest(version=version):
                message = self.current(index=7, identifier="example", version=version)
                self.assertEqual(self.current.FromString(message.SerializeToString()).version,
                                 version)

    def test_old_firmware_defaults_to_zero(self):
        wire = self.legacy(index=7, identifier="example", ui_url=["https://example.com"]).SerializeToString()
        current = self.current.FromString(wire)
        self.assertEqual(current.version, 0)
        self.assertEqual(current.identifier, "example")

    def test_old_client_accepts_versioned_firmware(self):
        wire = self.current(index=7, identifier="example", ui_url=["https://example.com"],
                            version=2**32 - 1).SerializeToString()
        legacy = self.legacy.FromString(wire)
        self.assertEqual(legacy.index, 7)
        self.assertEqual(legacy.identifier, "example")
        self.assertEqual(list(legacy.ui_url), ["https://example.com"])

    def test_zero_preserves_legacy_wire_encoding(self):
        self.assertEqual(self.current(index=7, identifier="example", version=0).SerializeToString(),
                         self.legacy(index=7, identifier="example").SerializeToString())


if __name__ == "__main__":
    unittest.main()
