"""Collapsible element functionality.

This module provides a mixin and utilities for creating collapsible diagram elements
that can toggle between a compact (collapsed) and full (expanded) view.

The collapsed state:
- Is persisted with save/load
- Integrates with undo/redo
- Maintains connections to other elements
- Shows a collapse/expand icon for user interaction

Group collapse:
- Multiple items can be assigned to a collapse group
- Collapsing one item in the group collapses all items in the group
- Groups are identified by a string group_id
"""

from __future__ import annotations

from gaphas.geometry import Rectangle

from gaphor.core.modeling.properties import attribute
from gaphor.diagram.shapes import Box, CssNode, Text, cairo_state

# Constants for the collapse icon
COLLAPSE_ICON_SIZE = 12
COLLAPSE_ICON_MARGIN = 4

# Minimum interactive dimensions to ensure hit areas remain usable
MIN_INTERACTIVE_WIDTH = 40
MIN_INTERACTIVE_HEIGHT = 20


def draw_collapse_icon(
    collapsed: bool, box: Box, context, bounding_box: Rectangle
) -> Rectangle:
    """Draw an expand/collapse icon (triangle) in the top-right corner.

    The icon is drawn using local item coordinates (relative to bounding_box).
    Returns the bounding rectangle of the icon for hit testing in local coordinates.

    Note: bounding_box should have x=0, y=0 for proper coordinate alignment
    with hit testing functions that use item-local coordinates.
    """
    cr = context.cairo
    style = context.style

    icon_size = COLLAPSE_ICON_SIZE
    margin = COLLAPSE_ICON_MARGIN

    # Position in top-right corner using local coordinates
    # bounding_box.x and bounding_box.y are typically 0 in local space
    x = bounding_box.x + bounding_box.width - icon_size - margin
    y = bounding_box.y + margin

    with cairo_state(cr) as cr:
        stroke_color = style.get("color", (0, 0, 0, 1))
        cr.set_source_rgba(*stroke_color)
        cr.set_line_width(1.5)

        if collapsed:
            # Draw right-pointing triangle (collapsed state - click to expand)
            cr.move_to(x, y)
            cr.line_to(x + icon_size, y + icon_size / 2)
            cr.line_to(x, y + icon_size)
            cr.close_path()
        else:
            # Draw down-pointing triangle (expanded state - click to collapse)
            cr.move_to(x, y)
            cr.line_to(x + icon_size, y)
            cr.line_to(x + icon_size / 2, y + icon_size)
            cr.close_path()

        cr.fill()

    return Rectangle(x, y, icon_size, icon_size)


def is_point_in_collapse_icon(x: float, y: float, bounding_box: Rectangle) -> bool:
    """Check if a point (x, y) is within the collapse icon area.

    Args:
        x, y: Point coordinates in item-local space (0,0 is top-left of item)
        bounding_box: The item's bounding box in local coordinates
                     (typically Rectangle(0, 0, width, height))

    Returns:
        True if the point is within the collapse icon's clickable area.
    """
    icon_size = COLLAPSE_ICON_SIZE
    margin = COLLAPSE_ICON_MARGIN

    # Calculate icon position in local coordinates
    # Add a small hit area expansion for easier clicking
    hit_expansion = 2
    icon_x = bounding_box.width - icon_size - margin - hit_expansion
    icon_y = margin - hit_expansion

    # Expanded hit area for better usability
    hit_width = icon_size + 2 * hit_expansion
    hit_height = icon_size + 2 * hit_expansion

    return (
        icon_x <= x <= icon_x + hit_width and icon_y <= y <= icon_y + hit_height
    )


def can_show_collapse_icon(item) -> bool:
    """Check if an item can currently show a collapse icon.

    For InterfaceItem, only show the icon when not in folded (ball/socket) mode.
    """
    # Check if this is an InterfaceItem in folded mode
    if hasattr(item, "_folded"):
        from gaphor.UML.classes.interface import Folded

        if item._folded != Folded.NONE:
            return False
    return True


