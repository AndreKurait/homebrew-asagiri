#!/usr/bin/env python3
import importlib.util
import copy
import json
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


def provenance(workflow_commit="b" * 40):
    origin = "https://github.com/" + update.SOURCE
    source = {"version": "0.1.1-dev.62", "commit": "a" * 40}
    value = {"predicate": {
        "buildDefinition": {
            "externalParameters": {"workflow": {"path": ".github/workflows/release.yml",
                                   "repository": origin, "ref": "refs/heads/main"}},
            "resolvedDependencies": [
                {"uri": f"git+{origin}@refs/heads/main", "digest": {"gitCommit": workflow_commit},
                 "annotations": {"role": "build workflow"}},
                {"uri": f"git+{origin}@{source['commit']}", "digest": {"gitCommit": source["commit"]},
                 "annotations": {"role": "package source"}},
            ],
        },
        "runDetails": {"metadata": {"invocationId": origin + "/actions/runs/123/attempts/2"}},
    }}
    return value, source


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

    def test_monthly_verification_updates_the_audit_record_without_changing_the_cask(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = {**metadata(), "verified_month": "2026-11"}
            update.write_files(value, root)
            value["verified_month"] = "2026-12"
            self.assertEqual(set(update.write_files(value, root)), {"release.json"})

    def test_cannot_publish_from_a_local_or_another_repository_run(self):
        with patch.dict(update.os.environ, {}, clear=True), self.assertRaises(ValueError):
            update.publish(metadata(), {})

    def test_publication_uses_the_github_committable_branch_contract(self):
        response = {"data": {"createCommitOnBranch": {"commit": {
            "url": "https://github.com/" + update.TAP + "/commit/" + "a" * 40,
            "signature": {"__typename": "GpgSignature", "isValid": True},
        }}}}
        environment = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": update.TAP, "GITHUB_REF": "refs/heads/main"}
        with patch.dict(update.os.environ, environment, clear=True), patch.object(
                update, "command", side_effect=["a" * 40, json.dumps(response)]) as mocked:
            update.publish(metadata(), {"Casks/asagiri.rb": "fixture"})
            payload = json.loads(mocked.call_args.kwargs["input"])["variables"]["input"]
            self.assertEqual(payload["branch"], {"repositoryNameWithOwner": update.TAP, "branchName": "main"})
            self.assertEqual(payload["expectedHeadOid"], "a" * 40)

    def test_normal_and_recovered_publication_keep_both_source_identities(self):
        for commit in ("a" * 40, "b" * 40):
            value, source = provenance(commit)
            self.assertEqual(update.publication_identity(value, source), (commit, "123", "2"))

    def test_recovery_rejects_changed_source_wrong_workflow_and_duplicate_roles(self):
        original, source = provenance()
        cases = []
        for field, value in (("path", ".github/workflows/unrelated.yml"),
                             ("ref", "refs/heads/prototype"),
                             ("repository", "https://github.com/someone/fork")):
            changed = copy.deepcopy(original)
            changed["predicate"]["buildDefinition"]["externalParameters"]["workflow"][field] = value
            cases.append(changed)
        changed = copy.deepcopy(original)
        changed["predicate"]["buildDefinition"]["resolvedDependencies"][1]["digest"]["gitCommit"] = "c" * 40
        cases.append(changed)
        changed = copy.deepcopy(original)
        changed["predicate"]["buildDefinition"]["resolvedDependencies"].append(
            copy.deepcopy(changed["predicate"]["buildDefinition"]["resolvedDependencies"][0]))
        cases.append(changed)
        changed = copy.deepcopy(original)
        changed["predicate"]["runDetails"]["metadata"]["invocationId"] = "https://example.com/actions/runs/123/attempts/2"
        cases.append(changed)
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError):
                update.publication_identity(value, source)

    def test_recovery_requires_successful_exact_attempt_and_reviewed_ancestry(self):
        value, source = provenance()
        publisher = {"path": ".github/workflows/release.yml",
                     "repository": {"full_name": update.SOURCE}, "head_repository": {"full_name": update.SOURCE},
                     "event": "workflow_dispatch", "head_branch": "main", "head_sha": "b" * 40,
                     "status": "completed", "conclusion": "success"}
        replies = [json.dumps(publisher), json.dumps({"merge_base_commit": {"sha": "a" * 40}}),
                   json.dumps({"merge_base_commit": {"sha": "b" * 40}})]
        with patch.object(update, "command", side_effect=replies) as calls:
            self.assertEqual(update.verify_publisher(value, source), ("b" * 40, "123"))
            self.assertTrue(calls.call_args_list[0].args[-1].endswith("/123/attempts/2"))
        for field, invalid in (("conclusion", "failure"), ("status", "in_progress"),
                               ("head_sha", "c" * 40), ("event", "pull_request")):
            with patch.object(update, "command", return_value=json.dumps({**publisher, field: invalid})):
                with self.assertRaises(ValueError):
                    update.verify_publisher(value, source)
        with patch.object(update, "command", side_effect=[replies[0], json.dumps({"merge_base_commit": {"sha": "c" * 40}})]):
            with self.assertRaises(ValueError):
                update.verify_publisher(value, source)


if __name__ == "__main__":
    unittest.main()
