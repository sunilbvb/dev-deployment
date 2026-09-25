# Typography Component (`.ui-title`, `.ui-paragraph`, etc.)

Standardized text components and hierarchies for developer documentation, titles, code snippets, and layout copies.

## Titles (`.ui-title`)

Use `data-level` to specify the title size/hierarchy:

| Value | Heading Tag | Font Size | Description |
|---|---|---|---|
| `1` | `h1` | `32px` | Page title / Hero |
| `2` | `h2` | `24px` | Section title |
| `3` | `h3` | `20px` | Sub-section title |
| `4` | `h4` | `16px` | Inline card header |
| `5` | `h5` | `14px` | Small header / detail |
| `6` | `h6` | `12px` | uppercase category / label |

## Text Variants (`.ui-text`)

Use `data-variant` to add semantic color emphasis:

| Value | Color | Description |
|---|---|---|
| `secondary` | Gray / slate | Secondary textual details |
| `muted` | Light gray | Subdued hints or captions |
| `success` | Green | Successful action confirmation text |
| `warning` | Amber | Pending or warning descriptions |
| `danger` | Red | Critical error messages |

## Usage Examples

```html
<h2 class="ui-title" data-level="2">Main Dashboard Overview</h2>
<p class="ui-lead">A summary of your API health stats.</p>
<p class="ui-paragraph">To learn more, check out the <code class="ui-code">docs</code> or click <a href="#" class="ui-link">here</a>.</p>
```
