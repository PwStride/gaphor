from __future__ import annotations

import math
import uuid
from collections.abc import Iterable, Iterator
from functools import singledispatch

import pydot
from gaphas.connector import ConnectionSink, Connector
from gaphas.geometry import Point, Rect
from gaphas.item import NW
from gaphas.matrix import Matrix
from gaphas.segment import Segment

import gaphor.UML.interactions
from gaphor.abc import ActionProvider, Service
from gaphor.action import action
from gaphor.core import event_handler
from gaphor.core.modeling import Base, Diagram, Presentation
from gaphor.diagram.connectors import ItemTemporaryDisconnected
from gaphor.diagram.event import DiagramClosed, DiagramOpened
from gaphor.plugins.lock.lockable import is_item_locked
from gaphor.diagram.presentation import (
    AttachedPresentation,
    ElementPresentation,
    HandlePositionEvent,
    LinePresentation,
)
from gaphor.event import ActionEnabled
from gaphor.i18n import gettext
from gaphor.transaction import Transaction
from gaphor.UML.actions.activitynodes import ForkNodeItem
from gaphor.UML.classes.generalization import GeneralizationItem

DOT = "dot"
DPI = 72.0

# Size for clustered collapsed items
COLLAPSED_ICON_BOX_SIZE = 20


def _is_collapsible(item) -> bool:
    """Check if an item supports collapse functionality."""
    return hasattr(item, "collapsed") and hasattr(item, "collapse_group")


def _cluster_items(items, gap: float = 0) -> None:
    """Cluster items by collapsing and packing tightly.

    This function:
    1. Filters out locked items
    2. Collapses items to icon-only state (collapsed=2)
    3. Repositions items in a compact grid
    """
    # Filter to unlocked element presentations
    element_items = [
        item
        for item in items
        if isinstance(item, ElementPresentation) and not is_item_locked(item)
    ]

    if len(element_items) < 2:
        return

    # Generate group ID for coordinated expand/collapse
    group_id = f"collapse-group-{uuid.uuid4().hex[:8]}"

    # Collapse items and assign to group
    for item in element_items:
        if _is_collapsible(item):
            item.collapsed = 2  # Icon-only mode
            if not item.collapse_group:
                item.collapse_group = group_id

        # Set to icon-only size
        item.width = COLLAPSED_ICON_BOX_SIZE
        item.height = COLLAPSED_ICON_BOX_SIZE
        item.request_update()

    # Calculate anchor position and sort spatially
    min_x = min(item.matrix[4] for item in element_items)
    min_y = min(item.matrix[5] for item in element_items)
    sorted_items = sorted(element_items, key=lambda i: (i.matrix[5], i.matrix[4]))

    # Calculate grid dimensions
    num_cols = max(1, int(math.ceil(math.sqrt(len(sorted_items)))))

    # Position items in tight grid
    target_y, row_height, row_data = min_y, 0, []

    for idx, item in enumerate(sorted_items):
        w, h = item.width, item.height
        row_data.append((item, w, h))
        row_height = max(row_height, h)

        if len(row_data) >= num_cols or idx == len(sorted_items) - 1:
            target_x = min_x
            for row_item, rw, rh in row_data:
                row_item.matrix.translate(
                    target_x - row_item.matrix[4], target_y - row_item.matrix[5]
                )
                target_x += rw + gap
            target_y += row_height + gap
            row_height, row_data = 0, []

    # Request updates
    for item in element_items:
        item.request_update()


def _uncluster_items(items) -> None:
    """Uncluster items by expanding and removing from auto groups."""
    for item in items:
        if is_item_locked(item):
            continue

        if _is_collapsible(item):
            item.collapsed = 0  # Expanded

            # Remove from auto-generated groups only
            if item.collapse_group and item.collapse_group.startswith("collapse-group-"):
                item.collapse_group = ""

            item.request_update()


