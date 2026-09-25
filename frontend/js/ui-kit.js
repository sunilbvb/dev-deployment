/**
 * @fileoverview Generic UI Kit components library for Developer Dashboard.
 * Provides helper functions for rendering components like buttons and switches
 * with theme support.
 */

/**
 * Creates a styled button element.
 * @param {string} text - The label text of the button.
 * @param {string} type - Button style type ('primary' | 'secondary').
 * @param {Function} onClick - The click event handler callback.
 * @returns {HTMLButtonElement} The generated button element.
 */
function createButton(text, type = 'primary', onClick) {
    const btn = document.createElement('button');
    btn.className = `ui-btn ui-btn-${type}`;
    btn.textContent = text;
    if (onClick) {
        btn.addEventListener('click', onClick);
    }
    return btn;
}

/**
 * Creates a segmented tab control switch.
 * @param {Array<{label: string, value: string}>} items - List of segments.
 * @param {string} selectedValue - Currently active segment value.
 * @param {Function} onChange - Callback triggered when segment selection changes.
 * @returns {HTMLDivElement} The generated segmented control element.
 */
function createSegmentedControl(items, selectedValue, onChange) {
    const container = document.createElement('div');
    container.className = 'ui-segmented-control';
    
    items.forEach(item => {
        const seg = document.createElement('div');
        seg.className = `ui-segment ${item.value === selectedValue ? 'active' : ''}`;
        seg.textContent = item.label;
        seg.addEventListener('click', () => {
            container.querySelectorAll('.ui-segment').forEach(s => s.classList.remove('active'));
            seg.classList.add('active');
            if (onChange) {
                onChange(item.value);
            }
        });
        container.appendChild(seg);
    });
    
    return container;
}

// Export kit globally
window.UiKit = {
    createButton,
    createSegmentedControl
};
