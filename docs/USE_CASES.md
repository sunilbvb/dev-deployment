# Real-World Use Cases & Workflows 💡

The Dev Deployment Console addresses concrete operational bottlenecks across mobile engineering teams.

---

## 👨‍💻 1. Solo Mobile Engineer & Independent Developer
- **The Challenge**: Managing multiple flavors (`dev`, `qa`, `prod`) often requires typing complex, error-prone terminal commands with long parameter flags.
- **The Workflow**:
  - The developer opens the console with `./start.sh`.
  - Clicks **Build Android APK (dev)** or **Build iOS IPA (dev)**.
  - The build compiles in the background while the developer continues coding.
  - On completion, the developer points their physical phone camera at the screen QR code to install the fresh build over Wi-Fi.

---

## 🧪 2. QA & Device Testing Teams
- **The Challenge**: Distributing debug test builds to 5 physical Android phones and 3 iPads usually requires swapping USB cables or waiting for slow cloud artifact distribution services.
- **The Workflow**:
  - QA opens the **Wireless ADB** modal.
  - The console automatically detects all devices on the local Wi-Fi network.
  - The QA tester clicks **Push to All Devices**: The APK installs in parallel across all 5 phones simultaneously in seconds.

---

## 🏢 3. Agency & White-Label Monorepos
- **The Challenge**: An agency maintains a single core Flutter codebase with 8 branded customer applications (Client A, Client B, Client C), each with different package names, icons, and signing keys.
- **The Workflow**:
  - The console auto-detects the Melos monorepo and presents each client app as an independent selectable card.
  - The agency creates a **Saved Pipeline** for each client.
  - Switching between client apps instantly reconfigures the correct Fastlane lane and Google Play service account JSON.

---

## 🤖 4. Headless CI/CD & Two-Way ChatOps
- **The Challenge**: Developers in Slack or Discord want to trigger builds without remoting into the build machine or navigating web consoles.
- **The Workflow**:
  - A developer types `/deploy customer_app prod build_aab` in a private Slack channel.
  - The webhook hits `POST /api/deployment/webhook/incoming/slack`.
  - The backend validates the HMAC signature, queues the build, and reports live progress back to Slack.
  - Upon completion, the interactive Slack card includes build duration and artifact details.

---

## 🛡️ 5. Release Engineering & Audit Gates
- **The Challenge**: Uncompressed assets accidentally double app download sizes, or expired certificates break production releases at the last minute.
- **The Workflow**:
  - The **Certificate Sentinel** monitors keystores and `.p8` keys, warning 30 days before expiration.
  - The **Build Size Inspector** inspects the compiled `.aab` or `.ipa` central directory, halting the pipeline if oversized `ZIP_STORED` raw assets exceed 500 KB or size expands by >15%.
