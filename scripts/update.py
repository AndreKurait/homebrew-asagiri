#!/usr/bin/env python3
"""Update the Asagiri cask from a verified public GitHub release."""
import argparse
import base64
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
        "--signer-digest", commit, "--source-digest", commit,
        "--deny-self-hosted-runners", "--bundle", str(bundle), "--format", "json",
    ))
    statements = [item["verificationResult"]["statement"] for item in verification]
    statement = next((item for item in statements if
                      item["predicateType"] == "https://slsa.dev/provenance/v1" and
                      item["predicate"]["buildDefinition"]["externalParameters"].get("source")
                      == {"commit": commit, "version": manifest["version"]}), None)
    if statement is None:
        raise ValueError("The release has no verified provenance for its source and version")
    subjects = {Path(item["name"]).name: item["digest"]["sha256"] for item in statement["subject"]}
    listed = {item["name"]: item for item in manifest["assets"]}
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
            "commit": commit, "downloads": downloads}


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
                "headline": "Update Asagiri to " + metadata["version"],
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
