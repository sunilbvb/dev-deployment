# Modal Component (`.ui-modal`)

Accessible overlay dialog container with customizable sizes and animated backdrop.

## Structure

- `.ui-modal-backdrop`: Overlay background covering viewport
- `.ui-modal`: Modal dialog card
- `.ui-modal-header`: Title bar & close button
- `.ui-modal-body`: Main content area
- `.ui-modal-footer`: Action buttons

## Sizes (`data-size`)

| Value | Description |
|---|---|
| `sm` | Small confirmation dialogs (400px) |
| `md` | Standard form dialogs (540px, default) |
| `lg` | Complex data/step editors (760px) |
| `full` | Fullscreen viewport modal (95vw) |

## Usage Example

```html
<div class="ui-modal-backdrop ui-active">
  <div class="ui-modal" data-size="md">
    <div class="ui-modal-header">
      <h3 class="ui-modal-title">Confirm Action</h3>
      <button class="ui-modal-close">&times;</button>
    </div>
    <div class="ui-modal-body">
      <p>Are you sure you want to proceed?</p>
    </div>
    <div class="ui-modal-footer">
      <button class="ui-button" data-variant="ghost">Cancel</button>
      <button class="ui-button" data-variant="danger">Delete</button>
    </div>
  </div>
</div>
```
