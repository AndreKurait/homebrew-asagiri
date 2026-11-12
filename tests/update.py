#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "update", Path(__file__).resolve().parents[1] / "scripts/update.py")
update = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update)


def release(tag, draft=False, prerelease=None):
    return {"tag_name": tag, "draft": draft,
            "prerelease": "-dev." in tag if prerelease is None else prerelease}


def metadata():
    version = "0.1.0-dev.37"
    return {"version": version, "downloads": {
        arch: {"url": f"https://github.com/{update.SOURCE}/releases/download/v{version}/Asagiri-{version}-{arch}.dmg",
               "sha256": letter * 64}
        for arch, letter in (("arm64", "a"), ("x86_64", "b"))
    }}


class UpdateTests(unittest.TestCase):
    def test_waits_for_a_public_release(self):
        self.assertIsNone(update.select_release([]))
        self.assertIsNone(update.select_release([release("v0.1.0", draft=True)]))

    def test_stable_takes_precedence_over_a_newer_main_preview(self):
        stable = release("v0.1.0")
        self.assertEqual(update.select_release([release("v0.2.0-dev.99"), stable]), stable)

    def test_release_order_does_not_downgrade_the_cask(self):
        newest = release("v0.1.0-dev.10")
        self.assertEqual(update.select_release([newest, release("v0.1.0-dev.9")]), newest)
        self.assertEqual(update.select_release([release("v0.1.10"), release("v0.1.9")]), release("v0.1.10"))

    def test_invalid_and_mislabeled_versions_are_ignored(self):
        self.assertIsNone(update.select_release([
            release("v01.2.3"), release("v1.0.0-dev.1", prerelease=False),
            release("v1.0.0", prerelease=True), release('v1.0.0";system("bad")'),
        ]))

    def test_cask_uses_exact_per_architecture_checksums_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = update.write_files(metadata(), root)
            self.assertEqual(set(first), {"Casks/asagiri.rb", "release.json"})
            self.assertIn("a" * 64, first["Casks/asagiri.rb"])
            self.assertIn("b" * 64, first["Casks/asagiri.rb"])
            self.assertEqual(update.write_files(metadata(), root), {})

    def test_cask_rejects_redirected_downloads_and_ruby_injection(self):
        for invalid in ("https://example.com/app.dmg", '"; system("bad"); "'):
            value = metadata()
            value["downloads"]["arm64"]["url"] = invalid
            with self.assertRaises(ValueError):
                update.cask(value)
        value = metadata()
        value["downloads"]["arm64"]["sha256"] = "#{system('bad')}"
        with self.assertRaises(ValueError):
            update.cask(value)

    def test_cannot_publish_from_a_local_or_another_repository_run(self):
        with patch.dict(update.os.environ, {}, clear=True), self.assertRaises(ValueError):
            update.publish(metadata(), {})


if __name__ == "__main__":
    unittest.main()
