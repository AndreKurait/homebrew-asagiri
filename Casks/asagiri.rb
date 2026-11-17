cask "asagiri" do
  arch arm: "arm64", intel: "x86_64"

  version "0.1.7"
  sha256 arm:   "2dd9aa2fbcf0ba189c62b992050c10aacedc7065e6b8317e924afdd0cb057d0e",
         intel: "24dcc4cb8c85ca8bf3660ebfb87726b727062d5a86595a2c60fa242b962d441a"

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
