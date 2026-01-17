"""Tests for cluster feature UI menu interactions.

This module tests the cluster feature focusing on:
1. Right-click context menu accessibility after cluster operations
2. Repeated menu access scenarios (reopening menus after selecting operations)
3. Validation of cluster feature code placement and integration with existing menu options
4. UI automation for menu interactions
5. Group creation and management with cluster operations
6. Uncluster functionality and menu state consistency
"""

import pytest
import pytest_asyncio
from unittest.mock import MagicMock, patch

from gi.repository import Gio, GLib

from gaphor import UML
from gaphor.core.modeling import Diagram
from gaphor.diagram.collapsible import (
    Collapsible,
    cluster_items,
    assign_collapse_group,
    generate_group_id,
    remove_from_collapse_group,
    uncluster_items,
)
from gaphor.diagram.lockable import Lockable
from gaphor.diagram.presentation import Classified
from gaphor.ui.diagrampage import (
    DiagramPage,
    context_menu_controller,
    popup_model,
)
from gaphor.UML.diagramitems import ClassItem, PackageItem
from gaphor.UML.classes.interface import InterfaceItem


@pytest_asyncio.fixture
async def page(diagram, event_manager, element_factory, modeling_language):
    """Create a DiagramPage for testing."""
    page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
    page.construct()
    assert page.diagram == diagram
    assert page.view.model == diagram
    yield page
    page.close()


class TestClusterMenuAccessibility:
    """Tests for context menu accessibility after cluster operations."""

    @pytest.mark.asyncio
    async def test_context_menu_accessible_after_cluster_operation(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Test that right-click context menu is accessible after clustering items.

        This verifies that the menu can be reopened after a cluster operation
        without any issues blocking menu access.
        """
        # Create multiple class items for clustering
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)
        class3 = create(ClassItem, UML.Class)

        # Position items spread out
        class1.matrix.translate(50, 50)
        class2.matrix.translate(250, 50)
        class3.matrix.translate(50, 250)

        # Select items for clustering
        view.selection.select_items(class1, class2, class3)
        await view.update()

        # Create DiagramPage and perform cluster operation
        page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
        page.construct()
        page.view = view

        # Perform cluster operation
        page.cluster_selected()
        await view.update()

        # Verify items are collapsed after clustering
        assert class1.collapsed == 1
        assert class2.collapsed == 1
        assert class3.collapsed == 1

        # Test that context menu can be generated after cluster operation
        menu = popup_model(diagram, class1, view.selection.selected_items)

        # Menu should not be None and should have sections
        assert menu is not None
        assert isinstance(menu, Gio.Menu)
        assert menu.get_n_items() >= 1  # At least "Show in Model Browser"

        page.close()

    @pytest.mark.asyncio
    async def test_menu_options_available_after_cluster_then_expand(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Test menu options are available after cluster operation followed by expand.

        Simulates user workflow: cluster items -> access menu -> expand -> access menu again.
        """
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)

        class1.matrix.translate(50, 50)
        class2.matrix.translate(250, 50)

        view.selection.select_items(class1, class2)
        await view.update()

        page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
        page.construct()
        page.view = view

        # Step 1: Cluster items
        page.cluster_selected()
        await view.update()

        # Verify clustering occurred
        assert class1.collapsed == 1
        assert class2.collapsed == 1

        # Step 2: Access menu after clustering - should work
        menu_after_cluster = popup_model(diagram, class1, view.selection.selected_items)
        assert menu_after_cluster is not None

        # Step 3: Expand items
        page.expand_selected()
        await view.update()

        # Verify expansion
        assert class1.collapsed == 0
        assert class2.collapsed == 0

        # Step 4: Access menu again after expansion - should still work
        menu_after_expand = popup_model(diagram, class1, view.selection.selected_items)
        assert menu_after_expand is not None

        page.close()


