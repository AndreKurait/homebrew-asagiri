cask "asagiri" do
  arch arm: "arm64", intel: "x86_64"

  version "0.1.4"
  sha256 arm:   "ebfe074b10c28cedad3ff098bbb2eb3d04d4a73d32920824574f97df933ebe1f",
         intel: "6d6d667281118ac80fe61dbc6f09cf3a5bb72f3e7ab3f746ed21b2ce1198a413"

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
