# Page Header Component (`.ui-page-header`)

Standardized top page title section establishing visual hierarchy across all dashboard tabs.

## Structure

- `.ui-page-header`: Top header section block.
- `.ui-page-eyebrow`: Optional small uppercase category/workspace label.
- `.ui-page-title-row`: Flex row aligning title block and right actions.
- `.ui-page-title`: Main H1 page title (supports leading emoji/icon).
- `.ui-page-subtitle`: Muted description text below title.
- `.ui-page-actions`: Right-aligned container for page-level buttons.

## Usage Example
```html
<div class="ui-page-header">
  <span class="ui-page-eyebrow">WORKSPACE</span>
  <div class="ui-page-title-row">
    <h1 class="ui-page-title">📁 My Projects</h1>
    <div class="ui-page-actions">
      <button class="ui-button" data-variant="primary" data-size="sm">+ New Project</button>
    </div>
  </div>
  <p class="ui-page-subtitle">Manage apps and packages, and analyze project files.</p>
</div>
```
