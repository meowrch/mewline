from fabric.hyprland.widgets import Language
from fabric.utils import FormattedString
from fabric.utils import truncate
from fabric.widgets.box import Box

from mewline.shared.widget_container import ButtonWidget


class LanguageWidget(ButtonWidget):
    """A widget to display the current language."""

    def __init__(self):
        super().__init__(name="language")

        self.box = Box()
        self.children = (self.box,)

        self.lang = Language(
            formatter=FormattedString(
                "{truncate(language,length,suffix)}",
                truncate=truncate,
                length=2,
                suffix="",
            ),
        )
        self.box.children = (self.lang)


