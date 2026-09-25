# Image Lightbox Overlay Component (`.ui-lightbox`)

Full-screen backdrop overlay for zooming screenshots, trace recordings, or attached media files.

## Structure

- `.ui-lightbox`: Fixed overlay viewport backdrop. Set `.ui-active` class to reveal.
- `.ui-lightbox-close`: Close button button (`&times;`).
- `.ui-lightbox-container`: Centered flexbox structure.
- `.ui-lightbox-image`: Image tag with box-shadows.
- `.ui-lightbox-caption`: Bottom caption description text.

## Usage Example
```html
<div class="ui-lightbox ui-active">
  <button class="ui-lightbox-close">&times;</button>
  <div class="ui-lightbox-container">
    <img src="screenshot.png" class="ui-lightbox-image" />
    <div class="ui-lightbox-caption">Failure Screenshot</div>
  </div>
</div>
```
