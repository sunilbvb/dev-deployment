# Interactive Step Cards Component (`.ui-step-card`)

Sequential step execution card list with step indexes, titles, execution status colors, and outcomes.

## Structure

- `.ui-steps-row`: Flex column container.
- `.ui-step-card`: Card row item. Add status (`data-status="passed|failed|pending"`).
- `.ui-step-number`: Round index pill indicator.
- `.ui-step-content`: Main title and subtext wrapper.
- `.ui-step-title`: Step header label.
- `.ui-step-desc`: Detail status message or description.

## Usage Example
```html
<div class="ui-steps-row">
  <div class="ui-step-card" data-status="passed">
    <div class="ui-step-number">1</div>
    <div class="ui-step-content">
      <div class="ui-step-title">Step 1 Name</div>
      <div class="ui-step-desc">Detail subtext</div>
    </div>
    <span class="ui-badge" data-variant="success">Passed</span>
  </div>
</div>
```
