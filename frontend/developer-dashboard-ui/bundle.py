#!/usr/bin/env python3
"""
CSS Bundler for Developer Dashboard UI Component Library.
Concatenates all widget CSS files into the dist/ directory.
"""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
COMPONENTS_DIR = PROJECT_ROOT / "components"
DIST_DIR = PROJECT_ROOT / "dist"

# Order of files to bundle
CSS_FILES_TO_BUNDLE = [
    COMPONENTS_DIR / "base.css",
    COMPONENTS_DIR / "widgets" / "button" / "button.css",
    COMPONENTS_DIR / "widgets" / "badge" / "badge.css",
    COMPONENTS_DIR / "widgets" / "card" / "card.css",
    COMPONENTS_DIR / "widgets" / "modal" / "modal.css",
    COMPONENTS_DIR / "widgets" / "table" / "table.css",
    COMPONENTS_DIR / "widgets" / "input" / "input.css",
    COMPONENTS_DIR / "widgets" / "sidebar" / "sidebar.css",
    COMPONENTS_DIR / "widgets" / "typography" / "typography.css",
    COMPONENTS_DIR / "widgets" / "alert" / "alert.css",
    COMPONENTS_DIR / "widgets" / "loader" / "loader.css",
    COMPONENTS_DIR / "widgets" / "controls" / "controls.css",
    COMPONENTS_DIR / "widgets" / "progress" / "progress.css",
    COMPONENTS_DIR / "widgets" / "navigation" / "navigation.css",
    COMPONENTS_DIR / "widgets" / "avatar" / "avatar.css",
    COMPONENTS_DIR / "widgets" / "tooltip" / "tooltip.css",
    COMPONENTS_DIR / "widgets" / "skeleton" / "skeleton.css",
    COMPONENTS_DIR / "widgets" / "app-card" / "app-card.css",
    COMPONENTS_DIR / "widgets" / "command-button" / "command-button.css",
    COMPONENTS_DIR / "widgets" / "segmented" / "segmented.css",
    COMPONENTS_DIR / "widgets" / "terminal" / "terminal.css",
    COMPONENTS_DIR / "widgets" / "tree" / "tree.css",
    COMPONENTS_DIR / "widgets" / "step-card" / "step-card.css",
    COMPONENTS_DIR / "widgets" / "dropzone" / "dropzone.css",
    COMPONENTS_DIR / "widgets" / "modal-tabs" / "modal-tabs.css",
    COMPONENTS_DIR / "widgets" / "lightbox" / "lightbox.css",
    COMPONENTS_DIR / "widgets" / "toast" / "toast.css",
    COMPONENTS_DIR / "widgets" / "page-header" / "page-header.css",
    COMPONENTS_DIR / "widgets" / "section-header" / "section-header.css",
    COMPONENTS_DIR / "widgets" / "layout" / "layout.css",
    COMPONENTS_DIR / "widgets" / "tile-card" / "tile-card.css",
]

def bundle():
    print("⚡ Bundling component styles...")
    
    bundled_content = []
    
    for css_path in CSS_FILES_TO_BUNDLE:
        if css_path.exists():
            print(f"  Adding: {css_path.relative_to(PROJECT_ROOT)}")
            with open(css_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                bundled_content.append(content)
        else:
            print(f"  ⚠️ Warning: {css_path.relative_to(PROJECT_ROOT)} does not exist yet.")

    full_css = "\n\n".join(bundled_content) + "\n"
    
    # Ensure dist directory exists
    DIST_DIR.mkdir(exist_ok=True)
    
    # Write to target files
    ui_css_path = DIST_DIR / "ui.css"
    dev_ui_css_path = DIST_DIR / "developer-dashboard-ui.css"
    
    with open(ui_css_path, "w", encoding="utf-8") as f:
        f.write(full_css)
        
    with open(dev_ui_css_path, "w", encoding="utf-8") as f:
        f.write(full_css)
        
    print(f"✅ Success! Bundled CSS written to:")
    print(f"  - {ui_css_path.relative_to(PROJECT_ROOT)}")
    print(f"  - {dev_ui_css_path.relative_to(PROJECT_ROOT)}")

if __name__ == "__main__":
    bundle()
