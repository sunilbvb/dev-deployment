# Table Component (`.ui-table`)

Responsive data table widget with hover rows, striped rows, and compact spacing.

## Variants (`data-variant`)

| Value | Description |
|---|---|
| `hover` | Highlights rows on mouse hover (default) |
| `striped` | Alternating row background shading |
| `compact` | Reduced cell padding for dense data views |
| `bordered` | Full cell grid borders |

## Usage Example

```html
<div class="ui-table-container">
  <table class="ui-table" data-variant="hover">
    <thead>
      <tr>
        <th>ID</th>
        <th>Name</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>101</td>
        <td>Login Flow</td>
        <td><span class="ui-badge" data-variant="success">Passed</span></td>
      </tr>
    </tbody>
  </table>
</div>
```
