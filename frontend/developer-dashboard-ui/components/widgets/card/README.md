# Card Component (`.ui-card`)

Container widget for grouping related content and actions.

## Structure

- `.ui-card`: Main card container
- `.ui-card-header`: Top header bar
- `.ui-card-title`: Header title typography
- `.ui-card-body`: Primary content container
- `.ui-card-footer`: Action button container

## Variants (`data-variant`)

| Value | Description |
|---|---|
| `standard` | Basic card with standard borders (default) |
| `interactive` | Clickable card with hover elevation |
| `accent` | Top primary accent border |
| `success` | Top success green border |
| `warning` | Top warning amber border |
| `danger` | Top danger red border |
| `flat` | Borderless / subtle background card |

## Usage Example

```html
<div class="ui-card" data-variant="accent">
  <div class="ui-card-header">
    <h3 class="ui-card-title">Project Status</h3>
  </div>
  <div class="ui-card-body">
    <p>All use cases synced successfully.</p>
  </div>
</div>
```

## Metrics layout

Cards can be used to display stats or high-level numbers:

- `.ui-card-value`: The metric value (number)
- `.ui-card-comparison`: Comparison details

```html
<div class="ui-card">
  <div class="ui-card-header">
    <h3 class="ui-card-title">Monthly Revenue</h3>
    <span class="ui-badge" data-variant="success">+12%</span>
  </div>
  <div class="ui-card-body">
    <div class="ui-card-value">$24,800</div>
    <div class="ui-card-comparison">vs $22,150 last month</div>
  </div>
</div>
```

