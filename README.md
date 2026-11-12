# Asagiri for Homebrew

Install on Apple Silicon or Intel, with macOS 14 or newer:

```sh
brew install --cask andrekurait/asagiri/asagiri
open -a Asagiri
```

The cask is generated automatically after the first public Asagiri release.
It follows the newest stable release when available, otherwise the latest
tested main prerelease.

Update:

```sh
brew upgrade --cask andrekurait/asagiri/asagiri
```

Current builds are not notarized by Apple. If macOS asks for approval, open
System Settings → Privacy & Security → Open Anyway.

The [installation page](https://andrekurait.github.io/asagiri/install/) also
provides direct Mac downloads and a signed DNF repository for Amazon Linux 2023.
The [application source and releases](https://github.com/AndreKurait/asagiri)
live in the main repository.

## Automatic updates

GitHub Actions checks releases on a 15-minute schedule and can also be run
manually. GitHub may delay scheduled jobs. Before changing the cask, the
updater verifies the release manifest, source commit, GitHub build provenance,
and each architecture's DMG checksum. An older build finishing late cannot
downgrade the selected version.

Once a month it records a fresh successful provenance check in `release.json`,
even if the app version is unchanged. This keeps the public tap maintained
and avoids GitHub disabling its schedule after 60 days without repository
activity. The cask and its version stay unchanged during this audit.

Updates use this repository's temporary `GITHUB_TOKEN`; no personal token or
cross-repository write credential is required. GitHub signs the automatic
commit, and the updater checks its signature. Each update is signed off.

Uninstall with `brew uninstall --cask andrekurait/asagiri/asagiri`.
Container data is preserved.
