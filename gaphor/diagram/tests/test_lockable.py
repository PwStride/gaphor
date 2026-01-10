"""Tests for the lockable diagram element functionality."""

import pytest

from gaphor import UML
from gaphor.diagram.lockable import Lockable, is_item_locked
from gaphor.UML.classes.klass import ClassItem


class TestLockableMixin:
    """Test the Lockable mixin on ClassItem."""

    def test_class_has_locked_attribute(self, diagram):
        """Test that ClassItem has a locked attribute."""
        item = diagram.create(ClassItem)
        assert hasattr(item, "locked")
        assert item.locked == 0

    def test_is_lockable_mixin(self, diagram):
        """Test that ClassItem is an instance of Lockable."""
        item = diagram.create(ClassItem)
        assert isinstance(item, Lockable)

    def test_toggle_locked(self, diagram):
        """Test toggling the locked state."""
        item = diagram.create(ClassItem)
        assert item.locked == 0
        item.toggle_locked()
        assert item.locked == 1
        item.toggle_locked()
        assert item.locked == 0

    def test_lock_unlock(self, diagram):
        """Test explicit lock and unlock methods."""
        item = diagram.create(ClassItem)
        assert item.locked == 0
        item.lock()
        assert item.locked == 1
        item.unlock()
        assert item.locked == 0

    def test_is_locked_method(self, diagram):
        """Test the is_locked method."""
        item = diagram.create(ClassItem)
        assert not item.is_locked()
        item.locked = 1
        assert item.is_locked()


class TestIsItemLockedUtility:
    """Test the is_item_locked utility function."""

    def test_is_item_locked_returns_false_for_unlocked(self, diagram):
        """Test that is_item_locked returns False for unlocked items."""
        item = diagram.create(ClassItem)
        assert not is_item_locked(item)

    def test_is_item_locked_returns_true_for_locked(self, diagram):
        """Test that is_item_locked returns True for locked items."""
        item = diagram.create(ClassItem)
        item.locked = 1
        assert is_item_locked(item)

    def test_is_item_locked_with_non_lockable(self):
        """Test that is_item_locked returns False for objects without locked attribute."""

        class NonLockable:
            pass

        obj = NonLockable()
        assert not is_item_locked(obj)


class TestLockStatePersistence:
    """Test that locked state is properly saved and loaded."""

    def test_locked_state_is_saved(self, diagram, element_factory, saver):
        """Test that locked state is persisted."""
        item = diagram.create(ClassItem)
        item.subject = element_factory.create(UML.Class)
        item.locked = 1

        data = saver()
        assert "<locked>" in data
        assert "<val>1</val>" in data

    def test_locked_state_is_loaded(self, element_factory, loader):
        """Test that locked state is loaded correctly."""
        data = """<?xml version="1.0" encoding="utf-8"?>
<gaphor xmlns="http://gaphor.sourceforge.net/model" version="3.0" gaphor-version="2.12.0">
<StyleSheet id="58d6989a-66f8-11ec-b4c8-0456e5e540ed">
</StyleSheet>
<Diagram id="58d6c2b8-66f8-11ec-b4c8-0456e5e540ed">
<name>
<val><![CDATA[main]]></val>
</name>
</Diagram>
<Class id="1">
<name>
<val>MyClass</val>
</name>
</Class>
<ClassItem id="2">
<matrix>
<val>(1.0, 0.0, 0.0, 1.0, 100.0, 100.0)</val>
</matrix>
<top-left>
<val>(0.0, 0.0)</val>
</top-left>
<width>
<val>100</val>
</width>
<height>
<val>100</val>
</height>
<diagram>
<ref refid="58d6c2b8-66f8-11ec-b4c8-0456e5e540ed"/>
</diagram>
<subject>
<ref refid="1"/>
</subject>
<locked>
<val><![CDATA[1]]></val>
</locked>
</ClassItem>
</gaphor>"""

        loader(data)
        diagram = next(element_factory.select(UML.Diagram))
        item = next(diagram.select(ClassItem))
        assert item.locked == 1


class TestLockableLines:
    """Test that LinePresentation items are also lockable."""

    def test_line_has_locked_attribute(self, diagram, element_factory):
        """Test that line presentations have a locked attribute."""
        from gaphor.UML.classes.association import AssociationItem

        klass1 = diagram.create(ClassItem, subject=element_factory.create(UML.Class))
        klass2 = diagram.create(ClassItem, subject=element_factory.create(UML.Class))

        line = diagram.create(AssociationItem)
        assert hasattr(line, "locked")
        assert line.locked == 0

    def test_line_can_be_locked(self, diagram, element_factory):
        """Test that line presentations can be locked."""
        from gaphor.UML.classes.association import AssociationItem

        line = diagram.create(AssociationItem)
        assert not is_item_locked(line)
        line.locked = 1
        assert is_item_locked(line)
