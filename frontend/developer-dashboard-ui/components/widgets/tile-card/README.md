# Unified Tile Card Component (`.ui-tile-card`)

Standardized tile card component for displaying microservices, packages, git repositories, and target apps across dashboard tabs.

## Structure

- `.ui-tile-card`: Main tile wrapper card (`data-variant="interactive"`, `data-state="active"`).
- `.ui-tile-header`: Top flex row containing icon and badge.
- `.ui-tile-icon`: Unified 34x34 icon container slot.
- `.ui-tile-badge`: Status badge wrapper.
- `.ui-tile-body`: Title and subtext wrapper.
- `.ui-tile-title`: Card title text.
- `.ui-tile-meta`: Bottom meta stats row (branch, commit count, size).

## Usage Example
```html
<div class="ui-tile-card" data-variant="interactive">
  <div class="ui-tile-header">
    <div class="ui-tile-icon">📦</div>
    <span class="ui-badge" data-variant="success">STABLE</span>
  </div>
  <div class="ui-tile-body">
    <h4 class="ui-tile-title">pkg_notifications</h4>
    <div class="ui-tile-meta">
      <span>⌥ main</span>
      <span>52 branches</span>
    </div>
  </div>
</div>
```
