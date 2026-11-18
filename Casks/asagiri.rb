cask "asagiri" do
  arch arm: "arm64", intel: "x86_64"

  version "0.1.14"
  sha256 arm:   "18d2fc526e3419dbddf7f0b4d2d5f0137516f93a8ce707fb93aec519c1fb3bf9",
         intel: "fac2b103b7b3cf1f1e4d44fbca83ed4909b93d530b9bcacab1fefa04568d5352"

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
