"""Custom item tool that respects locked items."""

import gaphas.tool.itemtool as itemtool
from gaphas.canvas import ancestors
from gaphas.connector import Handle
from gaphas.handlemove import HandleMove
from gaphas.item import Item
from gaphas.move import Move
from gaphas.types import Pos
from gaphas.view import GtkView
from gi.repository import Gdk, Gtk

from gaphor.diagram.event import DiagramSelectionChanged
from gaphor.plugins.lock.lockable import is_item_locked
from gaphor.diagram.presentation import Framed


class DragState:
    """State tracking for drag operations."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.moving_items = set()
        self.moving_handle = None
        self.start_x = 0
        self.start_y = 0

    @property
    def moving(self):
        yield from self.moving_items
        if self.moving_handle:
            yield self.moving_handle


def item_tool(event_manager) -> Gtk.GestureDrag:
    """Create a custom item tool that respects locked items."""
    gesture = Gtk.GestureDrag.new()
    drag_state = DragState()
    gesture.connect("drag-begin", on_drag_begin, drag_state, event_manager)
    gesture.connect("drag-update", on_drag_update, drag_state)
    gesture.connect("drag-end", on_drag_end, drag_state)
    return gesture


def on_drag_begin(gesture, start_x, start_y, drag_state, event_manager):
    """Handle drag begin - select items but don't move locked ones."""
    view = gesture.get_widget()
    pos = (start_x, start_y)
    selection = view.selection
    modifiers = gesture.get_current_event_state()
    item, handle = find_item_and_handle_at_point(view, pos)

    # Deselect all items unless CTRL or SHIFT is pressed
    # or the item is already selected.
    if not (
        modifiers & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK)
        or item in selection.selected_items
    ):
        selection.unselect_all()

    if not item:
        gesture.set_state(Gtk.EventSequenceState.DENIED)
        return

    if (
        not handle
        and item in selection.selected_items
        and modifiers & Gdk.ModifierType.CONTROL_MASK
    ):
        selection.unselect_item(item)
        gesture.set_state(Gtk.EventSequenceState.DENIED)
        return

    if not handle and item is view.selection.focused_item:
        handle = itemtool.maybe_split_segment(view, item, pos)

    selection.focused_item = item
    gesture.set_state(Gtk.EventSequenceState.CLAIMED)

    drag_state.start_x = start_x
    drag_state.start_y = start_y

    # Check if item is locked - don't allow handle manipulation if locked
    if handle and not is_item_locked(item):
        drag_state.moving_handle = HandleMove(item, handle, view)
    elif handle:
        # Item is locked, no handle movement
        drag_state.moving_handle = None
    else:
        # Filter out locked items from moving items
        drag_state.moving_items = set(moving_items(view))

    for moving in drag_state.moving:
        moving.start_move((start_x, start_y))

    # Emit selection changed event
    event_manager.handle(
        DiagramSelectionChanged(view, selection.focused_item, selection.selected_items)
    )


def moving_items(view):
    """Filter the items that should eventually be moved.

    Returns Move aspects for the items, excluding locked items.
    """
    selected_items = set(view.selection.selected_items)
    for item in selected_items:
        # Skip locked items
        if is_item_locked(item):
            continue
        # Do not move subitems of selected items
        if not set(ancestors(view.model, item)).intersection(selected_items):
            yield Move(item, view)


def on_drag_update(gesture, offset_x, offset_y, drag_state):
    """Handle drag update - move unlocked items."""
    view = gesture.get_widget()
    x = drag_state.start_x + offset_x
    y = drag_state.start_y + offset_y

    for moving in drag_state.moving:
        moving.move((x, y))

    if not (0 <= x <= view.get_width() and 0 <= y <= view.get_height()):
        view.clamp_item(view.selection.focused_item)

    view.model.update()


def on_drag_end(gesture, offset_x, offset_y, drag_state):
    """Handle drag end."""
    view = gesture.get_widget()
    for moving in drag_state.moving:
        moving.stop_move((drag_state.start_x + offset_x, drag_state.start_y + offset_y))
    if drag_state.moving_handle:
        moving = drag_state.moving_handle
        itemtool.maybe_merge_segments(view, moving.item, moving.handle)
    drag_state.reset()

    view.selection.dropzone_item = None
    view.model.update()


def find_item_and_handle_at_point(
    view: GtkView, pos: Pos
) -> tuple[Item, Handle | None] | tuple[None, None]:
    """Find item and handle at point, respecting locked items."""
    item, handle = itemtool.handle_at_point(view, pos)
    found_item = item or next(
        itemtool.item_at_point(view, pos, exclude=set(view.model.select(Framed))), None
    )

    # If the item is locked, don't allow handle manipulation (resizing)
    # but still allow item selection
    if found_item and is_item_locked(found_item) and handle:
        return found_item, None

    return found_item, handle
