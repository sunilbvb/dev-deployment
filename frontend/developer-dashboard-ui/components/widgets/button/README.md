# Button Component (`.ui-button`)

Flexible, accessible button component with multiple semantic variants and sizes.

## Variants (`data-variant`)

| Value | Description |
|---|---|
| `primary` | Main call to action (default) |
| `secondary` | Secondary actions |
| `success` | Positive confirmation actions (Save, Approve) |
| `warning` | Actions requiring user caution |
| `danger` | Destructive actions (Delete, Remove) |
| `outline` | Low emphasis bordered buttons |
| `ghost` | Minimal borderless buttons |
| `disabled` | Disabled state |

## Sizes (`data-size`)

| Value | Description |
|---|---|
| `sm` | Compact (small) |
| `md` | Standard height (default) |
| `lg` | Large call to action |

## Usage Example

```html
<button class="ui-button" data-variant="primary" data-size="md">
  Submit Form
</button>
```
