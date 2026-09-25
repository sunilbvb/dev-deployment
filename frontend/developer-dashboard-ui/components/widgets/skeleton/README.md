# Skeleton Loader Component (`.ui-skeleton`)

Animated shimmer blocks representing content structures that are actively loading.

## Structure

- `.ui-skeleton`: Shimmer base class wrapper.
- `.ui-skeleton-avatar`: Round placeholder shape.
- `.ui-skeleton-line`: Rectangular line block.

## Usage Example
```html
<div style="display: flex; gap: 12px;">
  <div class="ui-skeleton ui-skeleton-avatar"></div>
  <div style="flex: 1;">
    <div class="ui-skeleton ui-skeleton-line" style="width: 50%;"></div>
    <div class="ui-skeleton ui-skeleton-line" style="width: 100%;"></div>
  </div>
</div>
```
