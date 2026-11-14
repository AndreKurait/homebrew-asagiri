#!/usr/bin/env python3
"""Update the Asagiri cask from a verified public GitHub release."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.request

SOURCE = "AndreKurait/asagiri"
TAP = "AndreKurait/homebrew-asagiri"
ROOT = Path(__file__).resolve().parents[1]
VERSION = re.compile(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-dev\.([1-9]\d*))?")


def command(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, capture_output=True, **kwargs).stdout


def select_release(releases):
    eligible = []
    for release in releases:
        match = VERSION.fullmatch(release["tag_name"])
        if release["draft"] or not match or bool(match[4]) != release["prerelease"]:
            continue
        order = (*map(int, match.groups()[:3]), int(match[4] or 0))
        eligible.append((order, release))
    stable = [item for item in eligible if not item[1]["prerelease"]]
    selected = max(stable or eligible, default=None)
    return selected[1] if selected else None


def checked_asset(release, asset):
    name = asset["name"]
    if name in (".", "..") or not re.fullmatch(r"[A-Za-z0-9_.~+-]+", name):
        raise ValueError("Unsafe asset name")
    if not VERSION.fullmatch(release["tag_name"]):
        raise ValueError("Invalid release tag")
    url = f"https://github.com/{SOURCE}/releases/download/{release['tag_name']}/{name}"
    digest = asset.get("digest", "")
    if (asset["browser_download_url"] != url or not isinstance(digest, str)
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest)):
        raise ValueError(f"Invalid release asset metadata: {name}")
    return url, digest[7:]


def download(release, asset, folder):
    url, digest = checked_asset(release, asset)
    # This updater only downloads small metadata and provenance files.
    if not 0 < asset["size"] <= 16 * 1024 * 1024:
        raise ValueError("Unexpected metadata size")
    request = urllib.request.Request(url, headers={"User-Agent": "Asagiri-Homebrew"})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read(asset["size"] + 1)
    if len(data) != asset["size"] or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("Release metadata failed its size or checksum verification")
    path = folder / asset["name"]
    path.write_bytes(data)
    return path


def publication_identity(statement, manifest):
    """Use only a statement already verified by gh against the official workflow."""
    predicate = statement["predicate"]
    definition = predicate["buildDefinition"]
    dependencies = definition["resolvedDependencies"]
    roles = {item.get("annotations", {}).get("role"): item for item in dependencies}
    if len(dependencies) != 2 or set(roles) != {"build workflow", "package source"}:
        raise ValueError("Provenance must identify one workflow and one package source")
    workflow = definition["externalParameters"]["workflow"]
    source = roles["package source"]
    commit = roles["build workflow"]["digest"]["gitCommit"]
    origin = f"https://github.com/{SOURCE}"
    if (not re.fullmatch(r"[a-f0-9]{40}", commit)
            or workflow["path"] != ".github/workflows/release.yml"
            or workflow["repository"] != origin
            or workflow["ref"] not in ("refs/heads/main", "refs/tags/v" + manifest["version"])
            or roles["build workflow"]["uri"] != f"git+{origin}@{workflow['ref']}"
            or source["uri"] != f"git+{origin}@{manifest['commit']}"
            or source["digest"]["gitCommit"] != manifest["commit"]):
        raise ValueError("Provenance workflow or package identity does not match the release")
    invocation = predicate["runDetails"]["metadata"]["invocationId"]
    match = re.fullmatch(re.escape(origin) + r"/actions/runs/([1-9]\d*)/attempts/([1-9]\d*)", invocation)
    if not match:
        raise ValueError("Provenance names an invalid publication run")
    return commit, match[1], match[2]


def verify_publisher(statement, manifest):
    commit, run_id, attempt = publication_identity(statement, manifest)
    publisher = json.loads(command("gh", "api", f"repos/{SOURCE}/actions/runs/{run_id}/attempts/{attempt}"))
    if (publisher["path"] != ".github/workflows/release.yml"
            or publisher["repository"]["full_name"] != SOURCE
            or publisher["head_repository"]["full_name"] != SOURCE
            or publisher["event"] not in ("push", "workflow_dispatch")
            or publisher["head_branch"] not in ("main", "v" + manifest["version"])
            or publisher["head_sha"] != commit or publisher["status"] != "completed"
            or publisher["conclusion"] != "success"):
        raise ValueError("The attested official release publisher has not completed successfully")
    for base, head in ((manifest["commit"], commit), (commit, "main")):
        comparison = json.loads(command("gh", "api", f"repos/{SOURCE}/compare/{base}...{head}"))
        if comparison["merge_base_commit"]["sha"] != base:
            raise ValueError("Package source and publisher must belong to reviewed main history")
    return commit, run_id


def verify_release(release, folder):
    assets = {item["name"]: item for item in release["assets"]}
    if len(assets) != len(release["assets"]):
        raise ValueError("Duplicate release assets")
    manifest = json.loads(download(release, assets["release-manifest.json"], folder).read_text())
    checksum_file = download(release, assets["SHA256SUMS"], folder)
    bundle = download(release, assets["attestation.sigstore.json"], folder)
    commit = json.loads(command("gh", "api", f"repos/{SOURCE}/commits/{release['tag_name']}"))["sha"]
    if (manifest["repository"] != SOURCE or manifest["version"] != release["tag_name"][1:]
            or manifest["commit"] != commit):
        raise ValueError("Source commit, version, repository, and manifest disagree")
    comparison = json.loads(command("gh", "api", f"repos/{SOURCE}/compare/{commit}...main"))
    if comparison["merge_base_commit"]["sha"] != commit:
        raise ValueError("The release source is not part of reviewed main history")
    verification = json.loads(command(
        "gh", "attestation", "verify", str(checksum_file), "--repo", SOURCE,
        "--signer-workflow", SOURCE + "/.github/workflows/release.yml",
        "--deny-self-hosted-runners", "--bundle", str(bundle), "--format", "json",
    ))
    statements = [item["verificationResult"]["statement"] for item in verification]
    statement = next((item for item in statements if
                      item["predicateType"] == "https://slsa.dev/provenance/v1" and
                      item["predicate"]["buildDefinition"]["externalParameters"].get("source")
                      == {"commit": commit, "version": manifest["version"]}), None)
    if statement is None:
        raise ValueError("The release has no verified provenance for its source and version")
    workflow_commit, run_id = verify_publisher(statement, manifest)
    # Recovery can publish previously tested packages from a newer reviewed
    # workflow. The certificate identifies the publisher, while the signed
    # package-source dependency identifies the original release source.
    command(
        "gh", "attestation", "verify", str(checksum_file), "--repo", SOURCE,
        "--signer-workflow", SOURCE + "/.github/workflows/release.yml",
        "--signer-digest", workflow_commit, "--source-digest", workflow_commit,
        "--deny-self-hosted-runners", "--bundle", str(bundle), "--format", "json",
    )
    subjects = {Path(item["name"]).name: item["digest"]["sha256"] for item in statement["subject"]}
    listed = {item["name"]: item for item in manifest["assets"]}
    if len(subjects) != len(statement["subject"]) or len(listed) != len(manifest["assets"]):
        raise ValueError("Duplicate manifest or provenance subjects")
    downloads = {}
    for arch in ("arm64", "x86_64"):
        name = f"Asagiri-{manifest['version']}-{arch}.dmg"
        url, digest = checked_asset(release, assets[name])
        if (listed[name]["sha256"] != digest or listed[name]["size"] != assets[name]["size"]
                or subjects.get(name) != digest):
            raise ValueError(f"DMG digest is not covered by the manifest and provenance: {name}")
        downloads[arch] = {"url": url, "sha256": digest}
    for name in ("release-manifest.json", "SHA256SUMS"):
        if subjects.get(name) != assets[name]["digest"][7:]:
            raise ValueError(f"Unattested release metadata: {name}")
    return {"repository": SOURCE, "version": manifest["version"], "tag": release["tag_name"],
            "commit": commit, "downloads": downloads,
            "publication_commit": workflow_commit, "publication_run": run_id,
            "verified_month": datetime.now(timezone.utc).strftime("%Y-%m")}


def cask(metadata):
    if not VERSION.fullmatch("v" + metadata["version"]):
        raise ValueError("Invalid cask version")
    for arch in ("arm64", "x86_64"):
        value = metadata["downloads"][arch]
        expected = (f"https://github.com/{SOURCE}/releases/download/v{metadata['version']}/"
                    f"Asagiri-{metadata['version']}-{arch}.dmg")
        if value["url"] != expected or not re.fullmatch(r"[0-9a-f]{64}", value["sha256"]):
            raise ValueError("Untrusted cask download")
    return '''cask "asagiri" do
  arch arm: "arm64", intel: "x86_64"

  version "%s"
  sha256 arm:   "%s",
         intel: "%s"

  url "https://github.com/AndreKurait/asagiri/releases/download/v#{version}/Asagiri-#{version}-#{arch}.dmg"
  name "Asagiri"
  desc "Container engine with Docker CLI, Compose, and Buildx"
  homepage "https://andrekurait.github.io/asagiri/"

  depends_on macos: :sonoma

  app "Asagiri.app"

  uninstall quit: "dev.asagiri.app"

  caveats <<~EOS
    Open Asagiri from Applications to complete setup.
    Current builds are not notarized by Apple. If macOS asks for approval,
    use System Settings > Privacy & Security > Open Anyway.
    Uninstalling the app preserves your container data.
  EOS
end
''' % (metadata["version"], metadata["downloads"]["arm64"]["sha256"],
       metadata["downloads"]["x86_64"]["sha256"])


def write_files(metadata, root=ROOT):
    content = {"Casks/asagiri.rb": cask(metadata),
               "release.json": json.dumps(metadata, indent=2) + "\n"}
    changed = {}
    for name, text in content.items():
        path = root / name
        if path.is_file() and path.read_text() == text:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        changed[name] = text
    return changed


def publish(metadata, changed):
    if (os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("GITHUB_REPOSITORY") != TAP
            or os.environ.get("GITHUB_REF") != "refs/heads/main"):
        raise ValueError("Automatic commits are restricted to this tap's main workflow")
    query = """mutation($input: CreateCommitOnBranchInput!) {
      createCommitOnBranch(input: $input) {
        commit { oid url signature { __typename isValid state wasSignedByGitHub } }
      }
    }"""
    payload = {
        "query": query,
        "variables": {"input": {
            "branch": {"repositoryNameWithOwner": TAP, "refName": "main"},
            "expectedHeadOid": command("git", "rev-parse", "HEAD").strip(),
            "message": {
                "headline": (("Verify Asagiri release integrity for " if set(changed) == {"release.json"}
                              else "Update Asagiri to ") + metadata["version"]),
                "body": ("Verified release provenance and per-architecture DMG checksums.\n"
                         f"Source: {metadata['commit']}\n\n"
                         "Signed-off-by: github-actions[bot] "
                         "<41898282+github-actions[bot]@users.noreply.github.com>"),
            },
            "fileChanges": {"additions": [
                {"path": name, "contents": base64.b64encode(text.encode()).decode()}
                for name, text in sorted(changed.items())
            ]},
        }},
    }
    result = json.loads(command("gh", "api", "graphql", "--input", "-", input=json.dumps(payload)))
    commit = result["data"]["createCommitOnBranch"]["commit"]
    if (not commit["signature"] or not commit["signature"]["isValid"]
            or commit["signature"]["__typename"] != "GpgSignature"):
        raise RuntimeError("GitHub did not verify the automatic commit's GPG signature")
    print("Published verified, signed cask update:", commit["url"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    pages = json.loads(command("gh", "api", "--paginate", "--slurp",
                               f"repos/{SOURCE}/releases?per_page=100"))
    release = select_release([release for page in pages for release in page])
    if release is None:
        print("No public release yet; the cask will appear automatically after the first release.")
        return
    with tempfile.TemporaryDirectory(prefix="asagiri-cask-") as folder:
        metadata = verify_release(release, Path(folder))
    changed = write_files(metadata)
    if not changed:
        print("The cask already matches the latest recommended release.")
    elif args.publish:
        publish(metadata, changed)
    else:
        print("Generated verified cask and release metadata for review:", metadata["version"])


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.stderr or str(error)) from error
