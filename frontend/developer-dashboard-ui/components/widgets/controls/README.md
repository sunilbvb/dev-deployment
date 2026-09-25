# Checkbox, Radio, and Toggle Components (`.ui-control`, `.ui-checkbox`, etc.)

Consistent browser-agnostic form controls for gathering choices, states, and toggling configurations.

## Structure

- `.ui-control`: Flex wrapper label providing alignment, cursor spacing, and gaps.
- `.ui-checkbox`: Styled tick container checkbox.
- `.ui-radio`: Styled circular check indicator.
- `.ui-toggle`: Interactive switcher/toggle button.

## Usage Examples

### Checkbox
```html
<label class="ui-control">
  <input type="checkbox" class="ui-checkbox" checked />
  Enable notifications
</label>
```

### Radio
```html
<label class="ui-control">
  <input type="radio" name="options" class="ui-radio" />
  Option A
</label>
```

### Toggle Switch
```html
<label class="ui-control">
  <input type="checkbox" class="ui-toggle" />
  <span>Dark Mode</span>
</label>
```
