cask "asagiri" do
  arch arm: "arm64", intel: "x86_64"

  version "0.1.5"
  sha256 arm:   "2bb333be4362c9767e5733cabf9cd7bdae104d5457776689bf33aa998a6541b1",
         intel: "e43ff0cb827490c8f76a4296e5cfbb2c3859e9411a8a3b0813e71f687c2a8799"

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