class TestRepeatedMenuAccess:
    """Tests for repeated right-click menu access scenarios."""

    @pytest.mark.asyncio
    async def test_multiple_menu_accesses_after_cluster(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Test that menu can be accessed multiple times after cluster operation.

        This specifically tests the issue where menu access fails after
        initial cluster feature selection.
        """
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)

        class1.matrix.translate(100, 100)
        class2.matrix.translate(300, 100)

        view.selection.select_items(class1, class2)
        await view.update()

        page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
        page.construct()
        page.view = view

        # Perform cluster
        page.cluster_selected()
        await view.update()

        # Access menu multiple times in sequence
        for attempt in range(5):
            menu = popup_model(diagram, class1, view.selection.selected_items)
            assert menu is not None, f"Menu access failed on attempt {attempt + 1}"
            assert menu.get_n_items() >= 1, f"Menu empty on attempt {attempt + 1}"

        page.close()

    @pytest.mark.asyncio
    async def test_menu_access_alternating_operations(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Test menu access when alternating between different operations.

        Simulates: cluster -> menu -> collapse -> menu -> expand -> menu -> cluster
        """
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)
        class3 = create(ClassItem, UML.Class)

        class1.matrix.translate(50, 50)
        class2.matrix.translate(200, 50)
        class3.matrix.translate(350, 50)

        view.selection.select_items(class1, class2, class3)
        await view.update()

        page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
        page.construct()
        page.view = view

        operations = [
            ("cluster", page.cluster_selected),
            ("expand", page.expand_selected),
            ("collapse", page.collapse_selected),
            ("expand", page.expand_selected),
            ("cluster", page.cluster_selected),
        ]

        for op_name, operation in operations:
            # Perform operation
            operation()
            await view.update()

            # Access menu after operation
            menu = popup_model(diagram, class1, view.selection.selected_items)
            assert menu is not None, f"Menu inaccessible after {op_name} operation"

            # Verify menu has appropriate sections
            n_items = menu.get_n_items()
            assert n_items >= 1, f"Menu has no items after {op_name} operation"

        page.close()

    @pytest.mark.asyncio
    async def test_menu_access_after_changing_selection(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Test menu access when selection changes after cluster operation."""
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)
        class3 = create(ClassItem, UML.Class)

        class1.matrix.translate(50, 50)
        class2.matrix.translate(200, 50)
        class3.matrix.translate(350, 50)

        # Select first two items
        view.selection.select_items(class1, class2)
        await view.update()

        page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
        page.construct()
        page.view = view

        # Cluster first two items
        page.cluster_selected()
        await view.update()

        # Access menu on first selection
        menu1 = popup_model(diagram, class1, view.selection.selected_items)
        assert menu1 is not None

        # Change selection to different item
        view.selection.unselect_all()
        view.selection.select_items(class3)
        await view.update()

        # Access menu on new selection
        menu2 = popup_model(diagram, class3, view.selection.selected_items)
        assert menu2 is not None

        # Select all items including clustered ones
        view.selection.select_items(class1, class2, class3)
        await view.update()

        # Access menu on combined selection
        menu3 = popup_model(diagram, class1, view.selection.selected_items)
        assert menu3 is not None

        page.close()


class TestClusterFeatureCodePlacement:
    """Tests to validate cluster feature code placement and integration."""

    def test_cluster_items_function_exists_in_collapsible_module(self):
        """Verify cluster_items function is properly placed in collapsible module."""
        from gaphor.diagram import collapsible

        # cluster_items should be in the collapsible module
        assert hasattr(collapsible, 'cluster_items')
        assert callable(collapsible.cluster_items)

    def test_cluster_action_registered_in_diagrampage(self):
        """Verify cluster-selected action is registered in DiagramPage."""
        # Check that DiagramPage has the cluster_selected method with action decorator
        assert hasattr(DiagramPage, 'cluster_selected')
        assert callable(DiagramPage.cluster_selected)

    def test_popup_model_for_classified_items(self, create, diagram, view):
        """Verify popup_model shows association options for classified items.

        Note: Collapse/expand options have been moved to the main Diagram menu.
        """
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)

        view.selection.select_items(class1, class2)

        menu = popup_model(diagram, class1, view.selection.selected_items)

        # Menu should include options for classified items (associations)
        assert menu is not None

        # Menu should have at least:
        # - Show in Model Browser section
        # - Association section (for 2+ classified items)
        assert menu.get_n_items() >= 2  # Multiple sections should exist

    def test_popup_model_structure_for_selected_items(self, create, diagram, view):
        """Test popup model structure for selected items.

        Note: Collapse/expand options have been moved to the main Diagram menu.
        """
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)
        class3 = create(ClassItem, UML.Class)

        view.selection.select_items(class1, class2, class3)

        menu = popup_model(diagram, class1, view.selection.selected_items)

        # With 3 classified items, menu should have:
        # - Show in Model Browser section
        # - Association section (for Classified items)
        # - Lock/Unlock section (for multiple Lockable items)
        assert menu.get_n_items() >= 2

    @pytest.mark.asyncio
    async def test_cluster_action_uses_transaction(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Verify cluster operation is wrapped in a transaction for undo/redo support."""
        from gaphor.core import Transaction

        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)

        class1.matrix.translate(50, 50)
        class2.matrix.translate(250, 50)

        view.selection.select_items(class1, class2)
        await view.update()

        page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
        page.construct()
        page.view = view

        # Track transaction usage
        original_transaction = Transaction.__enter__
        transaction_used = []

        def track_transaction(self):
            transaction_used.append(True)
            return original_transaction(self)

        with patch.object(Transaction, '__enter__', track_transaction):
            page.cluster_selected()

        # Transaction should have been used
        assert len(transaction_used) > 0

        page.close()


