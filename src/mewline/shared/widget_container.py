from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.eventbox import EventBox
from ..utils.widget_utils import setup_cursor_hover


class BoxWidget(Box):
    """A container for box widgets."""

    def __init__(self, **kwargs):
        super().__init__(
            spacing=4,
            style_classes="panel-box",
            **kwargs,
        )
        self.add_style_class("default")


class EventBoxWidget(EventBox):
    """A container for box widgets."""

    def __init__(self, **kwargs):
        super().__init__(
            name="panel-eventbox",
            **kwargs,
        )
        self.connect(
            "child-notify",
            lambda *_: self.children[0].add_style_class("default"),
        )


class ButtonWidget(Button):
    """A container for button widgets."""

    def __init__(self, **kwargs):
        super().__init__(
            style_classes="panel-button",
            **kwargs,
        )
        setup_cursor_hover(self)
        self.add_style_class("default")
