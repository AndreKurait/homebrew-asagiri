cask "asagiri" do
  arch arm: "arm64", intel: "x86_64"

  version "0.1.16"
  sha256 arm:   "fa55a7cfb222aea5d4b9990d5c151712874166b53533fb5eb9c488685f5badcc",
         intel: "4f2d31d9ba858628b57816973409022a4a20cdf3a52873f84ba2108b6ada407c"

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
