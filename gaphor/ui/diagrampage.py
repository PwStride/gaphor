import functools
import importlib
import logging

from gaphas.guide import GuidePainter
from gaphas.painter import FreeHandPainter, HandlePainter, PainterChain
from gaphas.segment import LineSegmentPainter
from gaphas.tool.itemtool import default_find_item_and_handle_at_point
from gaphas.tool.rubberband import RubberbandPainter, RubberbandState
from gaphas.view import GtkView
from gi.repository import Adw, Gdk, GdkPixbuf, Gio, GLib, Gtk

from gaphor.action import action
from gaphor.core import event_handler, gettext
from gaphor.core.modeling import StyleSheet
from gaphor.core.modeling.diagram import StyledDiagram
from gaphor.core.modeling.event import (
    AttributeUpdated,
    StyleSheetUpdated,
)
from gaphor.core.styling import PrefersColorScheme
from gaphor.diagram.collapsible import (
    Collapsible,
    assign_collapse_group,
    cluster_items,
    generate_group_id,
    remove_from_collapse_group,
)
from gaphor.diagram.diagramtoolbox import get_tool_def, tooliter
from gaphor.diagram.event import DiagramSelectionChanged
from gaphor.diagram.lockable import Lockable, is_item_locked
from gaphor.diagram.painter import DiagramTypePainter, ItemPainter
from gaphor.diagram.presentation import Classified, connect
from gaphor.diagram.tools import (
    apply_default_tool_set,
    apply_magnet_tool_set,
    apply_placement_tool_set,
)
from gaphor.diagram.tools.magnet import MagnetPainter
from gaphor.i18n import translated_ui_string
from gaphor.transaction import Transaction
from gaphor.ui.actiongroup import apply_action_group
from gaphor.ui.clipboard import Clipboard
from gaphor.ui.event import ToolSelected

log = logging.getLogger(__name__)


@functools.lru_cache(maxsize=1)
def placement_icon_base():
    f = importlib.resources.files("gaphor") / "ui" / "placement-icon-base.png"
    return GdkPixbuf.Pixbuf.new_from_file_at_scale(str(f), 64, 64, True)


if hasattr(GtkView, "set_css_name"):
    GtkView.set_css_name("diagramview")


def new_builder():
    builder = Gtk.Builder()
    builder.add_from_string(translated_ui_string("gaphor.ui", "diagrampage.ui"))
    return builder


@functools.cache
def get_placement_icon(display, icon_name):
    if display is None:
        display = Gdk.Display.get_default()
    pixbuf = placement_icon_base().copy()
    theme_icon = Gtk.IconTheme.get_for_display(display).lookup_icon(
        icon_name,
        None,
        24,
        1,
        Gtk.TextDirection.NONE,
        Gtk.IconLookupFlags.FORCE_SYMBOLIC,
    )
    icon = GdkPixbuf.Pixbuf.new_from_file_at_scale(
        theme_icon.get_file().get_path(), 32, 32, True
    )
    icon.copy_area(
        0,
        0,
        icon.get_width(),
        icon.get_height(),
        pixbuf,
        9,
        15,
    )
    return Gdk.Texture.new_for_pixbuf(pixbuf)


def get_placement_cursor(display, icon_name):
    return Gdk.Cursor.new_from_texture(get_placement_icon(display, icon_name), 1, 1)


