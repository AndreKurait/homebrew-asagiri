cask "asagiri" do
  arch arm: "arm64", intel: "x86_64"

  version "0.1.15"
  sha256 arm:   "0f43aefa2e2cf4a3910bf89ef1b3daa7549f3c198a85643b04c4f36fa5dfda16",
         intel: "bb3b56c38ad78767925a83dc9f35dc6f2a83a3bcf91a3f7e20528ea8c03b1e67"

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
