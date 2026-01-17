"""Tests for the CollapseExpandService plugin."""

import pytest

from gaphor import UML
from gaphor.abc import ActionProvider
from gaphor.core.modeling import Diagram
from gaphor.diagram.collapsible import Collapsible
from gaphor.diagram.event import DiagramClosed, DiagramOpened
from gaphor.plugins.diagramtools.collapseexpand import CollapseExpandService
from gaphor.UML.diagramitems import ClassItem


class TestCollapseExpandService:
    """Tests for the CollapseExpandService."""

    def test_service_is_action_provider(self):
        """Test that CollapseExpandService inherits from ActionProvider."""
        assert issubclass(CollapseExpandService, ActionProvider)

    def test_service_has_required_actions(self):
        """Test that the service has all required action methods."""
        actions = [
            "collapse_selected",
            "expand_selected",
            "group_collapse",
            "ungroup_collapse",
            "cluster_selected",
            "uncluster_selected",
        ]
        for action_name in actions:
            assert hasattr(CollapseExpandService, action_name)
            assert callable(getattr(CollapseExpandService, action_name))

    def test_service_action_decorators(self):
        """Test that actions have proper decorators with names and labels."""
        # Check that __action__ attribute exists on decorated methods
        method = CollapseExpandService.collapse_selected
        assert hasattr(method, "__action__")
        assert method.__action__.name == "collapse-selected"
        assert method.__action__.label is not None

        method = CollapseExpandService.expand_selected
        assert hasattr(method, "__action__")
        assert method.__action__.name == "expand-selected"

        method = CollapseExpandService.cluster_selected
        assert hasattr(method, "__action__")
        assert method.__action__.name == "cluster-selected"


class TestCollapseExpandServiceIntegration:
    """Integration tests for CollapseExpandService with diagrams."""

    @pytest.fixture
    def mock_diagrams(self):
        """Create a mock Diagrams service."""

        class MockView:
            class Selection:
                def __init__(self):
                    self._items = set()

                @property
                def selected_items(self):
                    return self._items

            def __init__(self):
                self.selection = self.Selection()

            def update_back_buffer(self):
                pass

            def queue_draw(self):
                pass

        class MockPage:
            def __init__(self):
                self.view = MockView()

        class MockDiagrams:
            def __init__(self):
                self._current_diagram = None
                self._current_page = MockPage()

            def get_current_diagram(self):
                return self._current_diagram

            def get_current_page(self):
                return self._current_page

        return MockDiagrams()

    @pytest.fixture
    def service(self, event_manager, mock_diagrams):
        """Create a CollapseExpandService for testing."""
        service = CollapseExpandService(event_manager, mock_diagrams)
        yield service
        service.shutdown()

    def test_service_initialization(self, service):
        """Test that service initializes correctly."""
        assert service.event_manager is not None
        assert service.diagrams is not None

    def test_collapse_selected_with_no_selection(self, service):
        """Test collapse_selected with no items selected does nothing."""
        # Should not raise any errors
        service.collapse_selected()

    def test_expand_selected_with_no_selection(self, service):
        """Test expand_selected with no items selected does nothing."""
        # Should not raise any errors
        service.expand_selected()

    def test_on_diagram_opened_or_closed_handler(self, service, event_manager, mock_diagrams):
        """Test that the diagram opened/closed event handler works."""
        # Create a mock diagram
        mock_diagrams._current_diagram = object()

        # Simulate diagram opened event
        event = DiagramOpened(mock_diagrams._current_diagram)
        service.on_diagram_opened_or_closed(event)

        # Should not raise any errors


