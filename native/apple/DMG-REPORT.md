# DFM Mimir development preview DMG — 2026-09-19

- Artifact: `logs/mimir-apple/distribution/DFM-Mimir-0.1.0-arm64-preview.dmg`
- Version: 0.1.0 (build 1), Apple Silicon arm64, macOS 14.0 or later.
- Size: 1,127,885,590 bytes (1.13 GB decimal).
- SHA-256: `4f1eaf3ef6d9656b61798ff4c0ae63dd74695fa4dc01b183270ddb1a509e2e04`
- Packaged app: Mac Release build with explicit running Dock icon fix (`d885a2c`).
- Signature: existing ad-hoc development signature; no Developer ID or notarization.
- Contents: DFM Mimir.app with bundled Q4_K_M model and licenses, Applications
  shortcut, Read Me with installation instructions and preview signing status.

Verification passed: original and mounted app `codesign --verify --deep --strict`,
`hdiutil verify`, mounted Applications link and Read Me, and SHA-256 equality of
the mounted model, original model and Model.json identity. The test mount was
cleanly detached. The app was not launched from the mounted image; packaging
copies the already-tested Release app without modifying its signed contents.

Model SHA-256: `3cf8906f4dd1349c965e7dd873e3995419d34bf846a657840a393c32c89849a5`.
Local verification log: `logs/mimir-apple/dmg-package.log`.
Log SHA-256: `92de3cc2e0fbe50504ae05a42e0d80ef70ec477bfc6527a5e08819f5d393bf2a`.

Reproduce with `native/apple/Tools/package-dmg.sh`; see [README](README.md#development-preview-dmg).
The large DMG and checksum sidecar are local build artifacts, not Git objects.
Chats/settings are not packaged; installation and app replacement preserve the
user's Application Support data. Apple credentials remain deferred.
