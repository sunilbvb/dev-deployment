# Sidebar Component (`.ui-sidebar`)

Vertical navigation sidebar container with grouped items and badges.

## Structure

- `.ui-sidebar`: Main vertical sidebar wrapper (240px wide)
- `.ui-sidebar-header`: Top logo/brand section
- `.ui-sidebar-nav`: Scrollable navigation link list
- `.ui-sidebar-group-title`: Uppercase category header
- `.ui-sidebar-item`: Individual navigation tile
- `.ui-sidebar-footer`: Bottom footer bar

## States

| Attribute / Class | Description |
|---|---|
| `.ui-active` / `data-state="active"` | Highlighted active navigation route |

## Usage Example

```html
<aside class="ui-sidebar">
  <div class="ui-sidebar-header">
    <span class="ui-sidebar-brand">App Name</span>
  </div>
  <div class="ui-sidebar-nav">
    <a class="ui-sidebar-item ui-active">Dashboard</a>
  </div>
</aside>
```

## Using `<button>` items

`.ui-sidebar-item` also works on `<button>` elements (e.g. for in-page selection). The kit resets the browser's default button chrome for `button.ui-sidebar-item` — no grey fill or border, full width, left-aligned with an 8px gap — so buttons look like link items:

```html
<button type="button" class="ui-sidebar-item ui-active">
  <span class="app-dot"></span><span>customer</span>
</button>
```

The reset lives in the local fallback `frontend/css/developer-dashboard-ui-kit.css`; when the kit is loaded from the CDN, the consuming app needs the same rule until the CDN build includes it (the deployment console adds it in `features/deployment/frontend/styles.css`).
