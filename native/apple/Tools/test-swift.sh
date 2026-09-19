#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT"
mkdir -p logs/mimir-apple
xcrun swiftc native/apple/Sources/ModelProfile.swift native/apple/Sources/GenerationSettings.swift native/apple/Sources/Conversation.swift native/apple/Tests/StorageTests.swift -o logs/mimir-apple/storage-tests
logs/mimir-apple/storage-tests
xcrun swiftc native/apple/Sources/ModelProfile.swift native/apple/Sources/GenerationSettings.swift native/apple/Sources/Conversation.swift native/apple/Sources/ChatStore.swift native/apple/Tests/StoreTests.swift -o logs/mimir-apple/store-tests
logs/mimir-apple/store-tests
