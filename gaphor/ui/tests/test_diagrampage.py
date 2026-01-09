import os

import pytest
import pytest_asyncio
from gi.repository import Gdk

from gaphor import UML
from gaphor.core.modeling import Diagram
from gaphor.diagram.general import Box
from gaphor.ui.diagrampage import (
    DiagramPage,
    delete_selected_items,
    get_placement_cursor,
    placement_icon_base,
)
from gaphor.UML import Comment
from gaphor.UML.diagramitems import ClassItem, PackageItem
from gaphor.UML.general.comment import CommentItem


@pytest_asyncio.fixture
async def page(diagram, event_manager, element_factory, modeling_language):
    page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
    page.construct()
    assert page.diagram == diagram
    assert page.view.model == diagram
    yield page
    page.close()


def test_creation(page, element_factory):
    assert len(element_factory.lselect()) == 1
    assert len(element_factory.lselect(Diagram)) == 1


def test_placement(diagram, page, element_factory):
    box = diagram.create(Box)
    page.view.request_update([box])

    diagram.create(CommentItem, subject=element_factory.create(Comment))
    assert len(element_factory.lselect()) == 4


@pytest.mark.skipif(
    bool(os.environ.get("GDK_PIXBUF_MODULEDIR")),
    reason="Causes a SegFault when run from VSCode",
)
def test_placement_icon_base_is_loaded_once():
    icon1 = placement_icon_base()
    icon2 = placement_icon_base()

    assert icon1 is icon2


@pytest.mark.skipif(
    bool(os.environ.get("GDK_PIXBUF_MODULEDIR")),
    reason="Causes a SegFault when run from VSCode",
)
def test_placement_cursor():
    display = Gdk.Display.get_default()
    cursor = get_placement_cursor(display, "gaphor-box-symbolic")

    assert cursor


@pytest.mark.asyncio
async def test_delete_selected_items(create, diagram, view, event_manager):
    package_item = create(PackageItem, UML.Package)
    view.selection.select_items(package_item)
    await view.update()

    delete_selected_items(view, event_manager)

    assert not diagram.ownedPresentation


def test_delete_selected_owner(create, diagram, view, event_manager, sanitizer_service):
    class_item = create(ClassItem, UML.Class)
    diagram.element = class_item.subject
    view.selection.select_items(class_item)

    delete_selected_items(view, event_manager)

    assert not diagram.ownedPresentation
    assert diagram.element is None


@pytest.mark.asyncio
async def test_not_delete_selected_package_owner(
    create, diagram, view, event_manager, sanitizer_service
):
    package_item = create(PackageItem, UML.Package)
    package = package_item.subject
    diagram.element = package_item.subject
    view.selection.select_items(package_item)
    await view.update()

    delete_selected_items(view, event_manager)

    assert not diagram.ownedPresentation
    assert diagram.element is package


@pytest.mark.asyncio
async def test_add_association_between_classes(
    create, diagram, view, event_manager, element_factory, modeling_language
):
    """Test adding an association between two class items."""
    from gaphor.ui.diagrampage import DiagramPage
    from gaphor.UML.classes.association import AssociationItem

    # Create two class items
    class1 = create(ClassItem, UML.Class)
    class2 = create(ClassItem, UML.Class)

    # Position them apart
    class1.matrix.translate(50, 50)
    class2.matrix.translate(250, 50)

    # Select both classes
    view.selection.select_items(class1, class2)
    await view.update()

    # Create a DiagramPage and add association
    page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
    page.construct()
    page.view = view  # Use the test view

    page.add_association()

    # Check that an association was created
    associations = [
        item for item in diagram.get_all_items() if isinstance(item, AssociationItem)
    ]
    assert len(associations) == 1

    # Check that the association has a subject
    assoc = associations[0]
    assert assoc.subject is not None

    # Clean up the association to avoid teardown errors
    assoc.unlink()

    page.close()


@pytest.mark.asyncio
async def test_add_directed_association_between_classes(
    create, diagram, view, event_manager, element_factory, modeling_language
):
    """Test adding a directed association (with navigability) between two class items."""
    from gaphor.ui.diagrampage import DiagramPage
    from gaphor.UML.classes.association import AssociationItem

    # Create two class items
    class1 = create(ClassItem, UML.Class)
    class2 = create(ClassItem, UML.Class)

    # Position them apart
    class1.matrix.translate(50, 50)
    class2.matrix.translate(250, 50)

    # Select both classes
    view.selection.select_items(class1, class2)
    await view.update()

    # Create a DiagramPage and add directed association
    page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
    page.construct()
    page.view = view

    page.add_directed_association()

    # Check that an association was created
    associations = [
        item for item in diagram.get_all_items() if isinstance(item, AssociationItem)
    ]
    assert len(associations) == 1

    # Check that the association has a subject and navigability was applied
    assoc = associations[0]
    assert assoc.subject is not None
    # After connection, navigability is set on the tail_subject
    assert assoc.tail_subject is not None
    assert assoc.tail_subject.navigability is True

    # Clean up
    assoc.unlink()
    page.close()


