# Floating Toast Notifications Component (`.ui-toast`)

Non-intrusive floating status notification alerts positioned in screen corners.

## Structure

- `.ui-toast-container`: Fixed viewport positioning container (`data-position="bottom-right|top-right|bottom-left|top-left"`).
- `.ui-toast`: Notification card item (`data-variant="success|danger|warning|info"`).
- `.ui-toast-icon`: Status icon slot.
- `.ui-toast-content`: Title and message column.
- `.ui-toast-title`: Bold alert title.
- `.ui-toast-body`: Detailed notification description.
- `.ui-toast-close`: Dismiss button (`&times;`).

## Usage Example
```html
<div class="ui-toast-container" data-position="bottom-right">
  <div class="ui-toast" data-variant="success">
    <span class="ui-toast-icon">✅</span>
    <div class="ui-toast-content">
      <div class="ui-toast-title">Success</div>
      <div class="ui-toast-body">Task completed.</div>
    </div>
    <button class="ui-toast-close">&times;</button>
  </div>
</div>
```
