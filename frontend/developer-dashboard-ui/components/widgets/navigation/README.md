# Navigation Component (`.ui-tabs`, `.ui-breadcrumbs`)

Hierarchical page navigation and content switching elements.

## Tabs (`.ui-tabs`)

A pill-based container of buttons to toggle dashboard sub-views.

- `.ui-tabs`: Wrapper shell.
- `.ui-tab`: Interactive tab. Add `.ui-active` to highlight selected state.

### Usage Example
```html
<div class="ui-tabs">
  <button class="ui-tab ui-active">Overview</button>
  <button class="ui-tab">History</button>
</div>
```

## Breadcrumbs (`.ui-breadcrumbs`)

Secondary hierarchical trail helping users trace root folders or page locations.

### Usage Example
```html
<nav class="ui-breadcrumbs">
  <a href="#" class="ui-breadcrumb-link">Home</a>
  <span class="ui-breadcrumb-separator">/</span>
  <span class="ui-breadcrumb-current">Settings</span>
</nav>
```
