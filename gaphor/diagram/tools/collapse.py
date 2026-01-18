"""Collapse icon click tool.

This module provides a tool that handles clicking on the collapse/expand icon
of collapsible diagram elements.
"""

from __future__ import annotations

from gaphas.tool.itemtool import default_find_item_and_handle_at_point
from gi.repository import Gtk

from gaphor.diagram.collapsible import (
    Collapsible,
    can_show_collapse_icon,
    is_point_in_collapse_icon,
)
from gaphor.plugins.lock.lockable import is_item_locked
from gaphor.transaction import Transaction


def collapse_click_tool(event_manager) -> Gtk.GestureClick:
    """Create a gesture for handling collapse icon clicks.

    This tool intercepts single clicks on the collapse icon and toggles
    the collapsed state of the item (and its group if it belongs to one).
    """
    gesture = Gtk.GestureClick.new()
    gesture.set_button(1)  # Left mouse button
    gesture.connect("pressed", on_collapse_click, event_manager)
    return gesture


def on_collapse_click(gesture, n_press, x, y, event_manager):
    """Handle a click on the collapse icon."""
    if n_press != 1:
        return

    view = gesture.get_widget()

    # Find the item at the click position
    item, _handle = default_find_item_and_handle_at_point(view, (x, y))

    if item is None or not isinstance(item, Collapsible):
        return

    # Don't allow collapse/expand on locked items
    if is_item_locked(item):
        return

    # Check if this item can show a collapse icon (e.g., not an interface in folded mode)
    if not can_show_collapse_icon(item):
        return

    # Convert view coordinates to item coordinates
    vx, vy = view.get_matrix_v2i(item).transform_point(x, y)

    # Check if click is on the collapse icon
    from gaphas.geometry import Rectangle

    item_bounds = Rectangle(0, 0, item.width, item.height)
    if is_point_in_collapse_icon(vx, vy, item_bounds):
        # Toggle collapsed state within a transaction for undo/redo
        with Transaction(event_manager):
            # If item has a collapse group, toggle the whole group
            if item.collapse_group:
                item.toggle_group_collapsed()
            else:
                item.toggle_collapsed()

        # Stop event propagation
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
