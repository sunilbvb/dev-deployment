# Avatar Component (`.ui-avatar`, `.ui-avatar-group`)

Visual circles containing initials or user icons, commonly grouped for list assignments or contributors.

## Structure

- `.ui-avatar`: Single circular avatar. Supports `data-variant` and `data-size`.
- `.ui-avatar-group`: Overlap layout container.

## Sizes (`data-size` on `.ui-avatar`)

- `sm`: Small contributors list (`28px * 28px`)
- `md`: Default (`36px * 36px`)
- `lg`: Profile pages (`48px * 48px`)

## Variants (`data-variant` on `.ui-avatar`)

- `blue`, `purple`, `orange`, `green`, `red`

## Usage Examples

### Single Avatar
```html
<div class="ui-avatar" data-variant="blue">AB</div>
```

### Avatar Group
```html
<div class="ui-avatar-group">
  <div class="ui-avatar" data-variant="blue">AB</div>
  <div class="ui-avatar" data-variant="purple">CD</div>
  <div class="ui-avatar">+2</div>
</div>
```
