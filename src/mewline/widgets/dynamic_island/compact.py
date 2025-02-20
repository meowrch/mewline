import os
import re
from typing import TYPE_CHECKING

from fabric.hyprland.widgets import ActiveWindow
from fabric.utils import FormattedString
from fabric.utils import truncate
from fabric.widgets.button import Button
from fabric.widgets.centerbox import CenterBox

from mewline.config import cfg
from mewline.constants import WINDOW_TITLE_MAP
from mewline.utils.widget_utils import setup_cursor_hover
from mewline.widgets.dynamic_island.base import BaseDiWidget

if TYPE_CHECKING:
    from mewline.widgets.dynamic_island import DynamicIsland


class CompactOld(BaseDiWidget, CenterBox):
    """A widget to power off the system."""

    focuse_kb: bool = False

    def __init__(self, di: "DynamicIsland"):
        compact_button = Button(
            name="compact-label",
            label=f"{os.getlogin()}@{os.uname().nodename}",
            on_clicked=lambda *_: di.open("date_notification"),
        )

        setup_cursor_hover(compact_button)

        CenterBox.__init__(
            self,
            name="dynamic-island-compact",
            v_expand=True,
            h_expand=True,
            center_children=[compact_button],
        )


class Compact(BaseDiWidget, CenterBox):
    """A widget to power off the system."""

    focuse_kb: bool = False

    def __init__(self, di: "DynamicIsland"):
        self.config = cfg.modules.dynamic_island.window_titles

        compact_title = ActiveWindow(
            name="window",
            formatter=FormattedString(
                "{ get_title(win_title, win_class) }",
                get_title=self.get_title,
            ),
        )

        compact_button = Button(
            name="compact-label",
            child=compact_title,
            on_clicked=lambda *_: di.open("date_notification"),
        )

        setup_cursor_hover(compact_button)

        CenterBox.__init__(
            self,
            name="dynamic-island-compact",
            v_expand=True,
            h_expand=True,
            center_children=[compact_button],
        )

    def get_title(self, win_title, win_class):
        # Truncate the window title based on the configured length
        win_title = (
            truncate(win_title, self.config.truncation_size)
            if self.config.truncation
            else win_title
        )

        merged_titles = self.config.title_map + WINDOW_TITLE_MAP

        # Find a matching window class in the windowTitleMap
        matched_window = next(
            (wt for wt in merged_titles if re.search(wt[0], win_class.lower())),
            None,
        )

        # If no matching window class is found, return the window title
        if matched_window is None:
            return f"󰣆 {win_class.lower()}"

        if matched_window[0] == "^$":
            return (
                f"{matched_window[1]} {os.getlogin()}@{os.uname().nodename}"
                if self.config.enable_icon
                else f"{os.getlogin()}@{os.uname().nodename}"
            )

        # Return the formatted title with or without the icon
        return (
            f"{matched_window[1]} {matched_window[2]}"
            if self.config.enable_icon
            else f"{matched_window[2]}"
        )
