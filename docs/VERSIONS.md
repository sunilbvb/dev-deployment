# Versions & Compatibility Matrix 🏷️

Dev Deployment Console follows [Semantic Versioning 2.0.0](https://semver.org/) (`MAJOR.MINOR.PATCH`).

---

## 📅 Release History & Milestones

### v2.4.0 (Current Stable — October 2026)
- **Mobile Innovations**: Wireless ADB Wi-Fi pairing and parallel multi-device APK push.
- **Build Time Profiler**: Phase timing breakdown and compile bottleneck heatmap (flags phases taking ≥ 30%).
- **Smart Silent Cache Warmer**: Automatic background dependency pre-fetching (`flutter pub get`) on Git branch switches.
- **GitHub Actions Hybrid Cloud**: Remote workflow dispatching and cloud template installer.
- **Interactive Documentation Hub**: Embedded offline REST API catalog, dynamic section slicing, and live search.

### v2.3.0 (September 2026)
- **Universal Webhooks**: Two-way ChatOps and notifications for Slack, Discord, Microsoft Teams, Google Chat, and WhatsApp.
- **Local APK Server & QR Code**: Pure Python GF(256) Reed-Solomon QR code generator and local HTTP media streaming.
- **iOS OTA IPA Hosting**: Dynamic XML `manifest.plist` generator for Apple Camera QR installation via `itms-services://`.
- **Sentinel Expiry Monitor**: Proactive certificate, keystore, and Firebase project ID expiration auditing.

### v2.2.0 (August 2026)
- **Build Size Inspector & Diff**: In-memory ZIP central directory inspector detecting raw uncompressed assets (`ZIP_STORED` ≥ 500 KB).
- **Pre-flight App Doctor**: 12+ pre-flight diagnostics verifying Flutter SDK, Android SDK, keystores, and profiles.

### v2.1.0 (July 2026)
- **Saved Pipelines**: Sequential chained workflow execution with stop-on-failure safety.
- **Multi-Environment Tabs**: Parameterized Fastlane and Flutter command cards for Dev, QA, and Prod.

### v2.0.0 (June 2026)
- **Monorepo Architecture**: Native detection of Melos monorepos and Dart pub multi-app workspaces.

---

## 🧩 Compatibility Matrix

| Runtime / Tool | Supported Versions | Recommended |
|:---|:---|:---|
| **Python** | 3.10, 3.11, 3.12, 3.13, 3.14+ | Python 3.12+ |
| **Flutter SDK** | 3.0.0 through latest stable | Flutter 3.24+ |
| **Dart SDK** | 2.18+ through 3.5+ | Dart 3.5+ |
| **Android Gradle** | AGP 7.0+, 8.0+, 9.0+ | AGP 8.5+ |
| **Android SDK** | API 21 through API 35 | Target API 34+ |
| **Xcode (iOS/macOS)** | Xcode 14.x, 15.x, 16.x | Xcode 15+ |
| **Fastlane** | 2.200.0+ | Fastlane 2.220+ |
| **Web Browsers** | Chrome 90+, Edge 90+, Firefox 90+, Safari 15+ | Modern Chromium or Safari |
