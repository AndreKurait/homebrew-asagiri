cask "asagiri" do
  arch arm: "arm64", intel: "x86_64"

  version "0.1.11"
  sha256 arm:   "7d207519d51578c2aea1ff9ec339bd1f5841f3776f3b075eb193d5f7347da54c",
         intel: "539d5b1aa4039c9c6d410ebcdcff64f990b9d4aac02c07f83b5e437b5568b5fe"

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
