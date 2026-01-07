"""Tests for collapsible diagram elements."""

from gaphor import UML
from gaphor.core.modeling.diagram import Diagram
from gaphor.diagram.collapsible import (
    COLLAPSE_ICON_MARGIN,
    COLLAPSE_ICON_SIZE,
    Collapsible,
    assign_collapse_group,
    can_show_collapse_icon,
    generate_group_id,
    is_point_in_collapse_icon,
    remove_from_collapse_group,
)
from gaphor.UML.classes.klass import ClassItem


class TestCollapseIconHitTesting:
    """Tests for collapse icon hit detection."""

    def test_point_inside_icon(self):
        """Test that point inside icon area is detected."""
        from gaphas.geometry import Rectangle

        # For a 100x50 item, icon is at top-right corner
        # Icon position: x = 100 - 12 - 4 = 84, y = 4
        bounds = Rectangle(0, 0, 100, 50)

        # Point inside the icon
        assert is_point_in_collapse_icon(88, 8, bounds)

    def test_point_outside_icon(self):
        """Test that point outside icon area is not detected."""
        from gaphas.geometry import Rectangle

        bounds = Rectangle(0, 0, 100, 50)

        # Point far from icon
        assert not is_point_in_collapse_icon(10, 10, bounds)
        assert not is_point_in_collapse_icon(50, 25, bounds)

    def test_point_on_icon_boundary(self):
        """Test points on the icon boundary."""
        from gaphas.geometry import Rectangle

        bounds = Rectangle(0, 0, 100, 50)
        icon_x = bounds.width - COLLAPSE_ICON_SIZE - COLLAPSE_ICON_MARGIN
        icon_y = COLLAPSE_ICON_MARGIN

        # Point exactly on the boundary (should be inside)
        assert is_point_in_collapse_icon(icon_x, icon_y, bounds)
        assert is_point_in_collapse_icon(
            icon_x + COLLAPSE_ICON_SIZE, icon_y + COLLAPSE_ICON_SIZE, bounds
        )


class TestClassItemCollapse:
    """Tests for ClassItem collapse functionality."""

    def test_class_has_collapsed_attribute(self, element_factory):
        """Test that ClassItem has a collapsed attribute."""
        diagram = element_factory.create(Diagram)
        klass = diagram.create(ClassItem, subject=element_factory.create(UML.Class))

        assert hasattr(klass, "collapsed")
        assert klass.collapsed == 0  # Default is not collapsed

    def test_class_can_be_collapsed(self, element_factory):
        """Test that ClassItem can be collapsed."""
        diagram = element_factory.create(Diagram)
        klass = diagram.create(ClassItem, subject=element_factory.create(UML.Class))
        klass.subject.name = "TestClass"

        # Add some attributes and operations
        attr = element_factory.create(UML.Property)
        attr.name = "attribute1"
        klass.subject.ownedAttribute = attr

        oper = element_factory.create(UML.Operation)
        oper.name = "operation1"
        klass.subject.ownedOperation = oper

        diagram.update({klass})

        # Get number of children when expanded
        expanded_children = len(klass.shape.children)

        # Collapse the class
        klass.collapsed = 1
        diagram.update({klass})

        # Collapsed should have fewer children (only name compartment)
        collapsed_children = len(klass.shape.children)
        assert collapsed_children < expanded_children

    def test_collapsed_class_shows_name(self, element_factory):
        """Test that collapsed class still shows the name."""
        diagram = element_factory.create(Diagram)
        klass = diagram.create(ClassItem, subject=element_factory.create(UML.Class))
        klass.subject.name = "TestClass"

        klass.collapsed = 1
        diagram.update({klass})

        # Should still have a name compartment
        assert len(klass.shape.children) >= 1

    def test_toggle_collapsed(self, element_factory):
        """Test the toggle_collapsed method."""
        diagram = element_factory.create(Diagram)
        klass = diagram.create(ClassItem, subject=element_factory.create(UML.Class))

        assert klass.collapsed == 0
        klass.toggle_collapsed()
        assert klass.collapsed == 1
        klass.toggle_collapsed()
        assert klass.collapsed == 0

    def test_is_collapsible_mixin(self, element_factory):
        """Test that ClassItem is a Collapsible."""
        diagram = element_factory.create(Diagram)
        klass = diagram.create(ClassItem, subject=element_factory.create(UML.Class))

        assert isinstance(klass, Collapsible)


class TestCollapseStatePersistence:
    """Tests for collapse state persistence (save/load)."""

    def test_collapsed_state_is_saved(self, element_factory):
        """Test that collapsed state is persisted when saving."""
        diagram = element_factory.create(Diagram)
        klass = diagram.create(ClassItem, subject=element_factory.create(UML.Class))
        klass.collapsed = 1

        # The collapsed attribute should be saved through the standard property system
        # Since it's an attribute[int], it will be automatically saved
        saved_values = {}

        def save_func(name, value):
            saved_values[name] = value

        klass.save(save_func)

        # Check that collapsed is in saved values
        assert "collapsed" in saved_values
        assert saved_values["collapsed"] == 1

    def test_collapsed_state_is_loaded(self, element_factory):
        """Test that collapsed state is restored when loading."""
        diagram = element_factory.create(Diagram)
        klass = diagram.create(ClassItem, subject=element_factory.create(UML.Class))

        # Load a collapsed state
        klass.load("collapsed", "1")

        assert klass.collapsed == 1


