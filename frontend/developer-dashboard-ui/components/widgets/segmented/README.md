# Segmented Control Component (`.ui-segmented`)

Equally divided environmental toggle or switcher, commonly utilized to slide between environments (Dev, QA, Prod).

## Structure

- `.ui-segmented`: Main wrapper layout.
- `.ui-segmented-item`: Equal width selection pill. Set active item using `.ui-active`.

## Attributes

- `data-width="auto"`: Shrinks segmented width to fit items content instead of 100% wrapper width.

## Usage Example
```html
<div class="ui-segmented">
  <button class="ui-segmented-item ui-active">Dev</button>
  <button class="ui-segmented-item">QA</button>
  <button class="ui-segmented-item">Prod</button>
</div>
```