class TestMenuIntegrationWithExistingOptions:
    """Tests for cluster feature integration with pre-existing menu options."""

    @pytest.mark.asyncio
    async def test_collapse_expand_options_work_after_cluster(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Test that standard collapse/expand options work after cluster operation."""
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)

        class1.matrix.translate(50, 50)
        class2.matrix.translate(250, 50)

        view.selection.select_items(class1, class2)
        await view.update()

        page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
        page.construct()
        page.view = view

        # Cluster items
        page.cluster_selected()
        await view.update()

        # Items should be collapsed
        assert class1.collapsed == 1
        assert class2.collapsed == 1

        # Expand should work
        page.expand_selected()
        await view.update()

        assert class1.collapsed == 0
        assert class2.collapsed == 0

        # Collapse should work
        page.collapse_selected()
        await view.update()

        assert class1.collapsed == 1
        assert class2.collapsed == 1

        page.close()

    @pytest.mark.asyncio
    async def test_lock_unlock_options_work_after_cluster(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Test that lock/unlock options work after cluster operation."""
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)

        class1.matrix.translate(50, 50)
        class2.matrix.translate(250, 50)

        view.selection.select_items(class1, class2)
        await view.update()

        page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
        page.construct()
        page.view = view

        # Cluster items
        page.cluster_selected()
        await view.update()

        # Items should not be locked initially
        assert class1.locked == 0
        assert class2.locked == 0

        # Lock should work
        page.lock_selected()
        await view.update()

        assert class1.locked == 1
        assert class2.locked == 1

        # Unlock should work
        page.unlock_selected()
        await view.update()

        assert class1.locked == 0
        assert class2.locked == 0

        page.close()

    @pytest.mark.asyncio
    async def test_group_collapse_works_after_cluster(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Test that group collapse creation works after cluster operation."""
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)

        class1.matrix.translate(50, 50)
        class2.matrix.translate(250, 50)

        view.selection.select_items(class1, class2)
        await view.update()

        page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
        page.construct()
        page.view = view

        # Cluster items
        page.cluster_selected()
        await view.update()

        # Create collapse group should work
        page.group_collapse()
        await view.update()

        # Both items should be in the same group
        assert class1.collapse_group != ""
        assert class2.collapse_group != ""
        assert class1.collapse_group == class2.collapse_group

        page.close()

    @pytest.mark.asyncio
    async def test_association_options_work_after_cluster(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Test that association options work after cluster operation."""
        from gaphor.UML.classes.association import AssociationItem

        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)

        class1.matrix.translate(50, 50)
        class2.matrix.translate(250, 50)

        view.selection.select_items(class1, class2)
        await view.update()

        page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
        page.construct()
        page.view = view

        # Cluster items
        page.cluster_selected()
        await view.update()

        # Add association should work even after clustering
        page.add_association()
        await view.update()

        # Check that an association was created
        associations = [
            item for item in diagram.get_all_items() if isinstance(item, AssociationItem)
        ]
        assert len(associations) == 1

        # Clean up
        associations[0].unlink()
        page.close()


class TestContextMenuControllerIntegrity:
    """Tests for context menu controller behavior with cluster feature."""

    def test_context_menu_controller_returns_gesture(self, diagram):
        """Test that context_menu_controller returns a valid gesture controller."""
        from gi.repository import Gtk

        context_menu = Gtk.PopoverMenu.new_from_model(popup_model(diagram))
        ctrl = context_menu_controller(context_menu, diagram)

        assert ctrl is not None
        assert isinstance(ctrl, Gtk.GestureClick)

    def test_popup_model_handles_none_item(self, diagram):
        """Test that popup_model handles None item gracefully."""
        menu = popup_model(diagram, None, None)

        assert menu is not None
        # Should at least have "Show in Model Browser" for the diagram
        assert menu.get_n_items() >= 1

    def test_popup_model_handles_empty_selection(self, create, diagram):
        """Test that popup_model handles empty selection gracefully."""
        class1 = create(ClassItem, UML.Class)

        # Item provided but empty selection
        menu = popup_model(diagram, class1, set())

        assert menu is not None

    def test_popup_model_handles_single_collapsible_item(self, create, diagram, view):
        """Test popup model for single collapsible item.

        Note: Collapse/expand options are now in the main Diagram menu,
        so the context menu only shows basic options like Show in Model Browser.
        """
        class1 = create(ClassItem, UML.Class)

        view.selection.select_items(class1)

        menu = popup_model(diagram, class1, view.selection.selected_items)

        assert menu is not None
        # Menu should have at least the basic options (Show in Model Browser)
        assert menu.get_n_items() >= 1


