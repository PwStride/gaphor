"""Lockable element functionality.

This module provides a mixin and utilities for creating lockable diagram elements
that can be locked to prevent editing, moving, resizing, and other interactions.

The locked state:
- Is persisted with save/load
- Integrates with undo/redo
- Prevents item movement
- Prevents handle manipulation (resizing)
- Prevents text editing
- Prevents collapse/expand actions
- Shows a visual indicator (lock icon and styling changes)
"""

from __future__ import annotations

from gaphas.geometry import Rectangle

from gaphor.core.modeling.properties import attribute

# Constants for the lock icon
LOCK_ICON_SIZE = 12
LOCK_ICON_MARGIN = 4


class _cairo_state:
    """Context manager for saving and restoring cairo state.

    This is a local copy to avoid circular imports with gaphor.diagram.shapes.
    """

    def __init__(self, cr):
        self._cr = cr

    def __enter__(self):
        self._cr.save()
        return self._cr

    def __exit__(self, _type, _value, _traceback):
        self._cr.restore()


def draw_lock_icon(context, bounding_box: Rectangle) -> Rectangle:
    """Draw a lock icon in the top-left corner.

    Returns the bounding rectangle of the icon for hit testing.
    """
    cr = context.cairo
    style = context.style

    icon_size = LOCK_ICON_SIZE
    margin = LOCK_ICON_MARGIN

    # Position in top-left corner
    x = bounding_box.x + margin
    y = bounding_box.y + margin

    with _cairo_state(cr) as cr:
        stroke_color = style.get("color", (0, 0, 0, 1))
        cr.set_source_rgba(*stroke_color)
        cr.set_line_width(1.5)

        # Draw lock body (rectangle)
        body_width = icon_size * 0.7
        body_height = icon_size * 0.5
        body_x = x + (icon_size - body_width) / 2
        body_y = y + icon_size * 0.45

        cr.rectangle(body_x, body_y, body_width, body_height)
        cr.fill()

        # Draw lock shackle (arc)
        shackle_radius = body_width * 0.35
        shackle_center_x = x + icon_size / 2
        shackle_center_y = body_y

        cr.set_line_width(2)
        cr.arc(shackle_center_x, shackle_center_y, shackle_radius, 3.14159, 0)
        cr.stroke()

    return Rectangle(x, y, icon_size, icon_size)


class Lockable:
    """Mixin class for lockable diagram elements.

    Add this mixin to Presentation subclasses to enable lock/unlock
    functionality. The mixin provides:
    - `locked` attribute (persisted)
    - Icon drawing support
    - Check methods for locked state

    Usage:
        class MyItem(Lockable, ElementPresentation):
            def __init__(self, diagram, id=None):
                super().__init__(diagram, id=id)
                self.watch("locked", self.update_shapes)

            def update_shapes(self, event=None):
                # Optionally update appearance based on lock state
                pass
    """

    locked: attribute[int] = attribute("locked", int, default=0)

    # Store the last icon bounding box for hit testing
    _lock_icon_bounds: Rectangle | None = None

    def draw_lock_icon(self, context, bounding_box: Rectangle) -> None:
        """Draw the lock icon and store its bounds for hit testing."""
        if self.locked:
            self._lock_icon_bounds = draw_lock_icon(context, bounding_box)

    def is_locked(self) -> bool:
        """Check if the item is locked."""
        return bool(self.locked)

    def toggle_locked(self) -> None:
        """Toggle the locked state."""
        self.locked = 0 if self.locked else 1

    def lock(self) -> None:
        """Lock the item."""
        self.locked = 1

    def unlock(self) -> None:
        """Unlock the item."""
        self.locked = 0


def is_item_locked(item) -> bool:
    """Check if an item is locked.

    This is a utility function that can be used to check if any item
    (whether it implements Lockable or not) is locked.

    Returns False if the item doesn't have a locked attribute.
    """
    if hasattr(item, "locked"):
        return bool(item.locked)
    return False
