# Loader / Spinner Component (`.ui-loader`)

Lightweight animated spinner to indicate asynchronous loading, operations, database fetches, or processing states.

## Sizes (`data-size`)

| Value | Dimensions | Border Width | Description |
|---|---|---|---|
| `sm` | `16px * 16px` | `2px` | Fit inside buttons, table cells or inline text |
| `md` | `32px * 32px` | `3px` | Standard page level loader (default) |
| `lg` | `48px * 48px` | `4px` | Hero sections, fullscreen blockades or dashboards |

## Variants (`data-variant`)

- `primary`: Accent blue loader (default)
- `secondary`: Neutral grey spinner
- `success`: Green spinner
- `danger`: Red spinner

## Usage Example

```html
<div class="ui-loader" data-size="md" data-variant="primary"></div>
```
