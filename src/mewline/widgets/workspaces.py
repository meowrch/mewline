from fabric.core.widgets import WorkspaceButton
from fabric.hyprland.widgets import Workspaces as HyprlandWorkspaces
from loguru import logger

from mewline.config import cfg
from mewline.custom_fabric.bspwm import BspwmWorkspaces
from mewline.shared.widget_container import BoxWidget
from mewline.utils.misc import unique_list
from mewline.utils.window_manager import WindowManager
from mewline.utils.window_manager import detect_window_manager


def buttons_factory(ws_id) -> WorkspaceButton:
    """Factory function to create buttons for each workspace.

    Args:
        ws_id (_type_): Identifier of the workspace

    Returns:
        WorkspaceButton: Button for each workspace
    """
    return WorkspaceButton(
        id=ws_id,
        label=f"{cfg.modules.workspaces.icon_map.get(str(ws_id), ws_id)}",
        visible=ws_id not in unique_list(cfg.modules.workspaces.ignored),
    )


class _BaseWorkspacesWidget(BoxWidget):
    """Shared setup for Hyprland and bspwm workspace widgets."""

    workspace_class = None  # type: ignore

    def __init__(self, **kwargs):
        super().__init__(name="workspaces-box", **kwargs)
        self.config = cfg.modules.workspaces

        # Precreate buttons if we want to show empty workspaces
        buttons = None
        if not self.config.hide_unoccupied:
            buttons = [
                WorkspaceButton(
                    id=i,
                    label=f"{self.config.icon_map.get(str(i), i)}",
                    visible=i not in unique_list(self.config.ignored),
                )
                for i in range(1, self.config.count + 1)
            ]

        ws_kwargs = {
            "name": "workspaces",
            "spacing": 4,
            "buttons": buttons,
            "buttons_factory": buttons_factory,
            "invert_scroll": self.config.reverse_scroll,
            # hyprland uses this; bspwm __init__ accepts **kwargs so safe
            "empty_scroll": getattr(self.config, "empty_scroll", False),
        }

        self.workspace = self.workspace_class(**ws_kwargs)
        self.children = self.workspace


class HyprlandWorkSpacesWidget(_BaseWorkspacesWidget):
    workspace_class = HyprlandWorkspaces


class BspwmWorkSpacesWidget(_BaseWorkspacesWidget):
    workspace_class = BspwmWorkspaces


def create_workspaces_widget(**kwargs) -> BoxWidget:
    """Factory to create workspaces widget based on current window manager."""
    wm = detect_window_manager()

    if wm == WindowManager.BSPWM:
        logger.info("Creating bspwm workspaces widget")
        return BspwmWorkSpacesWidget(**kwargs)

    logger.info("Creating Hyprland workspaces widget")
    return HyprlandWorkSpacesWidget(**kwargs)
