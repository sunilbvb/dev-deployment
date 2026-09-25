# Collapsible Folder Tree Component (`.ui-tree`)

Hierarchical nested navigation tree for module suites, file explorers, and directory structures.

## Structure

- `.ui-tree`: Main wrapper block.
- `.ui-tree-node`: Node parent. Add `.ui-open` class to reveal nested `.ui-tree-children`.
- `.ui-tree-label`: Parent folder label.
- `.ui-tree-item`: Individual file item child. Add `.ui-active` to highlight selected items.
- `.ui-tree-icon`: Icon wrapper slot.
- `.ui-tree-title`: Text label title.

## Usage Example
```html
<div class="ui-tree">
  <div class="ui-tree-node ui-open">
    <div class="ui-tree-label">
      <span class="ui-tree-icon">📂</span>
      <span class="ui-tree-title">Module Suite</span>
    </div>
    <div class="ui-tree-children">
      <div class="ui-tree-item ui-active">
        <span class="ui-tree-icon">📄</span>
        <span class="ui-tree-title">Test Spec 1</span>
      </div>
    </div>
  </div>
</div>
```
