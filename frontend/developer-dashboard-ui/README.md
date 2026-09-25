# ⚡ Developer Dashboard UI (`ui-components`)

A standalone, zero-dependency generic UI component library for developer tools, dashboards, and web applications.

---

## 🚀 Quick Start & Showcase Server

Run the local showcase server to view live previews, variants, and copyable HTML snippets for all components:

```bash
cd developer-dashboard-ui
python3 server.py
```

Open your browser to:
👉 **[http://localhost:8088/showcase/](http://localhost:8088/showcase/)**

---

## 📦 How to Integrate into Any Application

### Step 1: Link the Bundled CSS

Add a relative or static link to `dist/ui.css` (or `dist/developer-dashboard-ui.css`) in the `<head>` of your project's HTML file:

```html
<head>
  <meta charset="UTF-8">
  <title>My Application</title>
  <!-- Import UI component library styles -->
  <link rel="stylesheet" href="../developer-dashboard-ui/dist/ui.css">
</head>
```

### Step 2: Use Scoped `.ui-*` Components

Copy HTML snippets directly from the showcase or component READMEs into your project views:

```html
<!-- Example: Button -->
<button class="ui-button" data-variant="primary">
  Save Changes
</button>

<!-- Example: Badge -->
<span class="ui-badge" data-variant="success">
  Active
</span>

<!-- Example: Card -->
<div class="ui-card" data-variant="accent">
  <div class="ui-card-header">
    <h3 class="ui-card-title">Module Status</h3>
  </div>
  <div class="ui-card-body">
    <p>System operating normally.</p>
  </div>
</div>
```

---

## 🎨 Component Gallery Index

| Component | Class Prefix | Variants (`data-variant`) | Directory |
|---|---|---|---|
| **Button** | `.ui-button` | `primary`, `secondary`, `success`, `warning`, `danger`, `outline`, `ghost`, `disabled` | [`components/widgets/button/`](components/widgets/button/) |
| **Badge** | `.ui-badge` | `primary`, `success`, `warning`, `danger`, `secondary`, `neutral` | [`components/widgets/badge/`](components/widgets/badge/) |
| **Card** | `.ui-card` | `standard`, `interactive`, `accent`, `success`, `warning`, `danger`, `flat` | [`components/widgets/card/`](components/widgets/card/) |
| **Modal** | `.ui-modal` | `data-size`: `sm`, `md`, `lg`, `full` | [`components/widgets/modal/`](components/widgets/modal/) |
| **Table** | `.ui-table` | `hover`, `striped`, `compact`, `bordered` | [`components/widgets/table/`](components/widgets/table/) |
| **Input** | `.ui-input`, `.ui-select` | `standard`, `error`, `success`, `disabled` | [`components/widgets/input/`](components/widgets/input/) |
| **Sidebar** | `.ui-sidebar` | `.ui-active` item state | [`components/widgets/sidebar/`](components/widgets/sidebar/) |
| **Typography** | `.ui-title`, `.ui-paragraph`, `.ui-lead`, `.ui-link`, `.ui-code`, `.ui-pre` | `secondary`, `muted`, `success`, `warning`, `danger`; `data-level`: `1` to `6` | [`components/widgets/typography/`](components/widgets/typography/) |
| **Alert** | `.ui-alert` | `info`, `success`, `warning`, `danger` | [`components/widgets/alert/`](components/widgets/alert/) |
| **Loader** | `.ui-loader` | `primary`, `secondary`, `success`, `danger`; `data-size`: `sm`, `md`, `lg` | [`components/widgets/loader/`](components/widgets/loader/) |
| **Controls** | `.ui-checkbox`, `.ui-radio`, `.ui-toggle` | Native checks, radio indicators, custom toggles | [`components/widgets/controls/`](components/widgets/controls/) |
| **Progress** | `.ui-progress` | `success`, `warning`, `danger` (bar variants) | [`components/widgets/progress/`](components/widgets/progress/) |
| **Navigation** | `.ui-tabs`, `.ui-breadcrumbs` | Pill tabs, links, active highlights | [`components/widgets/navigation/`](components/widgets/navigation/) |
| **Avatar** | `.ui-avatar`, `.ui-avatar-group` | `blue`, `purple`, `orange`, `green`, `red` (colors); `data-size`: `sm`, `md`, `lg` | [`components/widgets/avatar/`](components/widgets/avatar/) |
| **Tooltip** | `.ui-tooltip-trigger` | CSS hover text bubbles via `data-tooltip` attribute | [`components/widgets/tooltip/`](components/widgets/tooltip/) |
| **Skeleton** | `.ui-skeleton` | Pulsing loading placeholders (`avatar`, `line`) | [`components/widgets/skeleton/`](components/widgets/skeleton/) |
| **App Card** | `.ui-app-card` | App version grid card with online/offline/warning status | [`components/widgets/app-card/`](components/widgets/app-card/) |
| **Command Btn**| `.ui-command-button` | Build build-selection list button with status and lock support | [`components/widgets/command-button/`](components/widgets/command-button/) |
| **Segmented**  | `.ui-segmented` | Environmental switcher pills (Dev, QA, Prod) | [`components/widgets/segmented/`](components/widgets/segmented/) |
| **Terminal**   | `.ui-terminal` | Console layout window with outcome log lines and runtime timers | [`components/widgets/terminal/`](components/widgets/terminal/) |
| **Folder Tree**| `.ui-tree` | Hierarchical module folder sidebar tree | [`components/widgets/tree/`](components/widgets/tree/) |
| **Step Card**  | `.ui-step-card` | Sequential step execution card rows | [`components/widgets/step-card/`](components/widgets/step-card/) |
| **Dropzone**   | `.ui-dropzone` | Drag-and-drop & paste file upload area | [`components/widgets/dropzone/`](components/widgets/dropzone/) |
| **Modal Tabs** | `.ui-modal-tabs` | Sub-navigation headers for modal dialogs | [`components/widgets/modal-tabs/`](components/widgets/modal-tabs/) |
| **Lightbox**   | `.ui-lightbox` | Full-screen screenshot image preview overlay | [`components/widgets/lightbox/`](components/widgets/lightbox/) |
| **Toast**      | `.ui-toast` | Floating status alert notification cards | [`components/widgets/toast/`](components/widgets/toast/) |
| **Page Header**| `.ui-page-header` | Standardized page title, eyebrow, subtitle & top actions | [`components/widgets/page-header/`](components/widgets/page-header/) |
| **Section Header**| `.ui-section-header` | Standardized category dividers & sub-headers | [`components/widgets/section-header/`](components/widgets/section-header/) |
| **Layout Shell**| `.ui-page`, `.ui-grid`, `.ui-panel-group` | View shell containers, responsive grids, and split panes | [`components/widgets/layout/`](components/widgets/layout/) |
| **Tile Card**  | `.ui-tile-card` | Generic project, app, package, and git repository tiles | [`components/widgets/tile-card/`](components/widgets/tile-card/) |

---

## 📁 Directory Structure

```
developer-dashboard-ui/
├── bundle.py                ← CSS auto-bundling script
├── components/
│   ├── base.css             ← Global variables & root styles
│   └── widgets/
│       ├── button/          (button.html, button.css, README.md)
│       ├── badge/           (badge.html, badge.css, README.md)
│       ├── card/            (card.html, card.css, README.md)
│       ├── modal/           (modal.html, modal.css, README.md)
│       ├── table/           (table.html, table.css, README.md)
│       ├── input/           (input.html, input.css, README.md)
│       ├── sidebar/         (sidebar.html, sidebar.css, README.md)
│       ├── typography/      (typography.html, typography.css, README.md)
│       ├── alert/           (alert.html, alert.css, README.md)
│       ├── loader/          (loader.html, loader.css, README.md)
│       ├── controls/        (controls.html, controls.css, README.md)
│       ├── progress/        (progress.html, progress.css, README.md)
│       ├── navigation/      (navigation.html, navigation.css, README.md)
│       ├── avatar/          (avatar.html, avatar.css, README.md)
│       ├── tooltip/         (tooltip.html, tooltip.css, README.md)
│       ├── skeleton/        (skeleton.html, skeleton.css, README.md)
│       ├── app-card/        (app-card.html, app-card.css, README.md)
│       ├── command-button/  (command-button.html, command-button.css, README.md)
│       ├── segmented/       (segmented.html, segmented.css, README.md)
│       ├── terminal/        (terminal.html, terminal.css, README.md)
│       ├── tree/            (tree.html, tree.css, README.md)
│       ├── step-card/       (step-card.html, step-card.css, README.md)
│       ├── dropzone/        (dropzone.html, dropzone.css, README.md)
│       ├── modal-tabs/      (modal-tabs.html, modal-tabs.css, README.md)
│       ├── lightbox/        (lightbox.html, lightbox.css, README.md)
│       ├── toast/           (toast.html, toast.css, README.md)
│       ├── page-header/     (page-header.html, page-header.css, README.md)
│       ├── section-header/  (section-header.html, section-header.css, README.md)
│       ├── layout/          (layout.html, layout.css, README.md)
│       └── tile-card/       (tile-card.html, tile-card.css, README.md)
├── showcase/
│   ├── index.html           ← Live component showcase gallery
│   └── showcase.css         ← Documentation styling
├── dist/
│   ├── ui.css               ← Bundled single CSS file (alias)
│   └── developer-dashboard-ui.css
├── server.py                ← Local showcase server (port 8088)
└── README.md                ← Integration & documentation
```
