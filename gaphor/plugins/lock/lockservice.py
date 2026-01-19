"""Lock Service for diagram items.

This service provides actions to lock and unlock diagram items from the
main menu Tools section. It works at a broader system scope, allowing
users to lock/unlock items across the entire diagram.

The service:
- Follows the ActionProvider pattern used by other plugins
- Registers actions with the tools_menu MenuFragment
- Provides lock/unlock functionality for selected items
- Uses DiagramOpened/DiagramClosed events for action enabling
- Maintains the draw_lock_icon functionality from the Lockable mixin
"""

from __future__ import annotations

from gaphor.abc import ActionProvider, Service
from gaphor.action import action
from gaphor.core import event_handler
from gaphor.core.modeling import Diagram
from gaphor.diagram.event import DiagramClosed, DiagramOpened
from gaphor.event import ActionEnabled
from gaphor.i18n import gettext
from gaphor.plugins.lock.lockable import Lockable, is_item_locked
from gaphor.transaction import Transaction


class LockService(Service, ActionProvider):
    """Service that provides lock/unlock functionality for diagram items.

    This service adds menu items to the Tools menu for:
    - Lock Selected: Lock all selected lockable items
    - Unlock Selected: Unlock all selected lockable items
    - Toggle Lock: Toggle the lock state of selected items
    - Lock All: Lock all items in the current diagram
    - Unlock All: Unlock all items in the current diagram

    The service follows the plugin pattern used by AutoLayoutService,
    registering actions via the tools_menu MenuFragment.
    """

    def __init__(self, event_manager, diagrams, tools_menu=None):
        """Initialize the LockService.

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

        # Enable all lock related actions
        for action_name in (
            "win.lock-selected",
            "win.unlock-selected",
            "win.toggle-lock",
            "win.lock-all",
            "win.unlock-all",
        ):
            self.event_manager.handle(ActionEnabled(action_name, enabled))

    def _get_selected_items(self):
        """Get currently selected items from the active diagram view."""
        if page := self.diagrams.get_current_page():
            if view := page.view:
                return view.selection.selected_items
        return set()

    def _get_lockable_items(self):
        """Get lockable items from current selection.

        Returns:
            List of Lockable items from the current selection
        """
        items = []
        for item in self._get_selected_items():
            if isinstance(item, Lockable):
                items.append(item)
        return items

    def _get_current_diagram(self) -> Diagram | None:
        """Get the current diagram."""
        return self.diagrams.get_current_diagram()

    def _get_all_lockable_items(self):
        """Get all lockable items from the current diagram.

        Returns:
            List of all Lockable items in the current diagram
        """
        items = []
        if diagram := self._get_current_diagram():
            for item in diagram.get_all_items():
                if isinstance(item, Lockable):
                    items.append(item)
        return items

    def _get_view(self):
        """Get the current diagram view."""
        if page := self.diagrams.get_current_page():
            return page.view
        return None

    @action(
        name="lock-selected",
        label=gettext("Lock Selected"),
        shortcut="<Primary>L",
    )
    def lock_selected(self):
        """Lock all selected lockable items.

        Items that are already locked remain locked.
        """
        lockable_items = self._get_lockable_items()
        if not lockable_items:
            return

        with Transaction(self.event_manager):
            for item in lockable_items:
                item.locked = 1

        self._force_view_refresh()

    @action(
        name="unlock-selected",
        label=gettext("Unlock Selected"),
        shortcut="<Primary><Shift>U",
    )
    def unlock_selected(self):
        """Unlock all selected lockable items.

        Items that are already unlocked remain unlocked.
        """
        lockable_items = self._get_lockable_items()
        if not lockable_items:
            return

        with Transaction(self.event_manager):
            for item in lockable_items:
                item.locked = 0

        self._force_view_refresh()

    @action(
        name="toggle-lock",
        label=gettext("Toggle Lock"),
    )
    def toggle_lock(self):
        """Toggle the lock state of all selected lockable items.

        Locked items become unlocked, and unlocked items become locked.
        """
        lockable_items = self._get_lockable_items()
        if not lockable_items:
            return

        with Transaction(self.event_manager):
            for item in lockable_items:
                item.locked = 0 if item.locked else 1

        self._force_view_refresh()

    @action(
        name="lock-all",
        label=gettext("Lock All Items"),
    )
    def lock_all(self):
        """Lock all lockable items in the current diagram.

        This operates at the diagram scope, locking every lockable item.
        """
        lockable_items = self._get_all_lockable_items()
        if not lockable_items:
            return

        with Transaction(self.event_manager):
            for item in lockable_items:
                item.locked = 1

        self._force_view_refresh()

    @action(
        name="unlock-all",
        label=gettext("Unlock All Items"),
    )
    def unlock_all(self):
        """Unlock all lockable items in the current diagram.

        This operates at the diagram scope, unlocking every lockable item.
        """
        lockable_items = self._get_all_lockable_items()
        if not lockable_items:
            return

        with Transaction(self.event_manager):
            for item in lockable_items:
                item.locked = 0

        self._force_view_refresh()

    def _force_view_refresh(self):
        """Force a complete view refresh to ensure proper rendering.

        This method ensures that:
        1. The back buffer is updated with new item states
        2. Lock icons are properly drawn/hidden
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
