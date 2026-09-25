# App Selector Card Component (`.ui-app-card`)

Grid-tile selector element commonly representing back-end apps, services, microservices, or databases.

## Structure

- `.ui-app-card`: Card wrapper block. Supports state (`data-state`) and status (`data-status`).
- `.ui-app-icon`: Custom icon wrapper.
- `.ui-app-info`: Layout flex column.
- `.ui-app-name`: Bold title name.
- `.ui-app-version`: Small muted version label.
- `.ui-app-status-indicator`: Small color status circle.

## Attributes

- `data-state="active"`: Selects the card and adds primary accent border.
- `data-status="online"`: Green indicator.
- `data-status="offline"`: Red indicator.
- `data-status="warning"`: Amber indicator.

## Usage Example
```html
<div class="ui-app-card" data-state="active" data-status="online">
  <div class="ui-app-icon">🔐</div>
  <div class="ui-app-info">
    <div class="ui-app-name">Auth Service</div>
    <div class="ui-app-version">v1.2.4</div>
  </div>
  <div class="ui-app-status-indicator"></div>
</div>
```
