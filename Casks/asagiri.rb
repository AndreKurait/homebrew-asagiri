cask "asagiri" do
  arch arm: "arm64", intel: "x86_64"

  version "0.1.13"
  sha256 arm:   "66cd6ab94e1f2c6f0704b23bbc97cedaa1f1e40c6d76e2a3e2d2b36412315fa1",
         intel: "0b4b5c8282aa39de87c30ef8d8919b4b437f8342c21cb09f846264acc2638792"

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
