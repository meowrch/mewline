import os
from typing import TYPE_CHECKING

from fabric.widgets.button import Button
from fabric.widgets.centerbox import CenterBox

from mewline.utils.widget_utils import setup_cursor_hover
from mewline.widgets.dynamic_island.base import BaseDiWidget

if TYPE_CHECKING:
    from mewline.widgets.dynamic_island import DynamicIsland


class Compact(BaseDiWidget, CenterBox):
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