class AutoLayoutService(Service, ActionProvider):
    """Service providing auto layout and collapse functionality for diagrams.

    This service combines:
    - Auto layout using Graphviz DOT engine
    - Cluster/collapse functionality to minimize selected items to icon-only view

    The collapse functionality is tied to auto layout as clustered items
    are displayed as icon-only triangles for minimal visual footprint.
    """

    def __init__(self, event_manager, diagrams, tools_menu=None, dump_gv=False):
        self.event_manager = event_manager
        self.diagrams = diagrams
        if tools_menu:
            tools_menu.add_actions(self)
        self.dump_gv = dump_gv

        event_manager.subscribe(self.on_diagram_opened_or_closed)

    def shutdown(self):
        self.event_manager.unsubscribe(self.on_diagram_opened_or_closed)

    @action(
        name="auto-layout", label=gettext("Auto Layout"), shortcut="<Primary><Shift>L"
    )
    def layout_current_diagram(self):
        if current_diagram := self.diagrams.get_current_diagram():
            self.layout(current_diagram)

    @action(
        name="auto-layout-ortho",
        label=gettext("Auto Layout (orthogonal)"),
        shortcut="<Primary><Shift>K",
    )
    def layout_current_diagram_orthogonal(self):
        if current_diagram := self.diagrams.get_current_diagram():
            self.layout(current_diagram, splines="ortho")

    @action(
        name="cluster-selected",
        label=gettext("Cluster Selected"),
        shortcut="<Primary><Shift>U",
    )
    def cluster_selected(self):
        """Cluster selected items: collapse to icon-only and pack tightly."""
        current_diagram = self.diagrams.get_current_diagram()
        if not current_diagram:
            return

        selected_items = self._get_selected_items()
        collapsible_items = [
            item
            for item in selected_items
            if _is_collapsible(item) and not is_item_locked(item)
        ]

        if len(collapsible_items) < 2:
            return

        with Transaction(self.event_manager):
            _cluster_items(collapsible_items, gap=0)
            current_diagram.update(collapsible_items)

    @action(
        name="uncluster-selected",
        label=gettext("Uncluster Selected"),
    )
    def uncluster_selected(self):
        """Uncluster selected items: expand and remove from cluster group."""
        current_diagram = self.diagrams.get_current_diagram()
        if not current_diagram:
            return

        selected_items = self._get_selected_items()
        collapsible_items = [
            item for item in selected_items if _is_collapsible(item)
        ]

        if not collapsible_items:
            return

        with Transaction(self.event_manager):
            _uncluster_items(collapsible_items)
            current_diagram.update(collapsible_items)

    def _get_selected_items(self):
        """Get currently selected items from the active diagram view."""
        if page := self.diagrams.get_current_page():
            if view := page.view:
                return list(view.selection.selected_items)
        return []

    def layout(self, diagram: Diagram, splines="polyline"):
        auto_layout = AutoLayout(self.event_manager, self.dump_gv)

        with Transaction(self.event_manager):
            auto_layout.layout(diagram, splines)

    @event_handler(DiagramOpened, DiagramClosed)
    def on_diagram_opened_or_closed(self, event: DiagramOpened | DiagramClosed):
        enabled = (
            isinstance(event, DiagramOpened) or self.diagrams.get_current_diagram()
        )

        for action_name in (
            "win.auto-layout",
            "win.auto-layout-ortho",
            "win.cluster-selected",
            "win.uncluster-selected",
        ):
            self.event_manager.handle(ActionEnabled(action_name, enabled))


