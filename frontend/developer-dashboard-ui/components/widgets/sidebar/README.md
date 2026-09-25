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