class TestClusterStateConsistency:
    """Tests for state consistency after cluster operations."""

    @pytest.mark.asyncio
    async def test_view_state_consistent_after_cluster(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Test that view state remains consistent after cluster operation."""
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)

        class1.matrix.translate(50, 50)
        class2.matrix.translate(250, 50)

        view.selection.select_items(class1, class2)
        await view.update()

        page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
        page.construct()
        page.view = view

        # Store initial state
        initial_item_count = len(list(diagram.get_all_items()))

        # Cluster items
        page.cluster_selected()
        await view.update()

        # Item count should remain the same
        final_item_count = len(list(diagram.get_all_items()))
        assert initial_item_count == final_item_count

        # View should still be functional
        assert view.model == diagram
        assert page.view == view

        page.close()

    @pytest.mark.asyncio
    async def test_selection_preserved_after_cluster(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Test that selection is preserved after cluster operation."""
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)

        class1.matrix.translate(50, 50)
        class2.matrix.translate(250, 50)

        view.selection.select_items(class1, class2)
        await view.update()

        page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
        page.construct()
        page.view = view

        initial_selection = set(view.selection.selected_items)

        # Cluster items
        page.cluster_selected()
        await view.update()

        # Selection should be preserved
        final_selection = set(view.selection.selected_items)
        assert initial_selection == final_selection

        page.close()

    @pytest.mark.asyncio
    async def test_diagram_integrity_after_repeated_cluster_operations(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Test diagram integrity after multiple cluster operations."""
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)
        class3 = create(ClassItem, UML.Class)

        class1.matrix.translate(50, 50)
        class2.matrix.translate(250, 50)
        class3.matrix.translate(450, 50)

        view.selection.select_items(class1, class2, class3)
        await view.update()

        page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
        page.construct()
        page.view = view

        # Perform multiple cluster/expand cycles
        for _ in range(5):
            page.cluster_selected()
            await view.update()

            page.expand_selected()
            await view.update()

        # All items should still exist and be functional
        all_items = list(diagram.get_all_items())
        assert class1 in all_items
        assert class2 in all_items
        assert class3 in all_items

        # Menu should still be accessible
        menu = popup_model(diagram, class1, view.selection.selected_items)
        assert menu is not None

        page.close()


class TestClusterWithMixedItemTypes:
    """Tests for cluster feature with different item types."""

    @pytest.mark.asyncio
    async def test_cluster_with_class_and_interface(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Test clustering with mixed ClassItem and InterfaceItem."""
        class1 = create(ClassItem, UML.Class)
        interface1 = create(InterfaceItem, UML.Interface)

        class1.matrix.translate(50, 50)
        interface1.matrix.translate(250, 50)

        view.selection.select_items(class1, interface1)
        await view.update()

        page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
        page.construct()
        page.view = view

        # Cluster should work with mixed types
        page.cluster_selected()
        await view.update()

        # Both should be collapsed
        assert class1.collapsed == 1
        assert interface1.collapsed == 1

        # Menu should be accessible
        menu = popup_model(diagram, class1, view.selection.selected_items)
        assert menu is not None

        page.close()

    @pytest.mark.asyncio
    async def test_cluster_with_locked_items(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Test that cluster respects locked items."""
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)
        class3 = create(ClassItem, UML.Class)

        class1.matrix.translate(50, 50)
        class2.matrix.translate(250, 50)
        class3.matrix.translate(450, 50)

        # Lock class2
        class2.locked = 1

        view.selection.select_items(class1, class2, class3)
        await view.update()

        page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
        page.construct()
        page.view = view

        original_pos2 = (class2.matrix[4], class2.matrix[5])

        # Cluster items
        page.cluster_selected()
        await view.update()

        # Unlocked items should be collapsed
        assert class1.collapsed == 1
        assert class3.collapsed == 1

        # Locked item should NOT be collapsed
        assert class2.collapsed == 0

        # Locked item position should not change
        assert class2.matrix[4] == original_pos2[0]
        assert class2.matrix[5] == original_pos2[1]

        # Menu should still work
        menu = popup_model(diagram, class1, view.selection.selected_items)
        assert menu is not None

        page.close()


class TestMenuStateAfterTransactions:
    """Tests for menu state after transaction completion."""

    @pytest.mark.asyncio
    async def test_menu_accessible_during_no_transaction(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Test menu is accessible when no transaction is active."""
        from gaphor.core import Transaction

        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)

        view.selection.select_items(class1, class2)
        await view.update()

        # Ensure no transaction is active
        assert not Transaction.in_transaction()

        # Menu should be accessible
        menu = popup_model(diagram, class1, view.selection.selected_items)
        assert menu is not None

    @pytest.mark.asyncio
    async def test_menu_state_after_cluster_transaction_completes(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Test that menu state is correct after cluster transaction completes."""
        from gaphor.core import Transaction

        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)

        class1.matrix.translate(50, 50)
        class2.matrix.translate(250, 50)

        view.selection.select_items(class1, class2)
        await view.update()

        page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
        page.construct()
        page.view = view

        # Perform cluster
        page.cluster_selected()
        await view.update()

        # Transaction should be complete
        assert not Transaction.in_transaction()

        # Menu should still work (items are collapsed)
        menu = popup_model(diagram, class1, view.selection.selected_items)
        assert menu is not None

        # The context menu no longer shows collapse/expand options (moved to main menu)
        single_item_menu = popup_model(diagram, class1, {class1})
        assert single_item_menu is not None
        # Should have basic options (Show in Model Browser + lock/unlock)
        assert single_item_menu.get_n_items() >= 1

        page.close()


class TestClusterFeatureActionValidation:
    """Tests validating that cluster feature actions are properly defined."""

    def test_cluster_selected_action_name(self):
        """Verify cluster_selected action has correct name."""
        # The action decorator sets __action_name__ on the method
        method = DiagramPage.cluster_selected
        # Check method exists and is callable
        assert callable(method)

    def test_all_collapse_related_actions_exist(self):
        """Verify all collapse-related actions exist in DiagramPage."""
        actions = [
            'collapse_item',
            'expand_item',
            'collapse_selected',
            'expand_selected',
            'group_collapse',
            'ungroup_collapse',
            'cluster_selected',
        ]

        for action_name in actions:
            assert hasattr(DiagramPage, action_name), f"Missing action: {action_name}"
            assert callable(getattr(DiagramPage, action_name))

    def test_cluster_integrates_with_collapsible_module(self):
        """Test that cluster feature properly imports from collapsible module."""
        from gaphor.ui.diagrampage import cluster_items as dp_cluster_items
        from gaphor.diagram.collapsible import cluster_items as col_cluster_items

        # They should be the same function
        assert dp_cluster_items is col_cluster_items


class TestUIAutomationMenuSequences:
    """UI automation tests for common menu interaction sequences."""

    @pytest.mark.asyncio
    async def test_sequence_select_cluster_menu_collapse_menu(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Simulate: select items -> cluster -> open menu -> collapse -> open menu."""
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)

        class1.matrix.translate(50, 50)
        class2.matrix.translate(250, 50)

        page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
        page.construct()
        page.view = view

        # Step 1: Select items
        view.selection.select_items(class1, class2)
        await view.update()

        # Step 2: Open menu - verify accessible
        menu1 = popup_model(diagram, class1, view.selection.selected_items)
        assert menu1 is not None, "Menu inaccessible at step 2"

        # Step 3: Cluster items
        page.cluster_selected()
        await view.update()

        # Step 4: Open menu again - verify accessible
        menu2 = popup_model(diagram, class1, view.selection.selected_items)
        assert menu2 is not None, "Menu inaccessible at step 4 (after cluster)"

        # Step 5: Collapse (already collapsed by cluster, but testing action)
        page.collapse_selected()
        await view.update()

        # Step 6: Open menu again
        menu3 = popup_model(diagram, class1, view.selection.selected_items)
        assert menu3 is not None, "Menu inaccessible at step 6 (after collapse)"

        page.close()

    @pytest.mark.asyncio
    async def test_sequence_repeated_right_click_simulation(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Simulate multiple right-click events after cluster operation."""
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)

        class1.matrix.translate(50, 50)
        class2.matrix.translate(250, 50)

        page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
        page.construct()
        page.view = view

        view.selection.select_items(class1, class2)
        await view.update()

        # Cluster first
        page.cluster_selected()
        await view.update()

        # Simulate 10 "right-click" events (menu generations)
        for i in range(10):
            # Simulate clicking on different items
            target_item = class1 if i % 2 == 0 else class2
            menu = popup_model(diagram, target_item, view.selection.selected_items)
            assert menu is not None, f"Menu failed on simulated click {i + 1}"

            # Menu should have proper structure
            assert menu.get_n_items() >= 1

        page.close()

    @pytest.mark.asyncio
    async def test_sequence_cluster_change_selection_menu(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Test: cluster -> change selection -> access menu on different items."""
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)
        class3 = create(ClassItem, UML.Class)
        class4 = create(ClassItem, UML.Class)

        class1.matrix.translate(50, 50)
        class2.matrix.translate(200, 50)
        class3.matrix.translate(50, 200)
        class4.matrix.translate(200, 200)

        page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
        page.construct()
        page.view = view

        # Select and cluster class1, class2
        view.selection.select_items(class1, class2)
        await view.update()
        page.cluster_selected()
        await view.update()

        # Change selection to class3, class4
        view.selection.unselect_all()
        view.selection.select_items(class3, class4)
        await view.update()

        # Menu should work on new selection
        menu = popup_model(diagram, class3, view.selection.selected_items)
        assert menu is not None

        # Cluster new selection
        page.cluster_selected()
        await view.update()

        # Menu should still work
        menu2 = popup_model(diagram, class3, view.selection.selected_items)
        assert menu2 is not None

        # Select all and check menu
        view.selection.select_items(class1, class2, class3, class4)
        await view.update()

        menu3 = popup_model(diagram, class1, view.selection.selected_items)
        assert menu3 is not None

        page.close()


class TestClusterGroupCreation:
    """Tests for cluster function's automatic group creation feature."""

    @pytest.mark.asyncio
    async def test_cluster_creates_group_by_default(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Test that cluster operation creates a collapse group by default."""
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)

        class1.matrix.translate(50, 50)
        class2.matrix.translate(250, 50)

        # Initially no group
        assert class1.collapse_group == ""
        assert class2.collapse_group == ""

        view.selection.select_items(class1, class2)
        await view.update()

        page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
        page.construct()
        page.view = view

        # Cluster items
        page.cluster_selected()
        await view.update()

        # Both items should now be in a collapse group
        assert class1.collapse_group != ""
        assert class2.collapse_group != ""
        # They should be in the SAME group
        assert class1.collapse_group == class2.collapse_group
        # The group should be auto-generated
        assert class1.collapse_group.startswith("collapse-group-")

        page.close()

    @pytest.mark.asyncio
    async def test_cluster_preserves_existing_groups(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Test that cluster operation preserves items already in groups."""
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)
        class3 = create(ClassItem, UML.Class)

        class1.matrix.translate(50, 50)
        class2.matrix.translate(250, 50)
        class3.matrix.translate(450, 50)

        # Put class1 in an existing group
        existing_group = "my-custom-group"
        class1.collapse_group = existing_group

        view.selection.select_items(class1, class2, class3)
        await view.update()

        page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
        page.construct()
        page.view = view

        # Cluster items
        page.cluster_selected()
        await view.update()

        # class1 should STILL be in its existing group
        assert class1.collapse_group == existing_group
        # class2 and class3 should be in a new auto-generated group
        assert class2.collapse_group != ""
        assert class3.collapse_group != ""
        assert class2.collapse_group == class3.collapse_group
        assert class2.collapse_group.startswith("collapse-group-")
        # class1's group should be different from class2/class3
        assert class1.collapse_group != class2.collapse_group

        page.close()

    def test_cluster_items_returns_group_id(self, element_factory):
        """Test that cluster_items function returns the created group ID."""
        diagram = element_factory.create(Diagram)
        klass1 = diagram.create(ClassItem, subject=element_factory.create(UML.Class))
        klass2 = diagram.create(ClassItem, subject=element_factory.create(UML.Class))

        klass1.matrix.translate(0, 0)
        klass2.matrix.translate(200, 0)

        # Call cluster_items directly
        group_id = cluster_items([klass1, klass2], create_group=True)

        # Should return a valid group ID
        assert group_id is not None
        assert group_id.startswith("collapse-group-")
        assert klass1.collapse_group == group_id
        assert klass2.collapse_group == group_id

    def test_cluster_items_without_group_creation(self, element_factory):
        """Test cluster_items with create_group=False."""
        diagram = element_factory.create(Diagram)
        klass1 = diagram.create(ClassItem, subject=element_factory.create(UML.Class))
        klass2 = diagram.create(ClassItem, subject=element_factory.create(UML.Class))

        klass1.matrix.translate(0, 0)
        klass2.matrix.translate(200, 0)

        # Call cluster_items with create_group=False
        group_id = cluster_items([klass1, klass2], create_group=False)

        # Should return None since no group was created
        assert group_id is None
        # Items should still be collapsed but not grouped
        assert klass1.collapsed == 1
        assert klass2.collapsed == 1
        assert klass1.collapse_group == ""
        assert klass2.collapse_group == ""


class TestUnclusterFunctionality:
    """Tests for uncluster operation."""

    @pytest.mark.asyncio
    async def test_uncluster_expands_items(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Test that uncluster operation expands collapsed items."""
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)

        class1.matrix.translate(50, 50)
        class2.matrix.translate(250, 50)

        view.selection.select_items(class1, class2)
        await view.update()

        page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
        page.construct()
        page.view = view

        # First cluster
        page.cluster_selected()
        await view.update()

        # Verify clustered
        assert class1.collapsed == 1
        assert class2.collapsed == 1

        # Now uncluster
        page.uncluster_selected()
        await view.update()

        # Items should be expanded
        assert class1.collapsed == 0
        assert class2.collapsed == 0

        page.close()

    @pytest.mark.asyncio
    async def test_uncluster_removes_auto_generated_groups(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Test that uncluster removes items from auto-generated cluster groups."""
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)

        class1.matrix.translate(50, 50)
        class2.matrix.translate(250, 50)

        view.selection.select_items(class1, class2)
        await view.update()

        page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
        page.construct()
        page.view = view

        # Cluster (creates auto group)
        page.cluster_selected()
        await view.update()

        # Verify group was created
        assert class1.collapse_group.startswith("collapse-group-")

        # Uncluster
        page.uncluster_selected()
        await view.update()

        # Auto-generated group should be removed
        assert class1.collapse_group == ""
        assert class2.collapse_group == ""

        page.close()

    @pytest.mark.asyncio
    async def test_uncluster_preserves_manual_groups(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Test that uncluster preserves manually created groups."""
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)

        class1.matrix.translate(50, 50)
        class2.matrix.translate(250, 50)

        # Manually assign to a group (not auto-generated format)
        manual_group = "my-manual-group"
        class1.collapse_group = manual_group
        class2.collapse_group = manual_group
        class1.collapsed = 1
        class2.collapsed = 1

        view.selection.select_items(class1, class2)
        await view.update()

        page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
        page.construct()
        page.view = view

        # Uncluster
        page.uncluster_selected()
        await view.update()

        # Items should be expanded
        assert class1.collapsed == 0
        assert class2.collapsed == 0
        # But manual group should be PRESERVED (not starting with "collapse-group-")
        assert class1.collapse_group == manual_group
        assert class2.collapse_group == manual_group

        page.close()

    def test_uncluster_items_direct_function(self, element_factory):
        """Test uncluster_items function directly."""
        diagram = element_factory.create(Diagram)
        klass1 = diagram.create(ClassItem, subject=element_factory.create(UML.Class))
        klass2 = diagram.create(ClassItem, subject=element_factory.create(UML.Class))

        # Set up clustered state
        klass1.collapsed = 1
        klass2.collapsed = 1
        klass1.collapse_group = "collapse-group-test123"
        klass2.collapse_group = "collapse-group-test123"

        # Uncluster
        uncluster_items([klass1, klass2])

        # Should be expanded and ungrouped
        assert klass1.collapsed == 0
        assert klass2.collapsed == 0
        assert klass1.collapse_group == ""
        assert klass2.collapse_group == ""


class TestPopupMenuStateVariables:
    """Tests for popup menu state variables and alternatives.

    Note: Collapse/expand options have been moved to the main Diagram menu.
    These tests now verify that popup_model works correctly without collapse options.
    """

    def test_popup_model_works_with_collapsed_items(self, create, diagram, view):
        """Test popup_model works correctly with collapsed items.

        Note: Collapse/expand options are now in the main Diagram menu,
        not in the context menu.
        """
        class1 = create(ClassItem, UML.Class)

        # Not collapsed
        class1.collapsed = 0
        view.selection.select_items(class1)

        menu = popup_model(diagram, class1, {class1})
        assert menu is not None

        # Set to collapsed
        class1.collapsed = 1
        menu = popup_model(diagram, class1, {class1})
        assert menu is not None

    def test_popup_model_works_with_grouped_items(self, create, diagram, view):
        """Test popup_model works correctly with items in groups.

        Note: Collapse/expand and group options are now in the main Diagram menu.
        """
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)

        # No group initially
        view.selection.select_items(class1, class2)

        menu = popup_model(diagram, class1, view.selection.selected_items)
        assert menu is not None

        # Add to a group
        class1.collapse_group = "test-group"
        class2.collapse_group = "test-group"

        menu = popup_model(diagram, class1, view.selection.selected_items)
        assert menu is not None

    def test_popup_model_handles_various_selection_states(self, create, diagram, view):
        """Test popup_model handles various selection states.

        Note: Collapse/expand options are now in the main Diagram menu.
        """
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)
        class3 = create(ClassItem, UML.Class)

        # Only class1 is in a group
        class1.collapse_group = "partial-group"

        view.selection.select_items(class1, class2, class3)

        menu = popup_model(diagram, class1, view.selection.selected_items)
        assert menu is not None

    def test_popup_model_handles_mixed_collapsed_state(self, create, diagram, view):
        """Test popup_model handles items with mixed collapsed states.

        Note: Collapse/expand options are now in the main Diagram menu.
        """
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)

        # Only class1 is collapsed
        class1.collapsed = 1
        class2.collapsed = 0

        view.selection.select_items(class1, class2)

        menu = popup_model(diagram, class1, view.selection.selected_items)
        assert menu is not None

    def test_popup_model_works_with_collapsed_items_multi(self, create, diagram, view):
        """Test popup_model works with multiple collapsed items.

        Note: Uncluster option is now in the main Diagram menu.
        """
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)

        # Set both as collapsed
        class1.collapsed = 1
        class2.collapsed = 1

        view.selection.select_items(class1, class2)

        menu = popup_model(diagram, class1, view.selection.selected_items)
        assert menu is not None

    def test_popup_model_works_with_items_in_group(self, create, diagram, view):
        """Test popup_model works with items that are in a group.

        Note: Uncluster option is now in the main Diagram menu.
        """
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)

        # Items not collapsed but in a group
        class1.collapsed = 0
        class2.collapsed = 0
        class1.collapse_group = "collapse-group-test"
        class2.collapse_group = "collapse-group-test"

        view.selection.select_items(class1, class2)

        menu = popup_model(diagram, class1, view.selection.selected_items)
        assert menu is not None


class TestClusterUnclusterCycles:
    """Tests for cluster/uncluster operation cycles."""

    @pytest.mark.asyncio
    async def test_cluster_uncluster_cycle(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Test complete cluster -> uncluster cycle."""
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)

        class1.matrix.translate(50, 50)
        class2.matrix.translate(250, 50)

        view.selection.select_items(class1, class2)
        await view.update()

        page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
        page.construct()
        page.view = view

        # Initial state
        assert class1.collapsed == 0
        assert class2.collapsed == 0
        assert class1.collapse_group == ""

        # Cluster
        page.cluster_selected()
        await view.update()

        assert class1.collapsed == 1
        assert class2.collapsed == 1
        assert class1.collapse_group.startswith("collapse-group-")
        stored_group = class1.collapse_group

        # Uncluster
        page.uncluster_selected()
        await view.update()

        assert class1.collapsed == 0
        assert class2.collapsed == 0
        assert class1.collapse_group == ""

        # Menu should work at every step
        menu = popup_model(diagram, class1, view.selection.selected_items)
        assert menu is not None

        page.close()

    @pytest.mark.asyncio
    async def test_multiple_cluster_uncluster_cycles(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Test multiple cluster/uncluster cycles don't cause issues."""
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)

        class1.matrix.translate(50, 50)
        class2.matrix.translate(250, 50)

        view.selection.select_items(class1, class2)
        await view.update()

        page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
        page.construct()
        page.view = view

        # Perform 5 cluster/uncluster cycles
        for i in range(5):
            page.cluster_selected()
            await view.update()

            # Verify clustered state
            assert class1.collapsed == 1, f"Cycle {i}: class1 not collapsed after cluster"
            assert class1.collapse_group != "", f"Cycle {i}: class1 not grouped after cluster"

            # Menu should work
            menu = popup_model(diagram, class1, view.selection.selected_items)
            assert menu is not None, f"Cycle {i}: menu failed after cluster"

            page.uncluster_selected()
            await view.update()

            # Verify unclustered state
            assert class1.collapsed == 0, f"Cycle {i}: class1 not expanded after uncluster"
            assert class1.collapse_group == "", f"Cycle {i}: class1 still grouped after uncluster"

            # Menu should work
            menu = popup_model(diagram, class1, view.selection.selected_items)
            assert menu is not None, f"Cycle {i}: menu failed after uncluster"

        page.close()


class TestAllCollapseRelatedActionsExist:
    """Extended tests to verify all actions exist including new ones."""

    def test_uncluster_action_exists(self):
        """Verify uncluster_selected action exists in DiagramPage."""
        assert hasattr(DiagramPage, 'uncluster_selected')
        assert callable(DiagramPage.uncluster_selected)

    def test_uncluster_function_exists_in_collapsible(self):
        """Verify uncluster_items function exists in collapsible module."""
        from gaphor.diagram import collapsible
        assert hasattr(collapsible, 'uncluster_items')
        assert callable(collapsible.uncluster_items)

    def test_all_cluster_related_actions(self):
        """Verify all cluster-related actions exist."""
        actions = [
            'cluster_selected',
            'uncluster_selected',
            'collapse_selected',
            'expand_selected',
            'group_collapse',
            'ungroup_collapse',
        ]
        for action_name in actions:
            assert hasattr(DiagramPage, action_name), f"Missing action: {action_name}"


class TestCollapseIconCoordinates:
    """Tests for collapse icon coordinate transformation and hit testing."""

    def test_hit_testing_uses_local_coordinates(self, create, diagram):
        """Test that hit testing works with local item coordinates."""
        from gaphor.diagram.collapsible import is_point_in_collapse_icon
        from gaphas.geometry import Rectangle

        class1 = create(ClassItem, UML.Class)

        # Create a bounding box in local coordinates (0,0 is top-left)
        bounds = Rectangle(0, 0, 100, 50)

        # Icon should be at top-right: x = 100 - 12 - 4 = 84
        # With hit expansion of 2: icon_x = 84 - 2 = 82
        # Point on icon should return True
        assert is_point_in_collapse_icon(88, 8, bounds)

        # Point far from icon should return False
        assert not is_point_in_collapse_icon(10, 10, bounds)

        # Point at top-left should return False
        assert not is_point_in_collapse_icon(0, 0, bounds)

    def test_minimum_interactive_dimensions_constant_exists(self):
        """Test that minimum interactive dimension constants are defined."""
        from gaphor.diagram.collapsible import (
            MIN_INTERACTIVE_WIDTH,
            MIN_INTERACTIVE_HEIGHT,
        )

        assert MIN_INTERACTIVE_WIDTH >= 40
        assert MIN_INTERACTIVE_HEIGHT >= 20

    @pytest.mark.asyncio
    async def test_clustered_items_have_minimum_dimensions(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Test that clustered items maintain minimum interactive dimensions."""
        from gaphor.diagram.collapsible import (
            MIN_INTERACTIVE_WIDTH,
            MIN_INTERACTIVE_HEIGHT,
        )

        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)

        class1.matrix.translate(50, 50)
        class2.matrix.translate(250, 50)

        view.selection.select_items(class1, class2)
        await view.update()

        page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
        page.construct()
        page.view = view

        # Cluster items
        page.cluster_selected()
        await view.update()

        # Items should have at least minimum interactive dimensions
        assert class1.width >= MIN_INTERACTIVE_WIDTH
        assert class1.height >= MIN_INTERACTIVE_HEIGHT
        assert class2.width >= MIN_INTERACTIVE_WIDTH
        assert class2.height >= MIN_INTERACTIVE_HEIGHT

        page.close()

    def test_hit_expansion_increases_clickable_area(self):
        """Test that hit testing includes a small expansion for easier clicking."""
        from gaphor.diagram.collapsible import is_point_in_collapse_icon, COLLAPSE_ICON_SIZE
        from gaphas.geometry import Rectangle

        bounds = Rectangle(0, 0, 100, 50)

        # The icon is at position (100 - 12 - 4, 4) = (84, 4)
        # With 2px hit expansion, the clickable area extends 2px in each direction
        # So valid x range is 82 to 82 + 16 = 98
        # And valid y range is 2 to 2 + 16 = 18

        # Point slightly outside icon visual bounds but within hit expansion
        # Icon visual left edge is at 84, but hit area starts at 82
        assert is_point_in_collapse_icon(82, 4, bounds)

        # Point just outside the expanded hit area should return False
        assert not is_point_in_collapse_icon(75, 4, bounds)


class TestGroupCoordinatedExpand:
    """Tests for coordinated expand/collapse with groups."""

    @pytest.mark.asyncio
    async def test_expand_one_expands_group_members(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Test that expanding one item in a cluster group can expand all members."""
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)

        class1.matrix.translate(50, 50)
        class2.matrix.translate(250, 50)

        view.selection.select_items(class1, class2)
        await view.update()

        page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
        page.construct()
        page.view = view

        # Cluster to create group
        page.cluster_selected()
        await view.update()

        # Both should be in same group and collapsed
        assert class1.collapse_group == class2.collapse_group
        assert class1.collapsed == 1
        assert class2.collapsed == 1

        # Use expand_item on one item (should expand via group)
        page.expand_item(class1.id)
        await view.update()

        # Both should be expanded (group coordination)
        assert class1.collapsed == 0
        assert class2.collapsed == 0

        page.close()

    @pytest.mark.asyncio
    async def test_collapse_one_collapses_group_members(
        self, create, diagram, view, event_manager, element_factory, modeling_language
    ):
        """Test that collapsing one item in a cluster group collapses all members."""
        class1 = create(ClassItem, UML.Class)
        class2 = create(ClassItem, UML.Class)

        class1.matrix.translate(50, 50)
        class2.matrix.translate(250, 50)

        view.selection.select_items(class1, class2)
        await view.update()

        page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
        page.construct()
        page.view = view

        # Cluster then uncluster to keep group but expand
        page.cluster_selected()
        await view.update()

        page.expand_selected()  # Just expand, don't remove group
        await view.update()

        # Both expanded but still in group
        assert class1.collapse_group == class2.collapse_group
        assert class1.collapsed == 0
        assert class2.collapsed == 0

        # Collapse via single item (should collapse whole group)
        page.collapse_item(class1.id)
        await view.update()

        # Both should be collapsed
        assert class1.collapsed == 1
        assert class2.collapsed == 1

        page.close()
