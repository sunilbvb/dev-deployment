# System Requirements & Environment Prerequisites 📋

Hardware, operating system, and software prerequisites for running the Dev Deployment Console.

---

## 💻 Host System Requirements

| Resource | Minimum | Recommended |
|:---|:---|:---|
| **CPU** | 2 cores (x86_64 or ARM64) | 4+ cores (e.g. Apple Silicon M-series or Intel Core i7+) |
| **RAM** | 512 MB (Console only) | 8 GB+ (to comfortably compile Flutter/Android/iOS builds) |
| **Disk Space** | 50 MB (Console code) | 20 GB+ free disk for SDK caches, Gradle, and CocoaPods |
| **Network** | Local loopback (`127.0.0.1`) | Local Wi-Fi (for wireless ADB and QR phone downloads) |

---

## 🐍 Software Prerequisites

### Mandatory
- **Python**: Version **3.10.0 or higher** (Python 3.10, 3.11, 3.12, 3.13, 3.14+).
  - Verify with:
    ```bash
    python3 --version
    ```
- **Web Browser**: Any modern web browser supporting ES6 and CSS Grid (Chrome, Edge, Firefox, Safari, Brave, Opera).

### Optional (Depending on Build Targets)
- **Flutter SDK**: `≥ 3.0.0` (required for Flutter builds)
- **Android SDK & Build Tools**: API 21 through 35 (required for APK/AAB builds)
- **Xcode & Command Line Tools**: Xcode 14+ (required for iOS IPA compilation on macOS)
- **Android Platform Tools (`adb`)**: Required for Wireless ADB device pairing and parallel push
- **Java Runtime (`keytool`)**: Required for Android release keystore verification
- **Fastlane & Bundler**: Required for automated Google Play Console & TestFlight distribution
