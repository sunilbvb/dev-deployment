# Command Selector Button Component (`.ui-command-button`)

Interactive build list selector showing run outcomes, locks, run titles, and commit meta.

## Structure

- `.ui-command-button`: Button list container. Supports selection state (`data-state`).
- `.ui-command-info`: Text grouping flexbox.
- `.ui-command-title`: Bold run title (e.g. Build #482).
- `.ui-command-meta`: Sub-details (times, commit author).
- `.ui-command-status`: Badge status grouping.
- `.ui-lock-badge`: Lock status icon indicator (e.g. 🔒).

## Attributes

- `data-state="selected"`: Highlights button using active theme variables.

## Usage Example
```html
<button class="ui-command-button" data-state="selected">
  <div class="ui-command-info">
    <span class="ui-command-title">Build #482</span>
    <span class="ui-command-meta">10m ago by sunil</span>
  </div>
  <div class="ui-command-status">
    <span class="ui-badge" data-variant="success">Passed</span>
    <span class="ui-lock-badge">🔒</span>
  </div>
</button>
```