class DiagramPage:
    def __init__(self, diagram, event_manager, element_factory, modeling_language):
        self.event_manager = event_manager
        self.element_factory = element_factory
        self.diagram = diagram
        self.modeling_language = modeling_language
        self.clipboard = Clipboard(event_manager, element_factory)
        self.style_manager = Adw.StyleManager.get_default()

        self.view: GtkView | None = None
        self.alignment_button: Gtk.Button | None = None
        self.diagram_css: Gtk.CssProvider | None = None

        self.rubberband_state = RubberbandState()
        self.context_menu = Gtk.PopoverMenu.new_from_model(popup_model(diagram))

        self.event_manager.subscribe(self._on_attribute_updated)
        self.event_manager.subscribe(self._on_style_sheet_updated)
        self.event_manager.subscribe(self._on_tool_selected)

    @property
    def title(self):
        return self.diagram and self.diagram.name or gettext("<None>")

    def get_diagram(self):
        return self.diagram

    def get_view(self):
        return self.view

    def construct(self):
        """Create the widget.

        Returns: the newly created widget.
        """
        assert self.diagram

        builder = new_builder()
        view: GtkView = builder.get_object("view")
        view.add_css_class(self._css_class())
        view.connect("delete", delete_selected_items, self.event_manager)
        view.connect("cut-clipboard", self.clipboard.cut)
        view.connect("copy-clipboard", self.clipboard.copy)
        view.connect("paste-clipboard", self.clipboard.paste_link)
        view.connect("paste-full-clipboard", self.clipboard.paste_full)
        view.selection.add_handler(self._selection_changed)
        self.clipboard.clipboard.connect(
            "notify::content", self._clipboard_content_changed
        )

        self.diagram_css = Gtk.CssProvider.new()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            self.diagram_css,
            Gtk.STYLE_PROVIDER_PRIORITY_USER,
        )

        self.style_manager.connect("notify::dark", self._on_notify_dark)

        view.model = self.diagram
        self.view = view
        self.context_menu.set_parent(view)

        self.select_tool("toolbox-pointer")

        self._on_notify_dark(self.style_manager)
        self.update_drawing_style()

        diagrampage = builder.get_object("diagrampage")
        apply_action_group(self, "diagram", diagrampage)
        self._clipboard_content_changed(self.clipboard.clipboard)

        self.alignment_button = builder.get_object("alignment-button")

        return diagrampage

    def apply_tool_set(self, tool_name):
        """Return a tool associated with an id (action name).

        Tool sets can't be changed if a transaction is active,
        because it could ruin the user (inter)action.
        """

        if Transaction.in_transaction():
            log.warning("Cannot change tool set while in a transaction.")
            return False

        if tool_name == "toolbox-pointer":
            apply_default_tool_set(
                self.view,
                self.modeling_language,
                self.event_manager,
                self.rubberband_state,
            )
            if self.view:
                self.view.add_controller(
                    context_menu_controller(self.context_menu, self.diagram)
                )

        elif tool_name == "toolbox-magnet":
            apply_magnet_tool_set(
                self.view,
                self.modeling_language,
                self.event_manager,
            )
        else:
            tool_def = get_tool_def(self.modeling_language, tool_name)
            item_factory = tool_def.item_factory
            handle_index = tool_def.handle_index
            apply_placement_tool_set(
                self.view,
                item_factory=item_factory,
                modeling_language=self.modeling_language,
                event_manager=self.event_manager,
                handle_index=handle_index,
            )
        return True

    def get_tool_icon_name(self, tool_name):
        if tool_name == "toolbox-pointer":
            return None
        return next(
            t
            for t in tooliter(self.modeling_language.toolbox_definition)
            if t.id == tool_name
        ).icon_name

    def _css_class(self):
        return f"diagram-{id(self)}"

    def _selection_changed(self, _item):
        view = self.view
        assert view
        selection = view.selection
        self.event_manager.handle(
            DiagramSelectionChanged(
                view, selection.focused_item, selection.selected_items
            )
        )

    @event_handler(ToolSelected)
    def _on_tool_selected(self, event: ToolSelected):
        self.select_tool(event.tool_name)

    @event_handler(AttributeUpdated)
    def _on_attribute_updated(self, event: AttributeUpdated):
        if event.property.name == "name" and self.view:
            self.view.update_back_buffer()

    @event_handler(StyleSheetUpdated)
    def _on_style_sheet_updated(self, _event):
        self.update_drawing_style()
        self.diagram.update(self.diagram.ownedPresentation)

    def _clipboard_content_changed(self, clipboard, _pspec=None):
        if not self.view:
            return

        enabled = self.clipboard.can_paste()
        self.view.action_set_enabled("clipboard.paste", enabled)
        self.view.action_set_enabled("clipboard.paste-full", enabled)

    def _on_notify_dark(self, style_manager, _gparam=None):
        self.update_drawing_style()

    def close(self):
        """Tab is destroyed.

        Do the same thing that would be done if Close was pressed.
        """
        assert self.view

        Gtk.StyleContext.remove_provider_for_display(
            Gdk.Display.get_default(),
            self.diagram_css,
        )

        self.event_manager.unsubscribe(self._on_attribute_updated)
        self.event_manager.unsubscribe(self._on_style_sheet_updated)
        self.event_manager.unsubscribe(self._on_tool_selected)
        self.view = None

    def select_tool(self, tool_name: str):
        if not self.view:
            return

        if self.apply_tool_set(tool_name):
            if icon_name := self.get_tool_icon_name(tool_name):
                self.view.set_cursor(get_placement_cursor(None, icon_name))
            else:
                self.view.set_cursor(None)

    def update_drawing_style(self):
        """Set the drawing style for the diagram based on the active style
        sheet."""
        assert self.view
        assert self.diagram_css

        prefers_color_scheme = (
            PrefersColorScheme.DARK
            if self.style_manager.get_dark()
            else PrefersColorScheme.LIGHT
        )

        view = self.view
        style_sheet = self.element_factory.style_sheet or StyleSheet()
        item_painter = ItemPainter(
            view.selection,
            functools.partial(
                style_sheet.compute_style, prefers_color_scheme=prefers_color_scheme
            ),
        )

        style = style_sheet.compute_style(
            StyledDiagram(self.diagram), prefers_color_scheme
        )
        bg = style.get("background-color", (0.0, 0.0, 0.0, 0.0))
        self.diagram_css.load_from_string(
            f".{self._css_class()} {{ background-color: rgba({int(255 * bg[0])}, {int(255 * bg[1])}, {int(255 * bg[2])}, {bg[3]}); }}",
        )

        if sloppiness := style.get("line-style", 0.0):
            item_painter = FreeHandPainter(item_painter, sloppiness=sloppiness)

        view.bounding_box_painter = item_painter
        view.painter = (
            PainterChain()
            .append(item_painter)
            .append(HandlePainter(view))
            .append(LineSegmentPainter(view.selection))
            .append(GuidePainter(view))
            .append(MagnetPainter(view))
            .append(RubberbandPainter(self.rubberband_state))
            .append(
                DiagramTypePainter(
                    self.diagram,
                    functools.partial(
                        style_sheet.compute_style,
                        prefers_color_scheme=prefers_color_scheme,
                    ),
                )
            )
        )

        view.request_update(self.diagram.get_all_items())

    @action(name="diagram.collapse-item")
    def collapse_item(self, item_id: str):
        """Collapse a diagram item."""
        item = self.element_factory.lookup(item_id)
        if item and isinstance(item, Collapsible):
            with Transaction(self.event_manager):
                # If item has a collapse group, collapse all group members
                if item.collapse_group:
                    for member in item.get_collapse_group_members():
                        member.collapsed = 1
                else:
                    item.collapsed = 1

    @action(name="diagram.expand-item")
    def expand_item(self, item_id: str):
        """Expand a diagram item."""
        item = self.element_factory.lookup(item_id)
        if item and isinstance(item, Collapsible):
            with Transaction(self.event_manager):
                # If item has a collapse group, expand all group members
                if item.collapse_group:
                    for member in item.get_collapse_group_members():
                        member.collapsed = 0
                else:
                    item.collapsed = 0

    @action(name="diagram.collapse-selected")
    def collapse_selected(self):
        """Collapse all selected items."""
        if not self.view:
            return
        with Transaction(self.event_manager):
            for item in self.view.selection.selected_items:
                if isinstance(item, Collapsible):
                    item.collapsed = 1

    @action(name="diagram.expand-selected")
    def expand_selected(self):
        """Expand all selected items."""
        if not self.view:
            return
        with Transaction(self.event_manager):
            for item in self.view.selection.selected_items:
                if isinstance(item, Collapsible):
                    item.collapsed = 0

    @action(name="diagram.group-collapse")
    def group_collapse(self):
        """Create a collapse group from selected items."""
        if not self.view:
            return
        collapsible_items = [
            item
            for item in self.view.selection.selected_items
            if isinstance(item, Collapsible)
        ]
        if len(collapsible_items) >= 2:
            with Transaction(self.event_manager):
                group_id = generate_group_id()
                assign_collapse_group(collapsible_items, group_id)

    @action(name="diagram.ungroup-collapse")
    def ungroup_collapse(self):
        """Remove selected items from their collapse groups."""
        if not self.view:
            return
        collapsible_items = [
            item
            for item in self.view.selection.selected_items
            if isinstance(item, Collapsible)
        ]
        if collapsible_items:
            with Transaction(self.event_manager):
                remove_from_collapse_group(collapsible_items)

    @action(name="diagram.cluster-selected")
    def cluster_selected(self):
        """Cluster selected items: collapse and pack tightly together.

        This operation:
        1. Collapses all selected collapsible items to their minimum size
        2. Removes extra space between items
        3. Arranges items in a compact grid layout
        4. Reduces rendering overhead by minimizing the diagram area
        """
        if not self.view:
            return
        collapsible_items = [
            item
            for item in self.view.selection.selected_items
            if isinstance(item, Collapsible)
        ]
        if len(collapsible_items) >= 2:
            with Transaction(self.event_manager):
                cluster_items(collapsible_items)
            # Post-transaction cleanup: ensure view state is reset
            self.view.update_back_buffer()

    @action(name="diagram.lock-item")
    def lock_item(self, item_id: str):
        """Lock a diagram item."""
        item = self.element_factory.lookup(item_id)
        if item and isinstance(item, Lockable):
            with Transaction(self.event_manager):
                item.locked = 1

    @action(name="diagram.unlock-item")
    def unlock_item(self, item_id: str):
        """Unlock a diagram item."""
        item = self.element_factory.lookup(item_id)
        if item and isinstance(item, Lockable):
            with Transaction(self.event_manager):
                item.locked = 0

    @action(name="diagram.lock-selected")
    def lock_selected(self):
        """Lock all selected items."""
        if not self.view:
            return
        with Transaction(self.event_manager):
            for item in self.view.selection.selected_items:
                if isinstance(item, Lockable):
                    item.locked = 1

    @action(name="diagram.unlock-selected")
    def unlock_selected(self):
        """Unlock all selected items."""
        if not self.view:
            return
        with Transaction(self.event_manager):
            for item in self.view.selection.selected_items:
                if isinstance(item, Lockable):
                    item.locked = 0

    def _create_association_between_items(self, head_item, tail_item, config_func=None):
        """Helper method to create an association between two items."""
        from gaphor.UML.classes.association import AssociationItem

        # Create the association item on the diagram
        assoc = self.diagram.create(AssociationItem)

        # Apply configuration function if provided (for different association types)
        if config_func:
            config_func(assoc)

        # Position the association line between the two items
        head_pos = (
            head_item.matrix[4] + head_item.width / 2,
            head_item.matrix[5] + head_item.height / 2,
        )
        tail_pos = (
            tail_item.matrix[4] + tail_item.width / 2,
            tail_item.matrix[5] + tail_item.height / 2,
        )

        assoc.handles()[0].pos = head_pos
        assoc.handles()[-1].pos = tail_pos

        # Connect the association ends to the items
        connect(assoc, assoc.head, head_item)
        connect(assoc, assoc.tail, tail_item)

        return assoc

    @action(name="diagram.add-association")
    def add_association(self):
        """Add basic associations between all selected classifier items."""
        self._add_association_with_type(None)

    @action(name="diagram.add-directed-association")
    def add_directed_association(self):
        """Add directed associations (arrow pointing to second item) between selected items."""
        from gaphor.UML.classes.classestoolbox import direct_association_config

        self._add_association_with_type(direct_association_config)

    @action(name="diagram.add-directed-association-reverse")
    def add_directed_association_reverse(self):
        """Add directed associations (arrow pointing to first item) between selected items."""
        from gaphor.UML.classes.classestoolbox import direct_association_config

        self._add_association_with_type(direct_association_config, reverse=True)

    @action(name="diagram.add-shared-association")
    def add_shared_association(self):
        """Add shared associations (diamond at second item) between selected items."""
        from gaphor.UML.classes.classestoolbox import shared_association_config

        self._add_association_with_type(shared_association_config)

    @action(name="diagram.add-shared-association-reverse")
    def add_shared_association_reverse(self):
        """Add shared associations (diamond at first item) between selected items."""
        from gaphor.UML.classes.classestoolbox import shared_association_config

        self._add_association_with_type(shared_association_config, reverse=True)

    @action(name="diagram.add-composite-association")
    def add_composite_association(self):
        """Add composite associations (diamond at second item) between selected items."""
        from gaphor.UML.classes.classestoolbox import composite_association_config

        self._add_association_with_type(composite_association_config)

    @action(name="diagram.add-composite-association-reverse")
    def add_composite_association_reverse(self):
        """Add composite associations (diamond at first item) between selected items."""
        from gaphor.UML.classes.classestoolbox import composite_association_config

        self._add_association_with_type(composite_association_config, reverse=True)

    def _add_association_with_type(self, config_func, reverse=False):
        """Add associations of a specific type between all selected classifier items.

        Args:
            config_func: Configuration function for the association type
            reverse: If True, swap head and tail to reverse the direction
        """
        if not self.view:
            return

        # Get all selected items that are Classified (can have associations)
        classified_items = [
            item
            for item in self.view.selection.selected_items
            if isinstance(item, Classified) and item.subject
        ]

        if len(classified_items) < 2:
            return

        with Transaction(self.event_manager):
            # Create associations between consecutive pairs of items
            for i in range(len(classified_items) - 1):
                if reverse:
                    # Swap head and tail to reverse direction
                    head_item = classified_items[i + 1]
                    tail_item = classified_items[i]
                else:
                    head_item = classified_items[i]
                    tail_item = classified_items[i + 1]

                self._create_association_between_items(
                    head_item, tail_item, config_func
                )

    @action(name="diagram.remove-association")
    def remove_association(self):
        """Remove all association arrows connected to selected items."""
        if not self.view:
            return

        from gaphor.UML.classes.association import AssociationItem

        # Get all selected items that are Classified
        classified_items = [
            item
            for item in self.view.selection.selected_items
            if isinstance(item, Classified)
        ]

        if not classified_items:
            return

        # Find all associations connected to selected items
        associations_to_remove = set()
        for item in self.diagram.get_all_items():
            if isinstance(item, AssociationItem):
                # Check if either end of the association is connected to a selected item
                head_conn = self.diagram.connections.get_connection(item.head)
                tail_conn = self.diagram.connections.get_connection(item.tail)

                head_connected = head_conn and head_conn.connected in classified_items
                tail_connected = tail_conn and tail_conn.connected in classified_items

                if head_connected or tail_connected:
                    associations_to_remove.add(item)

        if associations_to_remove:
            with Transaction(self.event_manager):
                for assoc in associations_to_remove:
                    assoc.unlink()


