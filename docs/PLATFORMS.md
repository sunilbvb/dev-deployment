# Supported Platforms & Ecosystems 📱💻

The Dev Deployment Console is architected to build, verify, and deliver across diverse mobile and desktop operating systems without platform locking.

---

## 🎯 Target Mobile Platforms

### 1. Android
- **Binary Formats**: Universal APK (`.apk`), Split APKs, and Google Play App Bundles (`.aab`).
- **Signing & Verification**: Java Keystore (`.jks`, `.keystore`) and PKCS#12 upload certificates.
- **Distribution Channels**:
  - Direct local HTTP streaming with Camera QR codes.
  - Wireless ADB parallel install to multiple Wi-Fi devices.
  - Automated Google Play Console deployment (Internal, Alpha, Beta, Production tracks).
  - ProGuard / R8 mapping file capture (`mapping.txt`).

### 2. iOS & iPadOS
- **Binary Formats**: iOS Application Archive (`.ipa`).
- **Signing & Verification**: Apple PKCS#8 API Key (`.p8`), Distribution Certificates, and Mobile Provisioning Profiles (`.mobileprovision`).
- **Distribution Channels**:
  - Over-the-Air (OTA) wireless installation via native `itms-services://` manifest URLs.
  - TestFlight internal and external beta tracks.
  - Apple App Store submission via Fastlane `deliver`.
  - dSYM crash symbol archive extraction and upload.

---

## 🏗️ Supported Project Layouts & Frameworks

| Project Type | Detection Pattern | Support Level |
|:---|:---|:---|
| **Melos Monorepos** | `melos.yaml` + `packages/` or `apps/` | First-class native support |
| **Dart Pub Workspaces** | `pubspec.yaml` with `workspace: [...]` | First-class native support |
| **Single-App Flutter** | Root `pubspec.yaml` + `lib/main.dart` | First-class native support |
| **Multi-App Workspace** | Multiple `pubspec.yaml` in subfolders | Auto-detected & switchable |
| **Native Android** | `build.gradle` or `settings.gradle` | Supported via custom pipeline templates |
| **Native iOS** | `Podfile` or `*.xcodeproj` | Supported via custom pipeline templates |

---

## 🖥️ Supported Host Operating Systems

- **Linux**: Ubuntu (20.04+), Debian (11+), Fedora, Arch Linux, CentOS / RHEL. Supports systemd user services and native `.desktop` menu entries.
- **macOS**: Apple Silicon (M1, M2, M3, M4) and Intel x86_64 running macOS Monterey, Ventura, Sonoma, or Sequoia. Full support for Xcode compilation.
- **Windows**: Windows 10/11 via WSL2 (Windows Subsystem for Linux) or native Python 3.10+ execution.