class Collapsible:
    """Mixin class for collapsible diagram elements.

    Add this mixin to ElementPresentation subclasses to enable collapse/expand
    functionality. The mixin provides:
    - `collapsed` attribute (persisted)
    - `collapse_group` attribute for group collapse (persisted)
    - Icon drawing support
    - Click detection for the collapse icon

    Usage:
        class MyItem(Collapsible, ElementPresentation):
            def __init__(self, diagram, id=None):
                super().__init__(diagram, id=id)
                self.watch("collapsed", self.update_shapes)

            def update_shapes(self, event=None):
                if self.collapsed:
                    self.shape = self.collapsed_shape()
                else:
                    self.shape = self.expanded_shape()
    """

    collapsed: attribute[int] = attribute("collapsed", int, default=0)
    collapse_group: attribute[str] = attribute("collapse_group", str, default="")

    # Store the last icon bounding box for hit testing
    _collapse_icon_bounds: Rectangle | None = None

    def draw_collapse_icon(self, context, bounding_box: Rectangle) -> None:
        """Draw the collapse icon and store its bounds for hit testing."""
        self._collapse_icon_bounds = draw_collapse_icon(
            bool(self.collapsed), None, context, bounding_box
        )

    def is_collapse_icon_at(self, x: float, y: float) -> bool:
        """Check if the given point is on the collapse icon.

        Coordinates are relative to the item's top-left corner.
        """
        if not can_show_collapse_icon(self):
            return False
        return is_point_in_collapse_icon(x, y, Rectangle(0, 0, self.width, self.height))

    def toggle_collapsed(self) -> None:
        """Toggle the collapsed state."""
        self.collapsed = 0 if self.collapsed else 1

    def get_collapse_group_members(self):
        """Get all items in the same collapse group.

        Returns a list of items that share the same collapse_group id.
        """
        if not self.collapse_group or not hasattr(self, "diagram"):
            return [self]

        members = []
        for item in self.diagram.get_all_items():
            if (
                isinstance(item, Collapsible)
                and item.collapse_group == self.collapse_group
            ):
                members.append(item)
        return members

    def toggle_group_collapsed(self) -> None:
        """Toggle the collapsed state for all items in the collapse group."""
        new_state = 0 if self.collapsed else 1
        for item in self.get_collapse_group_members():
            item.collapsed = new_state


def collapsed_compartment(presentation, name: str = "") -> CssNode:
    """Create a collapsed compartment showing just a summary.

    Args:
        presentation: The presentation item
        name: Optional name to show (defaults to subject name)
    """
    return CssNode(
        "compartment",
        None,
        Box(
            CssNode(
                "name",
                presentation.subject,
                Text(
                    text=lambda: name
                    or (presentation.subject and presentation.subject.name)
                    or ""
                ),
            ),
        ),
    )


def draw_collapsed_border(box: Box, context, bounding_box: Rectangle):
    """Draw a border for collapsed elements with the collapse icon."""
    from gaphor.diagram.shapes import draw_border

    # Draw the standard border
    draw_border(box, context, bounding_box)

    # Draw the collapse icon (right-pointing triangle for collapsed)
    draw_collapse_icon(True, box, context, bounding_box)


def draw_expanded_border(box: Box, context, bounding_box: Rectangle):
    """Draw a border for expanded elements with the collapse icon."""
    from gaphor.diagram.shapes import draw_border

    # Draw the standard border
    draw_border(box, context, bounding_box)

    # Draw the collapse icon (down-pointing triangle for expanded)
    draw_collapse_icon(False, box, context, bounding_box)


def assign_collapse_group(items, group_id: str) -> None:
    """Assign a group of items to a collapse group.

    Args:
        items: List of Collapsible items to group
        group_id: The group identifier string
    """
    for item in items:
        if isinstance(item, Collapsible):
            item.collapse_group = group_id


def remove_from_collapse_group(items) -> None:
    """Remove items from their collapse groups.

    Args:
        items: List of Collapsible items to ungroup
    """
    for item in items:
        if isinstance(item, Collapsible):
            item.collapse_group = ""


def generate_group_id() -> str:
    """Generate a unique group identifier."""
    import uuid

    return f"collapse-group-{uuid.uuid4().hex[:8]}"


