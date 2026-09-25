# Terminal Output Log Viewer Component (`.ui-terminal`)

Mock terminal console screen for displaying scrolling log outputs, command prompts, build processes, and colorized log entries.

## Structure

- `.ui-terminal`: Main black window container.
- `.ui-terminal-header`: Header bar holding actions and titles.
- `.ui-terminal-actions`: Controls block.
- `.ui-terminal-dot`: Small control color buttons (`data-action="close|minimize|maximize"`).
- `.ui-terminal-title`: Centered header title.
- `.ui-terminal-body`: Scrollable log view screen.
- `.ui-terminal-line`: Log text line. Supports outcome categories (`data-log`).

## Outcome Attributes (`data-log` on `.ui-terminal-line`)

- `command`: Appends a blue prompt indicator (`$ `) to start of line.
- `info`: Grey standard line.
- `success`: Green success line.
- `warning`: Amber warning line.
- `error`: Red error line.

## Usage Example
```html
<div class="ui-terminal">
  <div class="ui-terminal-header">
    <div class="ui-terminal-actions">
      <span class="ui-terminal-dot" data-action="close"></span>
      <span class="ui-terminal-dot" data-action="minimize"></span>
      <span class="ui-terminal-dot" data-action="maximize"></span>
    </div>
    <div class="ui-terminal-title">Build output — auth-service</div>
  </div>
  <div class="ui-terminal-body">
    <div class="ui-terminal-line" data-log="command">npm run build</div>
    <div class="ui-terminal-line" data-log="success">Build Succeeded.</div>
  </div>
</div>
```