class AutoLayout:
    def __init__(self, event_manager=None, dump_gv=False) -> None:
        self.event_manager = event_manager
        self.dump_gv = dump_gv

    def layout(self, diagram: Diagram, splines="polyline") -> None:
        diagram.update(diagram.ownedPresentation)
        graph = diagram_as_pydot(diagram, splines=splines)
        rendered_graph = self.render(graph)
        self.apply_layout(diagram, rendered_graph)
        diagram.update(diagram.ownedPresentation)

    def render(self, graph: pydot.Dot):
        if self.dump_gv:
            graph.write("auto_layout.gv")

        rendered_string = graph.create(prog=DOT, format="dot", encoding="utf-8").decode(
            "utf-8"
        )

        rendered_graphs = pydot.graph_from_dot_data(rendered_string)
        return rendered_graphs[0]

    def apply_layout(  # noqa: C901
        self, diagram, rendered_graph, parent_presentation=None, height=None
    ):
        if height is None:
            _, _, _, height = parse_bb(rendered_graph.get_node("graph")[0].get("bb"))

        matrix_c2i = (
            parent_presentation.matrix_i2c.inverse()
            if parent_presentation
            else Matrix()
        )

        # First record original positions for involved lines
        for edge in rendered_graph.get_edges():
            if presentation := presentation_for_object(diagram, edge):
                for handle in (presentation.head, presentation.tail):
                    if cinfo := diagram.connections.get_connection(handle):
                        self.handle(
                            ItemTemporaryDisconnected(
                                presentation, handle, cinfo.connected, cinfo.port
                            )
                        )

                for handle in presentation.handles():
                    self.handle(
                        HandlePositionEvent(presentation, handle, handle.pos.tuple())
                    )

        for subgraph in rendered_graph.get_subgraphs():
            if presentation := presentation_for_object(
                diagram, subgraph.get_node("graph")[0]
            ):
                # Skip locked items
                if is_item_locked(presentation):
                    continue

                if bb := subgraph.get_node("graph")[0].get("bb"):
                    x, y, w, h = parse_bb(bb, height)
                    presentation.handles()[NW].pos = (0.0, 0.0)
                    presentation.width = w
                    presentation.height = h

                    new_pos = matrix_c2i.transform_point(x, y)
                    presentation.matrix.set(
                        x0=new_pos[0],
                        y0=new_pos[1],
                    )
                    self.apply_layout(
                        diagram,
                        subgraph,
                        parent_presentation=presentation,
                        height=height,
                    )

        for node in rendered_graph.get_nodes():
            if not node.get_pos():
                continue

            if presentation := presentation_for_object(diagram, node):
                # Skip locked items
                if is_item_locked(presentation):
                    continue

                center = parse_point(node.get_pos(), height)
                if isinstance(presentation, ElementPresentation):
                    # Normalize handle placement
                    w = presentation.width
                    h = presentation.height
                    presentation.handles()[NW].pos = (0.0, 0.0)
                    presentation.width = w
                    presentation.height = h

                    new_pos = matrix_c2i.transform_point(
                        center[0] - w / 2, center[1] - h / 2
                    )
                else:
                    new_pos = matrix_c2i.transform_point(center[0], center[1])
                presentation.matrix.set(
                    x0=new_pos[0],
                    y0=new_pos[1],
                )
                if isinstance(presentation, AttachedPresentation):
                    reconnect(
                        presentation, presentation.handles()[0], diagram.connections
                    )

        for edge in rendered_graph.get_edges():
            if presentation := presentation_for_object(diagram, edge):
                # Skip locked items
                if is_item_locked(presentation):
                    continue

                presentation.orthogonal = False

                reverse = isinstance(presentation, GeneralizationItem)
                points = parse_edge_pos(edge.get_pos(), height, reverse)
                segment = Segment(presentation, diagram)
                while len(points) > len(presentation.handles()):
                    segment.split_segment(0)
                while len(points) < len(presentation.handles()):
                    segment.merge_segment(0)

                assert len(points) == len(presentation.handles())

                matrix = presentation.matrix_i2c.inverse()
                for handle, point in zip(presentation.handles(), points, strict=False):
                    handle.pos = matrix.transform_point(*point)

                for handle in (presentation.head, presentation.tail):
                    reconnect(presentation, handle, diagram.connections)

    def handle(self, event):
        if self.event_manager:
            self.event_manager.handle(event)


def presentation_for_object(diagram, obj) -> Presentation | None:
    if not obj.get("id"):
        return None

    id = strip_quotes(obj.get("id"))
    return next((p for p in diagram.ownedPresentation if p.id == id), None)


def reconnect(presentation, handle, connections) -> None:
    if not (connected := connections.get_connection(handle)):
        return

    connector = Connector(presentation, handle, connections)
    sink = ConnectionSink(connected.connected, distance=float("inf"))
    connector.connect(sink)


def diagram_as_pydot(diagram: Diagram, splines: str) -> pydot.Dot:
    graph = pydot.Dot(
        "gaphor", graph_type="digraph", compound="true", pad=8 / DPI, splines=splines
    )

    for presentation in diagram.ownedPresentation:
        if presentation.parent:
            continue

        add_to_graph(graph, as_pydot(presentation))

    return graph


@singledispatch
def as_pydot(element: Base) -> Iterator[pydot.Common]:
    return iter(())


