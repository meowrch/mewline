from fabric.hyprland.widgets import WorkspaceButton, Workspaces

from ..config import cfg
from ..shared.widget_container import BoxWidget
from ..utils.misc import unique_list


def buttons_factory(ws_id) -> WorkspaceButton:
    """Factory function to create buttons for each workspace

    Args:
        ws_id (_type_): _description_

    Returns:
        WorkspaceButton: _description_
    """
    return WorkspaceButton(
        id=ws_id,
        label=f"{cfg.modules.workspaces.icon_map.get(str(ws_id), ws_id)}",
        visible=ws_id
        not in unique_list(cfg.modules.workspaces.ignored),
    )


class HyprlandWorkSpacesWidget(BoxWidget):
    """A widget to display the current workspaces."""

    def __init__(self, **kwargs):
        super().__init__(name="workspaces-box", **kwargs)

        self.config = cfg.modules.workspaces

        # Create buttons for each workspace if occupied
        buttons = None
        if not self.config.hide_unoccupied:
            buttons = [
                WorkspaceButton(id=i, label=str(i))
                for i in range(1, self.config.count + 1)
            ]

        # Create a HyperlandWorkspace widget to manage workspace buttons
        self.workspace = Workspaces(
            name="workspaces",
            spacing=4,
            buttons=buttons,
            buttons_factory=buttons_factory,
            invert_scroll=self.config.reverse_scroll,
            empty_scroll=self.config.empty_scroll,
        )

        # Add the HyperlandWorkspace widget as a child
        self.children = self.workspace
