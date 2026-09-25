# Section Header Component (`.ui-section-header`)

Standardized subsection titles and dividers to group card sets and content categories cleanly.

## Structure

- `.ui-section-header`: Sub-header row container.
- `.ui-section-title`: Category title (uppercase tracking by default, or large via `data-size="lg"`).
- `.ui-section-subtitle`: Optional section description.
- `.ui-section-actions`: Right-aligned subsection buttons or link actions.

## Usage Example
```html
<div class="ui-section-header">
  <h3 class="ui-section-title">SELECT TARGET PROJECT</h3>
  <div class="ui-section-actions">
    <button class="ui-button" data-variant="ghost" data-size="sm">Manage Groups</button>
  </div>
</div>
```