@as_pydot.register
def _(presentation: ElementPresentation):
    if as_cluster(presentation):
        graph = pydot.Cluster(
            presentation.id,
            id=presentation.id,
            label=f"{presentation.subject.name}\n\n\n",
            margin=20,
        )

        # Add a placeholder, so we can connect to the cluster
        graph.add_node(
            pydot.Node(
                f'"{presentation.id}"',
                label="",
                shape="point",
            )
        )

        for child in presentation.children:
            if isinstance(child, AttachedPresentation):
                yield as_pydot(child)
            else:
                add_to_graph(graph, as_pydot(child))

        yield graph
    else:
        for attached in presentation.children:
            if isinstance(attached, AttachedPresentation):
                yield as_pydot(attached)

        yield pydot.Node(
            f'"{presentation.id}"',
            id=presentation.id,
            label="",
            shape="rect",
            width=presentation.width / DPI,
            height=presentation.height / DPI,
        )


@as_pydot.register
def _(presentation: LinePresentation):
    connections = presentation.diagram.connections
    head_connection = connections.get_connection(presentation.head)
    tail_connection = connections.get_connection(presentation.tail)
    if (
        head_connection
        and next(as_pydot(head_connection.connected), None)
        and tail_connection
        and next(as_pydot(tail_connection.connected), None)
    ):
        extra_args = {}
        if as_cluster(head_connection.connected):
            extra_args["lhead"] = f"cluster_{head_connection.connected.id}"
        if as_cluster(tail_connection.connected):
            extra_args["ltail"] = f"cluster_{tail_connection.connected.id}"

        if isinstance(presentation, GeneralizationItem):
            head_id = tail_connection.connected.id
            tail_id = head_connection.connected.id
        else:
            head_id = head_connection.connected.id
            tail_id = tail_connection.connected.id

        yield pydot.Edge(
            head_id,
            tail_id,
            id=presentation.id,
            minlen=3,
            arrowhead="none",
            **extra_args,
        )


@as_pydot.register
def _(presentation: AttachedPresentation):
    yield pydot.Node(
        presentation.id,
        id=presentation.id,
        label="",
        shape="point",
    )
    handle = presentation.handles()[0]
    if connection := presentation.diagram.connections.get_connection(handle):
        yield pydot.Edge(
            connection.connected.id,
            presentation.id,
            len=0.01,
        )


@as_pydot.register
def _(presentation: ForkNodeItem):
    h1, h2 = presentation.handles()
    yield pydot.Node(
        presentation.id,
        id=presentation.id,
        label="",
        shape="rect",
        width=(h2.pos.x - h1.pos.x) / DPI,
        height=(h2.pos.y - h1.pos.y) / DPI,
    )


def as_cluster(presentation: Presentation):
    return presentation.children and not all(
        isinstance(c, AttachedPresentation) for c in presentation.children
    )


def add_to_graph(graph, edge_or_node) -> None:
    if isinstance(edge_or_node, pydot.Edge):
        graph.add_edge(edge_or_node)
    elif isinstance(edge_or_node, pydot.Node):
        graph.add_node(edge_or_node)
    elif isinstance(edge_or_node, pydot.Graph):
        graph.add_subgraph(edge_or_node)
    elif isinstance(edge_or_node, Iterable):
        for obj in edge_or_node:
            add_to_graph(graph, obj)
    elif edge_or_node:
        raise ValueError(f"Can't transform {edge_or_node} to something DOT'ish?")


def parse_edge_pos(pos_str: str, height: float, reverse: bool) -> list[Point]:
    raw_points = strip_quotes(pos_str).split(" ")

    points = [parse_point(raw_points.pop(0), height)]

    while raw_points:
        # Drop bezier curve support points
        raw_points.pop(0)
        raw_points.pop(0)
        points.append(parse_point(raw_points.pop(0), height))
    if reverse:
        points.reverse()
    return points


def parse_point(point, height) -> Point:
    x, y = strip_quotes(point).split(",")
    return (float(x), height - float(y))


def parse_bb(bb, height: float | None = None) -> Rect:
    llx, lly, urx, ury = map(float, strip_quotes(bb).split(","))
    return (llx, lly if height is None else height - ury, urx - llx, ury - lly)


def strip_quotes(s):
    """Replace quotes and line continuations (backslash + newline).

    Basically cleaning up some stuff that Pydot leaves in.
    """
    return s.replace('"', "").replace("\\\n", "").replace("\\\r\n", "")


# Do not auto-layout sequence diagrams
_interaction_items = [i for i in dir(gaphor.UML.interactions) if i.endswith("Item")]
for _item in _interaction_items:
    as_pydot.register(getattr(gaphor.UML.interactions, _item))(lambda _: iter(()))

del _interaction_items
del _item