def cluster_items(
    items,
    gap: float = 0,
    create_group: bool = True,
    preserve_existing_groups: bool = True,
) -> str | None:
    """Cluster items together by collapsing them and packing tightly.

    This function:
    1. Filters out locked items (respects lock state)
    2. Collapses all collapsible items to minimize their size
    3. Repositions items in a compact grid with no extra space
    4. Optionally creates a collapse group for the clustered items
    5. Ensures minimum interactive dimensions for usability

    Args:
        items: List of diagram items to cluster
        gap: Space between items (default 0 for tight packing)
        create_group: If True, creates a collapse group for clustered items
                     allowing them to be expanded/collapsed together
        preserve_existing_groups: If True, items already in groups keep their
                                 existing group assignments

    Returns:
        The group_id if a new group was created, None otherwise
    """
    import math

    from gaphor.diagram.presentation import ElementPresentation
    from gaphor.plugins.lock.lockable import is_item_locked

    # Filter to unlocked element presentations only
    element_items = [
        item
        for item in items
        if isinstance(item, ElementPresentation) and not is_item_locked(item)
    ]

    if len(element_items) < 2:
        return None

    # Get diagram reference for constraint solving and updates
    diagram = element_items[0].diagram if element_items else None

    # Determine which items need group assignment
    collapsible_items = [
        item for item in element_items if isinstance(item, Collapsible)
    ]

    # Create a cluster group for coordinated expand/collapse
    cluster_group_id = None
    if create_group and len(collapsible_items) >= 2:
        cluster_group_id = generate_group_id()

        for item in collapsible_items:
            # Either assign to new group or preserve existing group
            if preserve_existing_groups and item.collapse_group:
                # Item already in a group - preserve it
                pass
            else:
                # Assign to the new cluster group
                item.collapse_group = cluster_group_id

    # Collapse all collapsible items and set to minimum size
    # Preserve minimum interactive dimensions for proper hit testing
    for item in element_items:
        if isinstance(item, Collapsible):
            item.collapsed = 1

        # Get the item's minimum dimensions
        min_w = getattr(item, "min_width", item.width)
        min_h = getattr(item, "min_height", item.height)

        # Ensure minimum interactive size for usability
        # This prevents hit areas from shrinking below visible text
        target_width = max(min_w, MIN_INTERACTIVE_WIDTH)
        target_height = max(min_h, MIN_INTERACTIVE_HEIGHT)

        item.width = target_width
        item.height = target_height

        # Request update to trigger shape recalculation
        item.request_update()

    # Calculate anchor position and sort by spatial ordering
    min_x = min(item.matrix[4] for item in element_items)
    min_y = min(item.matrix[5] for item in element_items)
    sorted_items = sorted(element_items, key=lambda i: (i.matrix[5], i.matrix[4]))

    # Calculate grid dimensions
    num_cols = max(1, int(math.ceil(math.sqrt(len(sorted_items)))))

    # Position items in tight grid using translation
    target_y, row_height, row_data = min_y, 0, []

    for idx, item in enumerate(sorted_items):
        w, h = item.width, item.height
        row_data.append((item, w, h))
        row_height = max(row_height, h)

        # When row is complete or last item, place all items in row
        if len(row_data) >= num_cols or idx == len(sorted_items) - 1:
            target_x = min_x
            for row_item, rw, rh in row_data:
                # Translate to target position (target - current)
                row_item.matrix.translate(
                    target_x - row_item.matrix[4], target_y - row_item.matrix[5]
                )
                target_x += rw + gap
            target_y += row_height + gap
            row_height, row_data = 0, []

    # Finalize: request updates and solve constraints for clean state
    for item in element_items:
        # Request update to ensure shape and bounds are recalculated
        item.request_update()

    # Solve diagram constraints and request diagram updates for all items
    if diagram:
        diagram.connections.solve()
        # Request update for each item to ensure proper view rendering
        for item in element_items:
            diagram.request_update(item)

    return cluster_group_id


def uncluster_items(items) -> None:
    """Expand clustered items and remove from their cluster group.

    This is the inverse operation of cluster_items, allowing users to
    expand previously clustered items and remove them from the cluster group.

    Args:
        items: List of diagram items to uncluster
    """
    from gaphor.plugins.lock.lockable import is_item_locked

    diagram = None

    for item in items:
        if is_item_locked(item):
            continue

        # Get diagram reference for later update
        if diagram is None and hasattr(item, "diagram"):
            diagram = item.diagram

        if isinstance(item, Collapsible):
            # Expand the item
            item.collapsed = 0
            # Remove from cluster group (but not from manually created groups)
            # Only remove if the group starts with "collapse-group-" (auto-generated)
            if item.collapse_group and item.collapse_group.startswith("collapse-group-"):
                item.collapse_group = ""
            item.request_update()

    # Request diagram-level update for proper view rendering
    if diagram:
        diagram.connections.solve()
        # Request update for each processed item
        for item in items:
            if not is_item_locked(item) and isinstance(item, Collapsible):
                diagram.request_update(item)
