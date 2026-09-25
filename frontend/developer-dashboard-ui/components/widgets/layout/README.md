# Layout Shell & Grid Component (`.ui-page`, `.ui-grid`, `.ui-panel-group`)

Standardized page containers, responsive grids, and multi-column split panes.

## Structure

- `.ui-page`: Main view wrapper block with standardized padding and background.
- `.ui-page-body`: Content scroll region.
- `.ui-grid`: Card grid wrapper (`data-columns="1|2|3|4|auto"`, `data-gap="sm|md|lg"`).
- `.ui-panel-group`: Split pane container (`data-layout="split-2|sidebar-left|sidebar-right|3-column"`).
- `.ui-panel`: Individual pane block inside split layouts.

## Usage Example
```html
<div class="ui-page">
  <div class="ui-panel-group" data-layout="sidebar-left">
    <div class="ui-panel">Left Pane</div>
    <div class="ui-panel">Right Main Pane</div>
  </div>
</div>
```