@pytest.mark.asyncio
async def test_add_composite_association_between_classes(
    create, diagram, view, event_manager, element_factory, modeling_language
):
    """Test adding a composite association (filled diamond) between two class items."""
    from gaphor.ui.diagrampage import DiagramPage
    from gaphor.UML.classes.association import AssociationItem

    # Create two class items
    class1 = create(ClassItem, UML.Class)
    class2 = create(ClassItem, UML.Class)

    # Position them apart
    class1.matrix.translate(50, 50)
    class2.matrix.translate(250, 50)

    # Select both classes
    view.selection.select_items(class1, class2)
    await view.update()

    # Create a DiagramPage and add composite association
    page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
    page.construct()
    page.view = view

    page.add_composite_association()

    # Check that an association was created
    associations = [
        item for item in diagram.get_all_items() if isinstance(item, AssociationItem)
    ]
    assert len(associations) == 1

    # Check that the association has composite aggregation configured
    assoc = associations[0]
    assert assoc.subject is not None
    # After connection, aggregation is set on the tail_subject
    assert assoc.tail_subject is not None
    assert assoc.tail_subject.aggregation == "composite"

    # Clean up
    assoc.unlink()
    page.close()


@pytest.mark.asyncio
async def test_add_shared_association_between_classes(
    create, diagram, view, event_manager, element_factory, modeling_language
):
    """Test adding a shared association (open diamond) between two class items."""
    from gaphor.ui.diagrampage import DiagramPage
    from gaphor.UML.classes.association import AssociationItem

    # Create two class items
    class1 = create(ClassItem, UML.Class)
    class2 = create(ClassItem, UML.Class)

    # Position them apart
    class1.matrix.translate(50, 50)
    class2.matrix.translate(250, 50)

    # Select both classes
    view.selection.select_items(class1, class2)
    await view.update()

    # Create a DiagramPage and add shared association
    page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
    page.construct()
    page.view = view

    page.add_shared_association()

    # Check that an association was created
    associations = [
        item for item in diagram.get_all_items() if isinstance(item, AssociationItem)
    ]
    assert len(associations) == 1

    # Check that the association has shared aggregation configured
    assoc = associations[0]
    assert assoc.subject is not None
    # After connection, aggregation is set on the tail_subject
    assert assoc.tail_subject is not None
    assert assoc.tail_subject.aggregation == "shared"

    # Clean up
    assoc.unlink()
    page.close()


@pytest.mark.asyncio
async def test_remove_association_from_classes(
    create, diagram, view, event_manager, element_factory, modeling_language
):
    """Test removing associations connected to selected class items."""
    from gaphor.diagram.presentation import connect
    from gaphor.ui.diagrampage import DiagramPage
    from gaphor.UML.classes.association import AssociationItem

    # Create two class items
    class1 = create(ClassItem, UML.Class)
    class2 = create(ClassItem, UML.Class)

    # Position them apart
    class1.matrix.translate(50, 50)
    class2.matrix.translate(250, 50)

    # Create an association manually
    assoc = diagram.create(AssociationItem)
    assoc.handles()[0].pos = (100, 75)
    assoc.handles()[-1].pos = (250, 75)

    connect(assoc, assoc.head, class1)
    connect(assoc, assoc.tail, class2)

    await view.update()

    # Verify association exists
    associations = [
        item for item in diagram.get_all_items() if isinstance(item, AssociationItem)
    ]
    assert len(associations) == 1

    # Select one class
    view.selection.select_items(class1)
    await view.update()

    # Create a DiagramPage and remove association
    page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
    page.construct()
    page.view = view

    page.remove_association()

    # Check that the association was removed
    associations = [
        item for item in diagram.get_all_items() if isinstance(item, AssociationItem)
    ]
    assert len(associations) == 0

    page.close()


def test_popup_model_shows_association_options_for_multiple_classes(
    create, diagram, view, element_factory
):
    """Test that popup menu shows association options when multiple classes are selected."""
    from gaphor.ui.diagrampage import popup_model

    # Create two class items
    class1 = create(ClassItem, UML.Class)
    class2 = create(ClassItem, UML.Class)

    # Select both classes
    view.selection.select_items(class1, class2)

    # Get popup model
    menu = popup_model(diagram, class1, view.selection.selected_items)

    # Convert menu to string representation to check contents
    # The menu should contain Add Association and Remove Association
    assert menu is not None
    # Menu is a Gio.Menu, we check that it has sections (association options are in a section)

    assert (
        menu.get_n_items() >= 2
    )  # At least "Show in Model Browser" section + association section


