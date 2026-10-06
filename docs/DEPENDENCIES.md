# Dependencies & Runtime Architecture 📦

Dev Deployment Console is built on an architectural guarantee: **Zero External Python Dependencies** and **Zero Frontend Build Steps**.

---

## 🐍 Backend Runtime: 100% Python Standard Library

The backend has **no `pip install` requirements** and zero third-party packages. Any system with standard Python ≥ 3.10 can run the console immediately.

### Standard Library Modules Used:
| Domain | Standard Library Modules |
|:---|:---|
| **HTTP & Routing** | `http.server`, `urllib.parse`, `urllib.request` |
| **Data & Serialization** | `json`, `pathlib`, `shutil`, `tempfile` |
| **Process & OS Execution** | `subprocess`, `os`, `sys`, `signal` |
| **Concurrency & Jobs** | `threading`, `time`, `queue` |
| **Cryptography & Auth** | `hmac`, `hashlib`, `secrets` |
| **Archive Inspection** | `zipfile` (central directory parser) |
| **Pure QR Generation** | Pure Python math (Galois Field $GF(2^8)$ Reed-Solomon polynomial math) |

---

## 🌐 Frontend: Vanilla JavaScript & Design System

The user interface requires no compilation, transpilation, or packaging (`npm`, `yarn`, `webpack`, `vite`).

- **Runtime**: Native ES6+ JavaScript running directly in modern web browsers.
- **Styling**: Pure CSS3 with CSS variables and the `developer-dashboard-ui` design kit.
- **Icons**: Scalable vector icons powered by Lucide (`lucide.min.js`).
- **Offline Resilience**: Works seamlessly over `http://localhost:18112` or directly loaded via `file://`.

---

## 🛠️ Optional Host Tools (For Mobile Builds)

The console itself runs without external tools. To execute specific mobile builds, the following tools are invoked from your local system `$PATH` when requested:

- **Flutter SDK (`flutter`)**: Used when triggering Flutter commands (`flutter build apk`, `flutter build ipa`).
- **Android Debug Bridge (`adb`)**: Used for device discovery, Wi-Fi pairing, and multi-device parallel installation.
- **Fastlane (`fastlane` or `bundle exec fastlane`)**: Used for automated store uploads to Google Play and Apple App Store.
- **Java Keytool (`keytool`)**: Used by App Doctor and Sentinel to verify keystore validity and certificate fingerprints.
- **Git (`git`)**: Used by Cache Warmer and Workspace inspector to detect clean status and active branch.
