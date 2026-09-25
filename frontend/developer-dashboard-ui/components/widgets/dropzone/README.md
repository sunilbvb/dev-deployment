# Image Drop Zone Uploader Component (`.ui-dropzone`)

Drag-and-drop file target block supporting hover transitions and drag focus.

## Structure

- `.ui-dropzone`: Dashed border container. Set active drag state (`data-state="active"`).
- `.ui-dropzone-icon`: Big icon symbol slot.
- `.ui-dropzone-title`: Call-to-action title.
- `.ui-dropzone-subtitle`: Format and paste instruction subtext.

## Usage Example
```html
<div class="ui-dropzone">
  <div class="ui-dropzone-icon">📁</div>
  <div class="ui-dropzone-title">Drag & drop files or click to browse</div>
  <div class="ui-dropzone-subtitle">PNG, JPG up to 10MB</div>
</div>
```