def test_popup_model_shows_remove_association_for_single_class(
    create, diagram, view, element_factory
):
    """Test that popup menu shows only remove association option for single classified item."""
    from gaphor.ui.diagrampage import popup_model

    # Create one class item
    class1 = create(ClassItem, UML.Class)

    # Select the class
    view.selection.select_items(class1)

    # Get popup model
    menu = popup_model(diagram, class1, view.selection.selected_items)

    # The menu should exist and have sections
    assert menu is not None
    # Menu should have at least 2 sections now (Show in Model Browser + Remove Association)
    assert menu.get_n_items() >= 2


@pytest.mark.asyncio
async def test_add_directed_association_reverse_between_classes(
    create, diagram, view, event_manager, element_factory, modeling_language
):
    """Test adding a directed association with reversed direction between classes."""
    from gaphor.ui.diagrampage import DiagramPage
    from gaphor.UML.classes.association import AssociationItem

    # Create two class items
    class1 = create(ClassItem, UML.Class)
    class1.subject.name = "First"
    class2 = create(ClassItem, UML.Class)
    class2.subject.name = "Second"

    # Position them apart
    class1.matrix.translate(50, 50)
    class2.matrix.translate(250, 50)

    # Select both classes
    view.selection.select_items(class1, class2)
    await view.update()

    # Create a DiagramPage and add reversed directed association
    page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
    page.construct()
    page.view = view

    page.add_directed_association_reverse()

    # Check that an association was created
    associations = [
        item for item in diagram.get_all_items() if isinstance(item, AssociationItem)
    ]
    assert len(associations) == 1

    # Check that the association has navigability configured
    # The reverse action creates an association with swapped direction
    assoc = associations[0]
    assert assoc.subject is not None
    assert assoc.tail_subject is not None
    # The tail should have navigability set (this confirms the directed config was applied)
    assert assoc.tail_subject.navigability is True

    # Clean up
    assoc.unlink()
    page.close()


@pytest.mark.asyncio
async def test_add_composite_association_reverse_between_classes(
    create, diagram, view, event_manager, element_factory, modeling_language
):
    """Test adding a composite association with reversed direction between classes."""
    from gaphor.ui.diagrampage import DiagramPage
    from gaphor.UML.classes.association import AssociationItem

    # Create two class items
    class1 = create(ClassItem, UML.Class)
    class1.subject.name = "First"
    class2 = create(ClassItem, UML.Class)
    class2.subject.name = "Second"

    # Position them apart
    class1.matrix.translate(50, 50)
    class2.matrix.translate(250, 50)

    # Select both classes
    view.selection.select_items(class1, class2)
    await view.update()

    # Create a DiagramPage and add reversed composite association
    page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
    page.construct()
    page.view = view

    page.add_composite_association_reverse()

    # Check that an association was created
    associations = [
        item for item in diagram.get_all_items() if isinstance(item, AssociationItem)
    ]
    assert len(associations) == 1

    # Check the association has composite aggregation configured
    assoc = associations[0]
    assert assoc.subject is not None
    assert assoc.tail_subject is not None
    # The tail should have composite aggregation set
    assert assoc.tail_subject.aggregation == "composite"

    # Clean up
    assoc.unlink()
    page.close()


@pytest.mark.asyncio
async def test_add_shared_association_reverse_between_classes(
    create, diagram, view, event_manager, element_factory, modeling_language
):
    """Test adding a shared association with reversed direction between classes."""
    from gaphor.ui.diagrampage import DiagramPage
    from gaphor.UML.classes.association import AssociationItem

    # Create two class items
    class1 = create(ClassItem, UML.Class)
    class1.subject.name = "First"
    class2 = create(ClassItem, UML.Class)
    class2.subject.name = "Second"

    # Position them apart
    class1.matrix.translate(50, 50)
    class2.matrix.translate(250, 50)

    # Select both classes
    view.selection.select_items(class1, class2)
    await view.update()

    # Create a DiagramPage and add reversed shared association
    page = DiagramPage(diagram, event_manager, element_factory, modeling_language)
    page.construct()
    page.view = view

    page.add_shared_association_reverse()

    # Check that an association was created
    associations = [
        item for item in diagram.get_all_items() if isinstance(item, AssociationItem)
    ]
    assert len(associations) == 1

    # Check the association has shared aggregation configured
    assoc = associations[0]
    assert assoc.subject is not None
    assert assoc.tail_subject is not None
    # The tail should have shared aggregation set
    assert assoc.tail_subject.aggregation == "shared"

    # Clean up
    assoc.unlink()
    page.close()
