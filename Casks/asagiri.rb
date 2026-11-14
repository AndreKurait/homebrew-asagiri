cask "asagiri" do
  arch arm: "arm64", intel: "x86_64"

  version "0.1.1-dev.62"
  sha256 arm:   "e43b986aff78c59c81a86960d4a1498ee81fbebe48b934f8db6e27e573db2afa",
         intel: "0e75e1172ae41017d22daebd7de1f3485cb475bfb2c115dd43050decc8d5b2f5"

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
