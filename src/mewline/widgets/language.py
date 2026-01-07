from fabric.utils import FormattedString
from fabric.utils import truncate
from fabric.widgets.box import Box
from loguru import logger

from mewline.shared.widget_container import ButtonWidget


class LanguageWidget(ButtonWidget):
    """A widget to display the current language with adaptive WM support."""

    def __init__(self):
        super().__init__(name="language")

        self.box = Box()
        self.children = (self.box,)

        # Detect current window manager and use appropriate widget
        self.lang = self._create_language_widget()
        self.box.children = (self.lang,)

    def _create_language_widget(self):
        """Create appropriate Language widget based on current WM.

        Returns:
            Language widget instance (Hyprland or bspwm specific)
        """
        formatter = FormattedString(
            "{truncate(language,length,suffix)}",
            truncate=truncate,
            length=2,
            suffix="",
        )

        # Try Hyprland first
        try:
            from fabric.hyprland.widgets import Language

            widget = Language(formatter=formatter)
            logger.info("[LanguageWidget] Using Hyprland Language widget")
            return widget
        except (ImportError, Exception) as e:
            logger.debug(f"[LanguageWidget] Hyprland not available: {e}, trying bspwm")

        # Fallback to bspwm
        try:
            from mewline.custom_fabric.bspwm.widgets import BspwmLanguage

            widget = BspwmLanguage(formatter=formatter)
            logger.info("[LanguageWidget] Using bspwm Language widget")
            return widget
        except (ImportError, Exception) as e:
            logger.error(f"[LanguageWidget] Failed to initialize language widget: {e}")
            # Return a minimal fallback
            from fabric.widgets.label import Label

            return Label(label="N/A")
