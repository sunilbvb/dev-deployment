# Badge Component (`.ui-badge`)

Compact visual tag for status, categories, and labels with status dot indicators.

## Variants (`data-variant`)

| Value | Description |
|---|---|
| `primary` | Primary highlights (default) |
| `success` | Passed / Active / Completed status |
| `warning` | In Progress / Pending status |
| `danger` | Failed / Error status |
| `secondary` | Secondary / Neutral tags |
| `neutral` | Subtle / Archived tags |

## Usage Example

```html
<span class="ui-badge" data-variant="success">Passed</span>
<span class="ui-badge" data-variant="danger">Failed</span>
```

## Tags (`.ui-tag`)

Tags represent keywords or metadata categories. They can include a close action.

```html
<span class="ui-tag">
  design
  <button class="ui-tag-close">&times;</button>
</span>
```