def delete_selected_items(view: GtkView, event_manager):
    with Transaction(event_manager):
        items = view.selection.selected_items
        for i in list(items):
            i.unlink()


def context_menu_controller(context_menu, diagram):
    def on_show_popup(ctrl, n_press, x, y):
        if (
            Transaction.in_transaction()
            or ctrl.get_last_event() is None
            or not ctrl.get_last_event().triggers_context_menu()
        ):
            return

        view = ctrl.get_widget()
        item, _handle = default_find_item_and_handle_at_point(view, (x, y))

        context_menu.set_menu_model(
            popup_model(
                item.subject if item and item.subject else diagram,
                item,
                view.selection.selected_items,
            )
        )

        gdk_rect = Gdk.Rectangle()
        gdk_rect.x = x
        gdk_rect.y = y
        gdk_rect.width = gdk_rect.height = 1

        context_menu.set_has_arrow(False)
        context_menu.set_pointing_to(gdk_rect)
        context_menu.popup()

    ctrl = Gtk.GestureClick.new()
    ctrl.set_button(0)
    ctrl.connect("pressed", on_show_popup)
    return ctrl


def popup_model(element, item=None, selected_items=None):
    model = Gio.Menu.new()
    part = Gio.Menu.new()

    menu_item = Gio.MenuItem.new(
        gettext("Show in Model Browser"),
        "win.show-in-model-browser",
    )
    menu_item.set_attribute_value("target", GLib.Variant.new_string(element.id))

    part.append_item(menu_item)
    model.append_section(None, part)

    # Add association options when classified items are selected
    if selected_items:
        classified_selected = [
            i for i in selected_items if isinstance(i, Classified) and i.subject
        ]

        if len(classified_selected) >= 2:
            assoc_part = Gio.Menu.new()

            # Create submenu for different association types
            add_assoc_submenu = Gio.Menu.new()

            # Basic Association (no direction)
            add_basic = Gio.MenuItem.new(
                gettext("Association"),
                "diagram.add-association",
            )
            add_assoc_submenu.append_item(add_basic)

            # Directed Association submenu with direction options
            directed_submenu = Gio.Menu.new()
            add_directed_forward = Gio.MenuItem.new(
                gettext("First → Second"),
                "diagram.add-directed-association",
            )
            directed_submenu.append_item(add_directed_forward)
            add_directed_reverse = Gio.MenuItem.new(
                gettext("Second → First"),
                "diagram.add-directed-association-reverse",
            )
            directed_submenu.append_item(add_directed_reverse)
            directed_item = Gio.MenuItem.new_submenu(
                gettext("Directed Association"),
                directed_submenu,
            )
            add_assoc_submenu.append_item(directed_item)

            # Shared Association submenu with direction options
            shared_submenu = Gio.Menu.new()
            add_shared_forward = Gio.MenuItem.new(
                gettext("◇ at Second"),
                "diagram.add-shared-association",
            )
            shared_submenu.append_item(add_shared_forward)
            add_shared_reverse = Gio.MenuItem.new(
                gettext("◇ at First"),
                "diagram.add-shared-association-reverse",
            )
            shared_submenu.append_item(add_shared_reverse)
            shared_item = Gio.MenuItem.new_submenu(
                gettext("Shared Association"),
                shared_submenu,
            )
            add_assoc_submenu.append_item(shared_item)

            # Composite Association submenu with direction options
            composite_submenu = Gio.Menu.new()
            add_composite_forward = Gio.MenuItem.new(
                gettext("◆ at Second"),
                "diagram.add-composite-association",
            )
            composite_submenu.append_item(add_composite_forward)
            add_composite_reverse = Gio.MenuItem.new(
                gettext("◆ at First"),
                "diagram.add-composite-association-reverse",
            )
            composite_submenu.append_item(add_composite_reverse)
            composite_item = Gio.MenuItem.new_submenu(
                gettext("Composite Association"),
                composite_submenu,
            )
            add_assoc_submenu.append_item(composite_item)

            # Add the submenu as "Add Association" with arrow
            add_assoc_item = Gio.MenuItem.new_submenu(
                gettext("Add Association"),
                add_assoc_submenu,
            )
            assoc_part.append_item(add_assoc_item)

            # Option to remove associations
            remove_assoc = Gio.MenuItem.new(
                gettext("Remove Association"),
                "diagram.remove-association",
            )
            assoc_part.append_item(remove_assoc)

            model.append_section(None, assoc_part)
        elif len(classified_selected) == 1:
            # Show only remove association when single item is selected
            assoc_part = Gio.Menu.new()
            remove_assoc = Gio.MenuItem.new(
                gettext("Remove Association"),
                "diagram.remove-association",
            )
            assoc_part.append_item(remove_assoc)
            model.append_section(None, assoc_part)

    # Add collapse/expand option for collapsible items
    if item is not None and isinstance(item, Collapsible):
        # Don't show collapse/expand if item is locked
        if not is_item_locked(item):
            collapse_part = Gio.Menu.new()
            if item.collapsed:
                collapse_item = Gio.MenuItem.new(
                    gettext("Expand"),
                    "diagram.expand-item",
                )
            else:
                collapse_item = Gio.MenuItem.new(
                    gettext("Collapse"),
                    "diagram.collapse-item",
                )
            collapse_item.set_attribute_value(
                "target", GLib.Variant.new_string(item.id)
            )
            collapse_part.append_item(collapse_item)
            model.append_section(None, collapse_part)

    # Add lock/unlock option for lockable items
    if item is not None and isinstance(item, Lockable):
        lock_part = Gio.Menu.new()
        if item.locked:
            lock_item = Gio.MenuItem.new(
                gettext("Unlock"),
                "diagram.unlock-item",
            )
        else:
            lock_item = Gio.MenuItem.new(
                gettext("Lock"),
                "diagram.lock-item",
            )
        lock_item.set_attribute_value("target", GLib.Variant.new_string(item.id))
        lock_part.append_item(lock_item)
        model.append_section(None, lock_part)

    # Add group collapse options when multiple items are selected
    if selected_items:
        collapsible_selected = [i for i in selected_items if isinstance(i, Collapsible)]

        if len(collapsible_selected) >= 2:
            group_part = Gio.Menu.new()

            # Option to collapse all selected
            collapse_all = Gio.MenuItem.new(
                gettext("Collapse Selected"),
                "diagram.collapse-selected",
            )
            group_part.append_item(collapse_all)

            # Option to expand all selected
            expand_all = Gio.MenuItem.new(
                gettext("Expand Selected"),
                "diagram.expand-selected",
            )
            group_part.append_item(expand_all)

            # Option to create a collapse group
            create_group = Gio.MenuItem.new(
                gettext("Create Collapse Group"),
                "diagram.group-collapse",
            )
            group_part.append_item(create_group)

            # Option to cluster selected items (collapse and pack tightly)
            cluster_selected = Gio.MenuItem.new(
                gettext("Cluster Selected"),
                "diagram.cluster-selected",
            )
            group_part.append_item(cluster_selected)

            # Check if any selected items are in a group
            any_in_group = any(i.collapse_group for i in collapsible_selected)
            if any_in_group:
                ungroup = Gio.MenuItem.new(
                    gettext("Remove from Collapse Group"),
                    "diagram.ungroup-collapse",
                )
                group_part.append_item(ungroup)

            model.append_section(None, group_part)

    # Add lock/unlock options when multiple items are selected
    if selected_items:
        lockable_selected = [i for i in selected_items if isinstance(i, Lockable)]

        if len(lockable_selected) >= 2:
            lock_group_part = Gio.Menu.new()

            # Option to lock all selected
            lock_all = Gio.MenuItem.new(
                gettext("Lock Selected"),
                "diagram.lock-selected",
            )
            lock_group_part.append_item(lock_all)

            # Option to unlock all selected
            unlock_all = Gio.MenuItem.new(
                gettext("Unlock Selected"),
                "diagram.unlock-selected",
            )
            lock_group_part.append_item(unlock_all)

            model.append_section(None, lock_group_part)

    return model
