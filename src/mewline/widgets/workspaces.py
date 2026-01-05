import json
import subprocess
import threading

from fabric.hyprland.widgets import WorkspaceButton
from fabric.hyprland.widgets import Workspaces
from fabric.widgets.button import Button
from gi.repository import GLib
from loguru import logger

from mewline.config import cfg
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


class BspwmWorkspaceButton(Button):
    """Button for a single bspwm workspace."""

    def __init__(self, desktop_id: str, icon_map: dict, **kwargs):
        label = icon_map.get(str(desktop_id), desktop_id)
        super().__init__(label=label, **kwargs)
        self.desktop_id = desktop_id
        self.icon_map = icon_map

    def update_label(self):
        """Update button label from icon map."""
        self.label = f"{self.icon_map.get(str(self.desktop_id), self.desktop_id)}"


class BspwmWorkspacesWidget(BoxWidget):
    """A widget to display bspwm workspaces."""

    def __init__(self, **kwargs):
        super().__init__(name="workspaces", **kwargs)
        self.config = cfg.modules.workspaces
        self.ignored_ws = unique_list(self.config.ignored)
        self.buttons: list[BspwmWorkspaceButton] = []
        self.monitor = ""

        # Initialize workspace buttons
        self._init_workspaces()

        # Start thread to listen for bspwm events
        self.update_thread = threading.Thread(target=self._listen_bspwm, daemon=True)
        self.update_thread.start()

    def _init_workspaces(self):
        """Initialize workspace buttons for all desktops."""
        try:
            # Get desktop names
            result = subprocess.run(
                ["bspc", "query", "-D", "--names"],
                capture_output=True,
                text=True,
                check=True,
            )
            desktops = result.stdout.strip().split("\n")

            # Create buttons for each desktop
            for desktop in desktops:
                if desktop in self.ignored_ws or not desktop:
                    continue

                button = BspwmWorkspaceButton(
                    desktop_id=desktop,
                    icon_map=self.config.icon_map,
                    name=f"workspace-{desktop}",
                    visible=True,
                )
                button.connect("button-press-event", self._on_workspace_click)
                self.buttons.append(button)
                self.add(button)

            # Update initial state
            self._update_state()

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to initialize bspwm workspaces: {e}")
        except Exception as e:
            logger.error(f"Unexpected error initializing workspaces: {e}")

    def _update_state(self):
        """Update workspace button states based on current bspwm state."""
        try:
            # Get current bspwm state
            result = subprocess.run(
                ["bspc", "wm", "--dump-state"],
                capture_output=True,
                text=True,
                check=True,
            )
            status = json.loads(result.stdout)

            # Process each monitor and desktop
            for monitor in status["monitors"]:
                for desktop in monitor["desktops"]:
                    for button in self.buttons:
                        if button.desktop_id == str(desktop["name"]):
                            # Determine desktop states
                            is_focused = monitor["focusedDesktopId"] == desktop["id"]
                            is_occupied = desktop["root"] is not None

                            # Update button visibility
                            if self.config.hide_unoccupied:
                                button.set_visible(desktop["root"] or is_focused)
                            else:
                                button.set_visible(True)

                            # Check for urgent state
                            is_urgent = False
                            if desktop["root"] is not None:
                                is_urgent = self._check_if_urgent(desktop["root"])

                            # Update CSS classes
                            style_context = button.get_style_context()
                            style_context.remove_class("active")
                            style_context.remove_class("occupied")
                            style_context.remove_class("urgent")

                            if is_focused:
                                style_context.add_class("active")
                            if is_occupied:
                                style_context.add_class("occupied")
                            if is_urgent:
                                style_context.add_class("urgent")

                            button.update_label()

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to update bspwm workspace state: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse bspwm state JSON: {e}")
        except Exception as e:
            logger.error(f"Unexpected error updating workspace state: {e}")

    def _check_if_urgent(self, root_node: dict) -> bool:
        """Recursively check if any window in the tree is urgent.

        Args:
            root_node: Root node of the window tree

        Returns:
            True if any window is urgent, False otherwise
        """
        if root_node is None:
            return False

        # Check if current node has urgent client
        if root_node.get("client") and "urgent" in root_node["client"]:
            return True

        # Recursively check children
        if "firstChild" in root_node and self._check_if_urgent(root_node["firstChild"]):
            return True

        return bool("secondChild" in root_node and self._check_if_urgent(root_node["secondChild"]))

    def _listen_bspwm(self):
        """Listen to bspwm events and update state accordingly."""
        try:
            process = subprocess.Popen(
                ["bspc", "subscribe", "report"],
                stdout=subprocess.PIPE,
                text=True,
            )

            logger.info("Started listening to bspwm events")

            while True:
                output = process.stdout.readline()
                if output:
                    # Update state on GTK main thread
                    GLib.idle_add(self._update_state)

        except Exception as e:
            logger.error(f"Error listening to bspwm events: {e}")

    def _on_workspace_click(self, widget, event):
        """Handle workspace button click to switch desktop.

        Args:
            widget: The clicked button widget
            event: The button press event
        """
        try:
            subprocess.run(
                ["bspc", "desktop", "-f", widget.desktop_id],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to switch to desktop {widget.desktop_id}: {e}")


def create_workspaces_widget(**kwargs) -> BoxWidget:
    """Factory function to create the appropriate workspaces widget based on WM.

    Args:
        **kwargs: Arguments to pass to the widget constructor

    Returns:
        BoxWidget: Either HyprlandWorkSpacesWidget or BspwmWorkspacesWidget
    """
    wm = detect_window_manager()

    if wm == WindowManager.BSPWM:
        logger.info("Creating bspwm workspaces widget")
        return BspwmWorkspacesWidget(**kwargs)
    else:
        # Default to Hyprland
        logger.info("Creating Hyprland workspaces widget")
        return HyprlandWorkSpacesWidget(**kwargs)
