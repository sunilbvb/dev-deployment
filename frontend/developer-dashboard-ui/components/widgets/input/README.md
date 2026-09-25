# Input & Form Components (`.ui-input`, `.ui-select`, `.ui-textarea`)

Accessible form control elements with validation states and help text.

## Structure

- `.ui-field`: Wrapper for label, input, and helper text
- `.ui-label`: Form field label
- `.ui-input`: Standard single-line text input
- `.ui-select`: Custom styled dropdown select
- `.ui-textarea`: Multi-line text field
- `.ui-help-text`: Helper or validation message

## Variants (`data-variant`)

| Value | Description |
|---|---|
| `standard` | Regular default border (default) |
| `error` | Red validation highlight border |
| `success` | Green success validation border |
| `disabled` | Disabled state |

## Usage Example

```html
<div class="ui-field">
  <label class="ui-label">Title</label>
  <input type="text" class="ui-input" placeholder="Title..." />
</div>
```

## Input Groups (`.ui-input-group`)

Enables combining a text input field with an action button seamlessly.

```html
<div class="ui-input-group">
  <input type="text" class="ui-input" placeholder="Search..." />
  <button class="ui-button" data-variant="primary">Go</button>
</div>
```

