"""Decision tree template factory.

Creates a decision tree layout with 7 boxes and 6 connecting lines
arranged in a triangle pattern:

              [Main Event]
             /            \\
      [Decision A]    [Decision B]
       /      \\         /      \\
   [Out A1] [Out A2] [Out B1] [Out B2]
"""

from __future__ import annotations

from gaphor.core.modeling import Diagram, Presentation
from gaphor.diagram.general.simpleitem import Line

# Box dimensions
BOX_W = 120
BOX_H = 50

# Vertical spacing between levels (top of parent to top of child)
LEVEL_GAP = 120

# Horizontal spread: distance from center of parent to center of child
L1_SPREAD = 160  # Root to Level 1 children horizontal offset
L2_SPREAD = 90   # Level 1 to Level 2 children horizontal offset


def decision_tree_factory(diagram: Diagram, parent: Presentation | None = None) -> Presentation:
    """Create a decision tree template with 7 boxes and 6 connecting lines.

    All positions are relative to root box top-left at (0, 0).
    The placement tool will translate the root to the click position.
    Child boxes and lines are positioned at absolute diagram coordinates.

    Returns the root box as the placed item.
    """
    # The placement tool will translate the returned item to the click point.
    # We return a zero-length invisible anchor line so that none of the 7
    # visible text boxes get displaced. All boxes stay at their positions.
    anchor = diagram.create(Line)
    anchor.handles()[-1].pos = (0, 0)  # zero-length line (invisible)

    # Tree center_x aligns with the top box center
    root_cx = BOX_W / 2

    # Level 0: Top box (Main Event)
    _create_comment_box(diagram, 0, 0, "Main Event")

    # Level 1 centers
    l1_y = LEVEL_GAP
    l1_left_cx = root_cx - L1_SPREAD
    l1_right_cx = root_cx + L1_SPREAD

    # Level 2 centers
    l2_y = 2 * LEVEL_GAP
    l2_a_cx = l1_left_cx - L2_SPREAD   # far left
    l2_b_cx = l1_left_cx + L2_SPREAD   # mid left
    l2_c_cx = l1_right_cx - L2_SPREAD  # mid right
    l2_d_cx = l1_right_cx + L2_SPREAD  # far right

    # Level 1: Two decision boxes
    _create_comment_box(diagram, l1_left_cx - BOX_W / 2, l1_y, "Decision A")
    _create_comment_box(diagram, l1_right_cx - BOX_W / 2, l1_y, "Decision B")

    # Level 2: Four outcome boxes
    _create_comment_box(diagram, l2_a_cx - BOX_W / 2, l2_y, "Outcome A1")
    _create_comment_box(diagram, l2_b_cx - BOX_W / 2, l2_y, "Outcome A2")
    _create_comment_box(diagram, l2_c_cx - BOX_W / 2, l2_y, "Outcome B1")
    _create_comment_box(diagram, l2_d_cx - BOX_W / 2, l2_y, "Outcome B2")

    # Connecting lines: from parent bottom-center to child top-center
    # Top -> Level 1
    _create_line(diagram, root_cx, BOX_H, l1_left_cx, l1_y)
    _create_line(diagram, root_cx, BOX_H, l1_right_cx, l1_y)

    # Left L1 -> Level 2
    _create_line(diagram, l1_left_cx, l1_y + BOX_H, l2_a_cx, l2_y)
    _create_line(diagram, l1_left_cx, l1_y + BOX_H, l2_b_cx, l2_y)

    # Right L1 -> Level 2
    _create_line(diagram, l1_right_cx, l1_y + BOX_H, l2_c_cx, l2_y)
    _create_line(diagram, l1_right_cx, l1_y + BOX_H, l2_d_cx, l2_y)

    return anchor


# Set attributes expected by the toolbox DnD system.
# subject_class=None means the decision tree won't be grouped into parent items via DnD.
decision_tree_factory.item_class = None  # type: ignore[attr-defined]
decision_tree_factory.subject_class = None  # type: ignore[attr-defined]


def _create_comment_box(
    diagram: Diagram, x: float, y: float, label: str
) -> CommentItem:
    """Create an editable text box at position (x, y) with default label text."""
    from gaphor.UML.general.comment import CommentItem
    from gaphor.UML.uml import Comment

    subject = diagram.model.create(Comment)
    subject.body = label
    item = diagram.create(CommentItem, subject=subject)
    item.width = BOX_W
    item.height = BOX_H
    item.matrix.translate(x, y)
    return item


def _create_line(
    diagram: Diagram,
    head_x: float,
    head_y: float,
    tail_x: float,
    tail_y: float,
) -> Line:
    """Create a line from (head_x, head_y) to (tail_x, tail_y).

    All coordinates are in diagram space (relative to root top-left origin).
    """
    line = diagram.create(Line)
    # Position line origin at the head point
    line.matrix.translate(head_x, head_y)
    # Set tail handle position relative to line origin (head)
    tail_handle = line.handles()[-1]
    tail_handle.pos = (tail_x - head_x, tail_y - head_y)
    return line
