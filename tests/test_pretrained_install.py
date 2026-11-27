"""模型交接必须校验完整性、避免覆盖已有成果，并支持明确切换。"""
from pathlib import Path
import importlib.util
from importlib.metadata import version as package_version
import hashlib
import json
import platform
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pretrained_install", ROOT / "scripts/install_pretrained.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PretrainedInstallTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / ".artifacts/verification"
        parent.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="pretrained-test-", dir=parent)
        self.root = Path(self.temporary.name).resolve()
        self.assertTrue(self.root.is_relative_to(ROOT.resolve()))
        self.addCleanup(self.temporary.cleanup)
        self.package = self.root / "package"
        version = "1"*32
        samples = b'[]'
        contents = {"models/current.json": json.dumps({"version": version}).encode(),
                    "language-evaluation.json": b'{"count":48}', "THIRD_PARTY_NOTICES.md": b'test fixture notice',
                    "licenses/R-GPL-2.txt": b'test fixture license', "licenses/R-GPL-3.txt": b'test fixture license',
                    f"models/{version}/bundle.joblib": b'test fixture model bytes',
                    f"models/{version}/samples.json": samples,
                    f"models/{version}/evaluation.json": json.dumps({"version": version, "samples_sha256": hashlib.sha256(samples).hexdigest()}).encode()}
        for name, value in contents.items():
            target = self.package / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(value)
        runtime = {"python": platform.python_version(), **{name: package_version(name) for name in ("numpy", "scikit-learn", "joblib", "ortools")}}
        manifest = {"schema_version": 1, "model_version": version, "runtime": runtime,
                    "files": {name: {"bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()} for name, value in contents.items()}}
        (self.package / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        self.destination = self.root / "data"

    def test_fresh_restore_is_valid_and_idempotent(self):
        result = module.install(self.package, self.destination)
        version = result["model_version"]
        self.assertTrue((self.destination / f"models/{version}/bundle.joblib").is_file())
        repeat = module.install(self.package, self.destination)
        self.assertEqual(repeat["copied"], [])
        self.assertEqual(len(repeat["skipped"]), len(result["copied"]))

    def test_existing_different_pointer_is_preserved_without_writing_files(self):
        pointer = self.destination / "models/current.json"
        pointer.parent.mkdir(parents=True)
        pointer.write_bytes(b'{"version":"existing-user-version"}')
        before = pointer.read_bytes()
        with self.assertRaises(ValueError):
            module.install(self.package, self.destination)
        self.assertEqual(pointer.read_bytes(), before)
        self.assertEqual(list(self.destination.rglob("bundle.joblib")), [])

    def test_tampered_model_is_rejected_before_install(self):
        package = self.root / "tampered"
        shutil.copytree(self.package, package)
        model = next(package.glob("models/*/bundle.joblib"))
        with model.open("ab") as stream:
            stream.write(b"tampered")
        with self.assertRaises(ValueError):
            module.install(package, self.destination)
        self.assertFalse(self.destination.exists())

    def test_explicit_activation_keeps_backup_of_old_pointer_and_language_report(self):
        pointer = self.destination / "models/current.json"
        pointer.parent.mkdir(parents=True)
        pointer.write_bytes(b'{"version":"existing-user-version"}')
        language = self.destination / "language-evaluation.json"
        language.write_bytes(b'{"count":1}')
        result = module.install(self.package, self.destination, activate=True)
        backup = self.destination / result["backup"]
        self.assertEqual((backup / "models/current.json").read_bytes(), b'{"version":"existing-user-version"}')
        self.assertEqual((backup / "language-evaluation.json").read_bytes(), b'{"count":1}')
        self.assertEqual(json.loads(pointer.read_text(encoding="utf-8"))["version"], result["model_version"])


if __name__ == "__main__":
    unittest.main()
