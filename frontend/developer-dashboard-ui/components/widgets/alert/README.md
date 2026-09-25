# Alert Component (`.ui-alert`)

Feedback and status banners for reporting operations, errors, warning highlights, or system messages.

## Variants (`data-variant`)

| Value | Description |
|---|---|
| `info` | Information status banner (default) |
| `success` | Successful operation or completed task |
| `warning` | Warning state, deprecation hints or pending actions |
| `danger` | Critical errors, crashes or failure alerts |

## Sub-elements

- `.ui-alert-icon`: Icon placeholder (supports emojis or custom SVGs/fonts).
- `.ui-alert-title`: Bold heading.
- `.ui-alert-body`: Description text.

## Usage Example

```html
<div class="ui-alert" data-variant="danger">
  <span class="ui-alert-icon">🚨</span>
  <div class="ui-alert-content">
    <h4 class="ui-alert-title">Authorization Error</h4>
    <p class="ui-alert-body">Invalid API token supplied. Verify token and retry.</p>
  </div>
</div>
```
