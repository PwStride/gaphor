import logging

from gaphor import UML
from gaphor.core.format import format
from gaphor.core.modeling.properties import attribute
from gaphor.diagram.presentation import (
    Classified,
    ElementPresentation,
)
from gaphor.diagram.shapes import Box, CssNode, Text, draw_border, draw_top_separator
from gaphor.diagram.support import represents
from gaphor.UML.classes.stereotype import stereotype_compartments, stereotype_watches
from gaphor.UML.compartments import name_compartment

log = logging.getLogger(__name__)


def _draw_icon_only_box(box, context, bounding_box):
    """Draw an icon-only box with a triangle indicator for clustered state."""
    cr = context.cairo
    style = context.style

    stroke_color = style.get("color", (0, 0, 0, 1))
    fill_color = style.get("background-color", (1, 1, 1, 1))

    # Fill and draw border
    cr.set_source_rgba(*fill_color)
    cr.rectangle(bounding_box.x, bounding_box.y, bounding_box.width, bounding_box.height)
    cr.fill()

    cr.set_source_rgba(*stroke_color)
    cr.set_line_width(1.0)
    cr.rectangle(bounding_box.x, bounding_box.y, bounding_box.width, bounding_box.height)
    cr.stroke()

    # Draw centered right-pointing triangle
    icon_size = 12
    cx = bounding_box.x + bounding_box.width / 2
    cy = bounding_box.y + bounding_box.height / 2

    cr.set_line_width(1.5)
    cr.move_to(cx - icon_size / 3, cy - icon_size / 2)
    cr.line_to(cx + icon_size / 2, cy)
    cr.line_to(cx - icon_size / 3, cy + icon_size / 2)
    cr.close_path()
    cr.fill()


@represents(UML.Class)
@represents(UML.Stereotype)
class ClassItem(Classified, ElementPresentation[UML.Class]):
    """This item visualizes a Class instance.

    A ClassItem contains two compartments: one for attributes and one
    for operations. The item can be collapsed to show only the name
    compartment, or expanded to show all compartments.
    """

    def __init__(self, diagram, id=None):
        super().__init__(diagram, id=id)
        self.watch("show_stereotypes", self.update_shapes).watch(
            "show_attributes", self.update_shapes
        ).watch("show_operations", self.update_shapes).watch(
            "collapsed", self.update_shapes
        ).watch("subject[NamedElement].name").watch(
            "subject[NamedElement].namespace.name"
        ).watch("subject[Classifier].isAbstract", self.update_shapes)
        attribute_watches(self, "Class")
        operation_watches(self, "Class")
        stereotype_watches(self)

    show_stereotypes: attribute[int] = attribute("show_stereotypes", int)

    show_attributes: attribute[int] = attribute("show_attributes", int, default=True)

    show_operations: attribute[int] = attribute("show_operations", int, default=True)

    # Collapse state: 0=expanded, 1=collapsed (name only), 2=icon-only (clustered)
    collapsed: attribute[int] = attribute("collapsed", int, default=0)

    # Group ID for coordinated collapse/expand with other items
    collapse_group: attribute[str] = attribute("collapse_group", str, default="")

    def additional_stereotypes(self):
        if isinstance(self.subject, UML.Stereotype):
            return [self.diagram.gettext("stereotype")]
        elif UML.recipes.is_metaclass(self.subject):
            return [self.diagram.gettext("metaclass")]
        return ()

    def update_shapes(self, event=None):
        if self.collapsed == 2:
            # Icon-only view for auto layout clustered state
            self.shape = Box(draw=_draw_icon_only_box)
        elif self.collapsed:
            # Collapsed view: show only name compartment
            self.shape = Box(
                name_compartment(self, self.additional_stereotypes),
                draw=draw_border,
            )
        else:
            # Expanded view: show all compartments
            self.shape = Box(
                name_compartment(self, self.additional_stereotypes),
                *(
                    self.show_attributes
                    and self.subject
                    and [attributes_compartment(self.subject)]
                    or []
                ),
                *(
                    self.show_operations
                    and self.subject
                    and [operations_compartment(self.subject)]
                    or []
                ),
                *(
                    self.show_stereotypes
                    and stereotype_compartments(self.subject)
                    or []
                ),
                draw=draw_border,
            )


def attribute_watches(presentation, cast):
    presentation.watch(
        f"subject[{cast}].ownedAttribute", presentation.update_shapes
    ).watch(
        f"subject[{cast}].ownedAttribute.association", presentation.update_shapes
    ).watch(f"subject[{cast}].ownedAttribute.name").watch(
        f"subject[{cast}].ownedAttribute.isStatic", presentation.update_shapes
    ).watch(
        f"subject[{cast}].ownedAttribute.isReadOnly", presentation.update_shapes
    ).watch(f"subject[{cast}].ownedAttribute.isDerived").watch(
        f"subject[{cast}].ownedAttribute.visibility"
    ).watch(f"subject[{cast}].ownedAttribute.lowerValue").watch(
        f"subject[{cast}].ownedAttribute.upperValue"
    ).watch(f"subject[{cast}].ownedAttribute.defaultValue").watch(
        f"subject[{cast}].ownedAttribute.type"
    ).watch(f"subject[{cast}].ownedAttribute.type.name").watch(
        f"subject[{cast}].ownedAttribute.typeValue"
    )


def operation_watches(presentation, cast):
    presentation.watch(
        f"subject[{cast}].ownedOperation", presentation.update_shapes
    ).watch(f"subject[{cast}].ownedOperation.name").watch(
        f"subject[{cast}].ownedOperation.isAbstract", presentation.update_shapes
    ).watch(
        f"subject[{cast}].ownedOperation.isStatic", presentation.update_shapes
    ).watch(f"subject[{cast}].ownedOperation.visibility").watch(
        f"subject[{cast}].ownedOperation.ownedParameter.lowerValue"
    ).watch(f"subject[{cast}].ownedOperation.ownedParameter.upperValue").watch(
        f"subject[{cast}].ownedOperation.ownedParameter.type.name"
    ).watch(f"subject[{cast}].ownedOperation.ownedParameter.typeValue").watch(
        f"subject[{cast}].ownedOperation.ownedParameter.defaultValue"
    )


def attributes_compartment(subject):
    # We need to scope the attribute value, since the for loop changes it.
    def lazy_format(attribute):
        return lambda: format(attribute, tags=True)

    return CssNode(
        "compartment",
        subject,
        Box(
            *(
                CssNode(
                    "attribute",
                    attribute,
                    Text(
                        text=lazy_format(attribute),
                    ),
                )
                for attribute in subject.ownedAttribute
                if not attribute.association
            ),
            draw=draw_top_separator,
        ),
    )


def operations_compartment(subject):
    def lazy_format(operation):
        return lambda: format(
            operation, visibility=True, type=True, multiplicity=True, default=True
        )

    return CssNode(
        "compartment",
        subject,
        Box(
            *(
                CssNode(
                    "operation",
                    operation,
                    Text(
                        text=lazy_format(operation),
                    ),
                )
                for operation in subject.ownedOperation
            ),
            draw=draw_top_separator,
        ),
    )