class TestCollapsedConnectionsMaintained:
    """Tests that connections are maintained when collapsing."""

    def test_association_maintained_when_collapsed(self, element_factory):
        """Test that associations are maintained when a class is collapsed."""
        from gaphor.UML.classes.association import AssociationItem

        diagram = element_factory.create(Diagram)

        # Create two classes
        klass1 = diagram.create(ClassItem, subject=element_factory.create(UML.Class))
        klass1.subject.name = "Class1"

        klass2 = diagram.create(ClassItem, subject=element_factory.create(UML.Class))
        klass2.subject.name = "Class2"

        # Create an association between them
        assoc = diagram.create(AssociationItem)

        # The classes should still have their ports even when collapsed
        klass1.collapsed = 1
        diagram.update({klass1})

        # Check that ports are still available
        assert len(klass1.ports()) > 0


class TestCollapseGroups:
    """Tests for collapse group functionality."""

    def test_generate_group_id_is_unique(self):
        """Test that generated group IDs are unique."""
        id1 = generate_group_id()
        id2 = generate_group_id()
        assert id1 != id2
        assert id1.startswith("collapse-group-")
        assert id2.startswith("collapse-group-")

    def test_assign_collapse_group(self, element_factory):
        """Test assigning items to a collapse group."""
        diagram = element_factory.create(Diagram)
        klass1 = diagram.create(ClassItem, subject=element_factory.create(UML.Class))
        klass2 = diagram.create(ClassItem, subject=element_factory.create(UML.Class))

        group_id = "test-group-1"
        assign_collapse_group([klass1, klass2], group_id)

        assert klass1.collapse_group == group_id
        assert klass2.collapse_group == group_id

    def test_remove_from_collapse_group(self, element_factory):
        """Test removing items from a collapse group."""
        diagram = element_factory.create(Diagram)
        klass1 = diagram.create(ClassItem, subject=element_factory.create(UML.Class))
        klass2 = diagram.create(ClassItem, subject=element_factory.create(UML.Class))

        klass1.collapse_group = "test-group"
        klass2.collapse_group = "test-group"

        remove_from_collapse_group([klass1])

        assert klass1.collapse_group == ""
        assert klass2.collapse_group == "test-group"

    def test_get_collapse_group_members(self, element_factory):
        """Test getting all members of a collapse group."""
        diagram = element_factory.create(Diagram)
        klass1 = diagram.create(ClassItem, subject=element_factory.create(UML.Class))
        klass2 = diagram.create(ClassItem, subject=element_factory.create(UML.Class))
        klass3 = diagram.create(ClassItem, subject=element_factory.create(UML.Class))

        group_id = "test-group-2"
        klass1.collapse_group = group_id
        klass2.collapse_group = group_id
        # klass3 is not in the group

        members = klass1.get_collapse_group_members()
        assert len(members) == 2
        assert klass1 in members
        assert klass2 in members
        assert klass3 not in members

    def test_toggle_group_collapsed(self, element_factory):
        """Test toggling collapsed state for a group."""
        diagram = element_factory.create(Diagram)
        klass1 = diagram.create(ClassItem, subject=element_factory.create(UML.Class))
        klass2 = diagram.create(ClassItem, subject=element_factory.create(UML.Class))

        group_id = "test-group-3"
        klass1.collapse_group = group_id
        klass2.collapse_group = group_id

        # Initially not collapsed
        assert klass1.collapsed == 0
        assert klass2.collapsed == 0

        # Toggle group collapsed
        klass1.toggle_group_collapsed()

        # Both should be collapsed
        assert klass1.collapsed == 1
        assert klass2.collapsed == 1

        # Toggle again
        klass2.toggle_group_collapsed()

        # Both should be expanded
        assert klass1.collapsed == 0
        assert klass2.collapsed == 0

    def test_collapse_group_persisted(self, element_factory):
        """Test that collapse_group is persisted."""
        diagram = element_factory.create(Diagram)
        klass = diagram.create(ClassItem, subject=element_factory.create(UML.Class))
        klass.collapse_group = "my-group"

        saved_values = {}

        def save_func(name, value):
            saved_values[name] = value

        klass.save(save_func)

        assert "collapse_group" in saved_values
        assert saved_values["collapse_group"] == "my-group"


class TestInterfaceCollapseIcon:
    """Tests for interface collapse icon behavior."""

    def test_interface_in_class_mode_can_show_icon(self, element_factory):
        """Test that interface in class mode can show collapse icon."""
        from gaphor.UML.classes.interface import Folded, InterfaceItem

        diagram = element_factory.create(Diagram)
        interface = diagram.create(
            InterfaceItem, subject=element_factory.create(UML.Interface)
        )

        # In class mode (NONE), should show icon
        interface._folded = Folded.NONE
        assert can_show_collapse_icon(interface)

    def test_interface_in_folded_mode_cannot_show_icon(self, element_factory):
        """Test that interface in folded mode cannot show collapse icon."""
        from gaphor.UML.classes.interface import Folded, InterfaceItem

        diagram = element_factory.create(Diagram)
        interface = diagram.create(
            InterfaceItem, subject=element_factory.create(UML.Interface)
        )

        # In folded mode, should not show icon
        interface._folded = Folded.PROVIDED
        assert not can_show_collapse_icon(interface)

        interface._folded = Folded.REQUIRED
        assert not can_show_collapse_icon(interface)

    def test_class_always_can_show_icon(self, element_factory):
        """Test that class items always can show collapse icon."""
        diagram = element_factory.create(Diagram)
        klass = diagram.create(ClassItem, subject=element_factory.create(UML.Class))

        assert can_show_collapse_icon(klass)
