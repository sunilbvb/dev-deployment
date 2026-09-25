# Progress Component (`.ui-progress`)

Visual indicators showing progression of tasks, database operations, usage thresholds, and completion percentages.

## Structure

- `.ui-progress-container`: Wrapper block.
- `.ui-progress-label`: Layout spacing displaying operation titles and percent numbers.
- `.ui-progress`: Inner container background wrapper.
- `.ui-progress-bar`: Filled indicator element. Set width inline (e.g., `style="width: 72%;"`).

## Variants (`data-variant` on `.ui-progress-bar`)

- `success`: Green indicators.
- `warning`: Yellow indicators.
- `danger`: Red indicators.

## Usage Example

```html
<div class="ui-progress-container">
  <div class="ui-progress-label">
    <span>Build Progress</span>
    <span>45%</span>
  </div>
  <div class="ui-progress">
    <div class="ui-progress-bar" style="width: 45%;"></div>
  </div>
</div>
```
