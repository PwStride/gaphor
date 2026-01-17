"""Collapse/Expand Service for diagram items.

This service provides actions to collapse, expand, cluster, and uncluster
diagram items. It integrates with the Tools menu in the main application.

The service:
- Follows the ActionProvider pattern used by other plugins
- Registers actions with the tools_menu MenuFragment
- Respects item lock state when performing operations
- Uses DiagramOpened/DiagramClosed events for action enabling
"""

from __future__ import annotations

from gaphor.abc import ActionProvider, Service
from gaphor.action import action
from gaphor.core import event_handler
from gaphor.core.modeling import Diagram
from gaphor.diagram.collapsible import (
    Collapsible,
    assign_collapse_group,
    cluster_items,
    generate_group_id,
    remove_from_collapse_group,
    uncluster_items,
)
from gaphor.diagram.event import DiagramClosed, DiagramOpened
from gaphor.diagram.lockable import is_item_locked
from gaphor.event import ActionEnabled
from gaphor.i18n import gettext
from gaphor.transaction import Transaction


class CollapseExpandService(Service, ActionProvider):
    """Service that provides collapse/expand functionality for diagram items.

    This service adds menu items to the Tools menu for:
    - Collapse Selected / Expand Selected
    - Create Collapse Group / Remove from Collapse Group
    - Cluster Selected / Uncluster Selected

    The service follows the plugin pattern used by AutoLayoutService and other
    plugins, registering actions via the tools_menu MenuFragment.
    """

    def __init__(self, event_manager, diagrams, tools_menu=None):
        """Initialize the CollapseExpandService.

        Args:
            event_manager: The application event manager
            diagrams: The Diagrams service for accessing current diagram/page
            tools_menu: Optional MenuFragment to register actions with
        """
        self.event_manager = event_manager
        self.diagrams = diagrams
        if tools_menu:
            tools_menu.add_actions(self)

        event_manager.subscribe(self.on_diagram_opened_or_closed)

    def shutdown(self):
        """Clean up event subscriptions on service shutdown."""
        self.event_manager.unsubscribe(self.on_diagram_opened_or_closed)

    @event_handler(DiagramOpened, DiagramClosed)
    def on_diagram_opened_or_closed(self, event: DiagramOpened | DiagramClosed):
        """Enable/disable actions based on whether a diagram is open."""
        enabled = (
            isinstance(event, DiagramOpened) or self.diagrams.get_current_diagram()
        )

        # Enable all collapse/expand related actions
        for action_name in (
            "win.collapse-selected",
            "win.expand-selected",
            "win.group-collapse",
            "win.ungroup-collapse",
            "win.cluster-selected",
            "win.uncluster-selected",
        ):
            self.event_manager.handle(ActionEnabled(action_name, enabled))

    def _get_selected_items(self):
        """Get currently selected items from the active diagram view."""
        if page := self.diagrams.get_current_page():
            if view := page.view:
                return view.selection.selected_items
        return set()

    def _get_collapsible_items(self, check_locked: bool = True):
        """Get collapsible items from current selection.

        Args:
            check_locked: If True, filter out locked items

        Returns:
            List of Collapsible items from the current selection
        """
        items = []
        for item in self._get_selected_items():
            if isinstance(item, Collapsible):
                if check_locked and is_item_locked(item):
                    continue
                items.append(item)
        return items

    def _get_current_diagram(self) -> Diagram | None:
        """Get the current diagram."""
        return self.diagrams.get_current_diagram()

    def _get_view(self):
        """Get the current diagram view."""
        if page := self.diagrams.get_current_page():
            return page.view
        return None

    @action(
        name="collapse-selected",
        label=gettext("Collapse Selected"),
        shortcut="<Primary><Shift>C",
    )
    def collapse_selected(self):
        """Collapse all selected collapsible items.

        Locked items are skipped to respect the lock state.
        """
        collapsible_items = self._get_collapsible_items(check_locked=True)
        if not collapsible_items:
            return

        with Transaction(self.event_manager):
            for item in collapsible_items:
                item.collapsed = 1

    @action(
        name="expand-selected",
        label=gettext("Expand Selected"),
        shortcut="<Primary><Shift>E",
    )
    def expand_selected(self):
        """Expand all selected collapsible items.

        Locked items are skipped to respect the lock state.
        """
        collapsible_items = self._get_collapsible_items(check_locked=True)
        if not collapsible_items:
            return

        with Transaction(self.event_manager):
            for item in collapsible_items:
                item.collapsed = 0

    @action(
        name="group-collapse",
        label=gettext("Create Collapse Group"),
    )
    def group_collapse(self):
        """Create a collapse group from selected items.

        Requires at least 2 collapsible items to be selected.
        Locked items are skipped.
        """
        collapsible_items = self._get_collapsible_items(check_locked=True)
        if len(collapsible_items) < 2:
            return

        with Transaction(self.event_manager):
            group_id = generate_group_id()
            assign_collapse_group(collapsible_items, group_id)

    @action(
        name="ungroup-collapse",
        label=gettext("Remove from Collapse Group"),
    )
    def ungroup_collapse(self):
        """Remove selected items from their collapse groups.

        Locked items are skipped.
        """
        collapsible_items = self._get_collapsible_items(check_locked=True)
        if not collapsible_items:
            return

        with Transaction(self.event_manager):
            remove_from_collapse_group(collapsible_items)

    @action(
        name="cluster-selected",
        label=gettext("Cluster Selected"),
        shortcut="<Primary><Shift>U",
    )
    def cluster_selected(self):
        """Cluster selected items: collapse, pack tightly, and group together.

        This operation:
        1. Filters out locked items (respects lock state)
        2. Collapses all selected collapsible items to their minimum size
        3. Removes extra space between items
        4. Arranges items in a compact grid layout
        5. Creates a collapse group so items can be expanded/collapsed together
        6. Ensures minimum interactive dimensions for usability

        Requires at least 2 collapsible items to be selected.
        """
        collapsible_items = self._get_collapsible_items(check_locked=True)
        if len(collapsible_items) < 2:
            return

        with Transaction(self.event_manager):
            cluster_items(
                collapsible_items,
                gap=0,
                create_group=True,
                preserve_existing_groups=True,
            )

        # Post-transaction cleanup: force view refresh for proper GTK rendering
        self._force_view_refresh()

    @action(
        name="uncluster-selected",
        label=gettext("Uncluster Selected"),
    )
    def uncluster_selected(self):
        """Uncluster selected items: expand and remove from cluster group.

        This operation:
        1. Expands all selected collapsible items
        2. Removes them from auto-generated cluster groups
        3. Preserves manually created groups
        4. Respects item lock state

        The uncluster_items function internally handles lock checking.
        """
        collapsible_items = self._get_collapsible_items(check_locked=False)
        if not collapsible_items:
            return

        with Transaction(self.event_manager):
            # uncluster_items handles lock checking internally
            uncluster_items(collapsible_items)

        # Post-transaction cleanup: force view refresh
        self._force_view_refresh()

    def _force_view_refresh(self):
        """Force a complete view refresh to ensure proper GTK menu rendering.

        This method ensures that:
        1. The back buffer is updated with new item positions/sizes
        2. Matrix caches are invalidated for proper coordinate transforms
        3. The view is queued for redraw
        """
        view = self._get_view()
        if not view:
            return

        # Update the back buffer with current item states
        view.update_back_buffer()

        # Request all items to update their visual state
        if current_diagram := self._get_current_diagram():
            for item in current_diagram.get_all_items():
                item.request_update()

        # Queue a redraw to ensure GTK processes the changes
        view.queue_draw()