class TestCollapseExpandServiceActions:
    """Tests for individual service actions."""

    @pytest.fixture
    def service_with_items(self, event_manager, element_factory):
        """Create a service with some selected items for testing."""

        class MockView:
            class Selection:
                def __init__(self):
                    self._items = set()

                @property
                def selected_items(self):
                    return self._items

            def __init__(self):
                self.selection = self.Selection()

            def update_back_buffer(self):
                pass

            def queue_draw(self):
                pass

        class MockPage:
            def __init__(self):
                self.view = MockView()

        class MockDiagrams:
            def __init__(self):
                self._current_diagram = None
                self._current_page = MockPage()

            def get_current_diagram(self):
                return self._current_diagram

            def get_current_page(self):
                return self._current_page

        diagram = element_factory.create(Diagram)
        class1 = diagram.create(ClassItem, subject=element_factory.create(UML.Class))
        class2 = diagram.create(ClassItem, subject=element_factory.create(UML.Class))

        mock_diagrams = MockDiagrams()
        mock_diagrams._current_diagram = diagram
        mock_diagrams._current_page.view.selection._items = {class1, class2}

        service = CollapseExpandService(event_manager, mock_diagrams)

        yield service, class1, class2
        service.shutdown()

    def test_collapse_selected_collapses_items(self, service_with_items):
        """Test that collapse_selected collapses all selected items."""
        service, class1, class2 = service_with_items

        # Verify items are initially expanded
        assert class1.collapsed == 0
        assert class2.collapsed == 0

        service.collapse_selected()

        # Verify items are now collapsed
        assert class1.collapsed == 1
        assert class2.collapsed == 1

    def test_expand_selected_expands_items(self, service_with_items):
        """Test that expand_selected expands all selected items."""
        service, class1, class2 = service_with_items

        # First collapse the items
        class1.collapsed = 1
        class2.collapsed = 1

        service.expand_selected()

        # Verify items are now expanded
        assert class1.collapsed == 0
        assert class2.collapsed == 0

    def test_group_collapse_creates_group(self, service_with_items):
        """Test that group_collapse creates a collapse group."""
        service, class1, class2 = service_with_items

        # Verify items have no group initially
        assert class1.collapse_group == ""
        assert class2.collapse_group == ""

        service.group_collapse()

        # Verify items are now in the same group
        assert class1.collapse_group != ""
        assert class2.collapse_group != ""
        assert class1.collapse_group == class2.collapse_group

    def test_ungroup_collapse_removes_group(self, service_with_items):
        """Test that ungroup_collapse removes items from group."""
        service, class1, class2 = service_with_items

        # First create a group
        class1.collapse_group = "test-group"
        class2.collapse_group = "test-group"

        service.ungroup_collapse()

        # Verify items are no longer in a group
        assert class1.collapse_group == ""
        assert class2.collapse_group == ""

    def test_cluster_selected_clusters_items(self, service_with_items):
        """Test that cluster_selected collapses and groups items."""
        service, class1, class2 = service_with_items

        # Position items for clustering
        class1.matrix.translate(50, 50)
        class2.matrix.translate(250, 50)

        service.cluster_selected()

        # Verify items are collapsed
        assert class1.collapsed == 1
        assert class2.collapsed == 1

        # Verify items are in a group
        assert class1.collapse_group != ""
        assert class1.collapse_group == class2.collapse_group
        assert class1.collapse_group.startswith("collapse-group-")

    def test_uncluster_selected_unclusters_items(self, service_with_items):
        """Test that uncluster_selected expands and ungroups items."""
        service, class1, class2 = service_with_items

        # First cluster the items
        class1.collapsed = 1
        class2.collapsed = 1
        class1.collapse_group = "collapse-group-test123"
        class2.collapse_group = "collapse-group-test123"

        service.uncluster_selected()

        # Verify items are expanded
        assert class1.collapsed == 0
        assert class2.collapsed == 0

        # Verify items are no longer in auto-generated group
        assert class1.collapse_group == ""
        assert class2.collapse_group == ""

    def test_locked_items_are_skipped(self, service_with_items):
        """Test that locked items are skipped during collapse/expand."""
        service, class1, class2 = service_with_items

        # Lock class2
        class2.locked = 1

        # Collapse - class2 should not be collapsed
        service.collapse_selected()

        assert class1.collapsed == 1
        assert class2.collapsed == 0  # Locked item not collapsed

        # Expand - class2 should not be affected
        service.expand_selected()

        assert class1.collapsed == 0
        assert class2.collapsed == 0


class TestCollapseExpandServiceSingleItem:
    """Tests for single item scenarios."""

    @pytest.fixture
    def service_single_item(self, event_manager, element_factory):
        """Create a service with single item selected."""

        class MockView:
            class Selection:
                def __init__(self):
                    self._items = set()

                @property
                def selected_items(self):
                    return self._items

            def __init__(self):
                self.selection = self.Selection()

            def update_back_buffer(self):
                pass

            def queue_draw(self):
                pass

        class MockPage:
            def __init__(self):
                self.view = MockView()

        class MockDiagrams:
            def __init__(self):
                self._current_diagram = None
                self._current_page = MockPage()

            def get_current_diagram(self):
                return self._current_diagram

            def get_current_page(self):
                return self._current_page

        diagram = element_factory.create(Diagram)
        class1 = diagram.create(ClassItem, subject=element_factory.create(UML.Class))

        mock_diagrams = MockDiagrams()
        mock_diagrams._current_diagram = diagram
        mock_diagrams._current_page.view.selection._items = {class1}

        service = CollapseExpandService(event_manager, mock_diagrams)

        yield service, class1
        service.shutdown()

    def test_group_collapse_requires_multiple_items(self, service_single_item):
        """Test that group_collapse requires at least 2 items."""
        service, class1 = service_single_item

        # Should not create a group with only one item
        service.group_collapse()

        assert class1.collapse_group == ""

    def test_cluster_requires_multiple_items(self, service_single_item):
        """Test that cluster_selected requires at least 2 items."""
        service, class1 = service_single_item

        # Should not cluster with only one item
        service.cluster_selected()

        assert class1.collapsed == 0
        assert class1.collapse_group == ""
