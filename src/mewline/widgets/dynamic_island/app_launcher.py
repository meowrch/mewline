import contextlib
from collections.abc import Iterator
from threading import Lock
from typing import TYPE_CHECKING

from fabric.utils import DesktopApp
from fabric.utils import get_desktop_applications
from fabric.utils import idle_add
from fabric.utils import remove_handler
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.entry import Entry
from fabric.widgets.image import Image
from fabric.widgets.label import Label
from fabric.widgets.scrolledwindow import ScrolledWindow
from gi.repository import Gdk
from gi.repository import GLib

from mewline import constants as cnst
from mewline.utils.misc import check_icon_exists
from mewline.widgets.dynamic_island.base import BaseDiWidget

if TYPE_CHECKING:
    from mewline.widgets.dynamic_island import DynamicIsland


class AppLauncher(BaseDiWidget, Box):
    focuse_kb = True
    checking_changes_lock = Lock()
    arranging_viewport_lock = Lock()

    def __init__(self, dynamic_island: "DynamicIsland") -> None:
        Box.__init__(self, name="app-launcher", visible=False, all_visible=False)

        self.di = dynamic_island
        self.selected_index = -1  # Track the selected item index

        self._arranger_handler: int = 0
        self._arrange_token = None  # generation token to cancel stale updates
        self._all_apps = get_desktop_applications()

        # Width guardrails for the scrolled area to prevent runaway expansion
        self._min_content_width = 480
        self._max_content_width = 680

        self.viewport = Box(name="viewport", spacing=4, orientation="v")
        self.search_entry = Entry(
            name="app-launcher-search-entry",
            placeholder="Search Applications...",
            h_expand=True,
            notify_text=lambda entry, *_: self.arrange_viewport(entry.get_text()),
            on_activate=lambda entry, *_: self.on_search_entry_activate(
                entry.get_text()
            ),
            on_key_press_event=self.on_search_entry_key_press,  # Handle key presses
        )
        self.search_entry.props.xalign = 0.5
        self.scrolled_window = ScrolledWindow(
            name="app-launcher-scrolled-window",
            spacing=10,
            child=self.viewport,
            v_expand=True,
        )
        # Clamp width so CSS stays respected even under rapid updates
        with contextlib.suppress(Exception):
            self.scrolled_window.set_min_content_width(self._min_content_width)
        with contextlib.suppress(Exception):
            # Gtk.ScrolledWindow has max-content-width in GTK 3
            self.scrolled_window.set_max_content_width(self._max_content_width)

        self.header_box = Box(
            spacing=10,
            orientation="h",
            children=[
                self.search_entry,
                Button(
                    name="app-launcher-close-button",
                    image=Image(
                        style_classes="app-launcher-close-label",
                        icon_name=check_icon_exists(
                            "close-symbolic",
                            cnst.icons["ui"]["close"],
                        ),
                        icon_size=16,
                    ),
                    tooltip_text="Exit",
                    on_clicked=lambda *_: self.close_launcher(),
                ),
            ],
        )

        self.launcher_box = Box(
            name="launcher-box",
            spacing=10,
            h_expand=True,
            orientation="v",
            children=[
                self.header_box,
                self.scrolled_window,
            ],
        )

        self.resize_viewport()

        self.add(self.launcher_box)
        self.show_all()

    def close_launcher(self) -> None:
        self._clear_box_children(self.viewport)
        self.selected_index = -1  # Reset selection
        self.di.close()

    def open_widget_from_di(self) -> None:
        GLib.Thread.new("app_launcher_checking_for_changes", self._check_changes)

    def _check_changes(self) -> None:
        with self.checking_changes_lock:
            new_apps = get_desktop_applications()

            if not self._all_apps:
                self._all_apps = new_apps
                self.arrange_viewport()
                return

            new_app_names = [a.name for a in new_apps]
            old_app_names = [a.name for a in self._all_apps]

            if set(old_app_names) != set(new_app_names):
                self._all_apps = new_apps
                self.arrange_viewport()
                return

    def arrange_viewport(self, query: str = "") -> None:
        # Create a new generation token;
        # any previously scheduled updates will be ignored
        token = object()
        self._arrange_token = token
        GLib.Thread.new(
            "app_launcher_arrange_viewport",
            self._arrange_viewport,
            query,
            token,
        )

    def _arrange_viewport(self, query: str = "", token=None) -> None:
        # NOTE: GTK widgets must only be touched from the main thread.
        # This worker thread prepares data, then schedules all UI updates via idle_add.
        with self.arranging_viewport_lock:
            # Prepare filtered apps on the worker thread (no GTK usage here)
            filtered_apps = sorted(
                [
                    app
                    for app in self._all_apps
                    if query.casefold()
                    in (
                        (app.display_name or "")
                        + (" " + app.name + " ")
                        + (app.generic_name or "")
                    ).casefold()
                ],
                key=lambda app: (app.display_name or "").casefold(),
            )
            should_resize = len(filtered_apps) == len(self._all_apps)

            prev_handler = self._arranger_handler
            self._arranger_handler = 0

            def start_ui_update():
                # Ignore if a newer arrange request superseded us
                if token is not None and token is not self._arrange_token:
                    return False
                # Safely remove previous source from the main loop
                if prev_handler:
                    with contextlib.suppress(Exception):
                        remove_handler(prev_handler)
                # Clear viewport on the main thread using safe removal
                self._clear_box_children(self.viewport)
                self.selected_index = -1  # Clear selection when viewport changes
                # Re-assert width bounds to avoid temporary expansion
                with contextlib.suppress(Exception):
                    self.scrolled_window.set_min_content_width(self._min_content_width)
                with contextlib.suppress(Exception):
                    self.scrolled_window.set_max_content_width(self._max_content_width)

                filtered_apps_iter = iter(filtered_apps)
                current_token = token
                self._arranger_handler = idle_add(
                    lambda apps_iter, _tok=current_token: self._add_next_application(
                        apps_iter, _tok
                    )
                    or self.handle_arrange_complete(should_resize, query),
                    filtered_apps_iter,
                    pin=True,
                )
                return False

            GLib.idle_add(start_ui_update)

    def handle_arrange_complete(self, should_resize, query) -> bool:
        if should_resize:
            self.resize_viewport()

        # Only auto-select first item if query exists
        if query.strip() != "" and self.viewport.get_children():
            self.update_selection(0)

        return False

    def _add_next_application(self, apps_iter: Iterator[DesktopApp], token) -> bool:
        # Stop if outdated
        if token is not None and token is not self._arrange_token:
            return False
        if not (app := next(apps_iter, None)):
            return False
        # Adding a child must happen on the main thread (we are in idle handler)
        self.viewport.add(self.bake_application_slot(app))
        return True

    def resize_viewport(self) -> bool:
        # Keep sizing under strict guardrails; do not derive from current allocation
        with contextlib.suppress(Exception):
            self.scrolled_window.set_min_content_width(self._min_content_width)
        with contextlib.suppress(Exception):
            self.scrolled_window.set_max_content_width(self._max_content_width)
        return False

    def bake_application_slot(self, app: DesktopApp, **kwargs) -> Button:
        # Be defensive with icon loading; fall back to a standard icon on failure
        try:
            icon_pixbuf = app.get_icon_pixbuf(size=24)
            if icon_pixbuf is not None:
                icon_widget = Image(pixbuf=icon_pixbuf)
            else:
                icon_widget = Image(
                    icon_name=check_icon_exists(
                        "application-x-executable-symbolic",
                        cnst.icons["fallback"]["notification"],
                    ),
                    icon_size=16,
                )
        except Exception:
            icon_widget = Image(
                icon_name=check_icon_exists(
                    "application-x-executable-symbolic",
                    cnst.icons["fallback"]["notification"],
                ),
                icon_size=16,
            )

        button = Button(
            name="app-launcher-app-slot-button",
            child=Box(
                name="app-launcher-app-slot-box",
                orientation="h",
                spacing=10,
                children=[
                    icon_widget,
                    Label(
                        name="app-label",
                        label=app.display_name or "Unknown",
                        ellipsization="end",
                        v_align="center",
                        h_align="center",
                    ),
                ],
            ),
            tooltip_text=app.description,
            on_clicked=lambda *_: (app.launch(), self.close_launcher()),
            **kwargs,
        )
        return button

    def update_selection(self, new_index: int) -> None:
        # Unselect current
        if self.selected_index != -1 and self.selected_index < len(
            self.viewport.get_children()
        ):
            current_button = self.viewport.get_children()[self.selected_index]
            current_button.get_style_context().remove_class("selected")
        # Select new
        if new_index != -1 and new_index < len(self.viewport.get_children()):
            new_button = self.viewport.get_children()[new_index]
            new_button.get_style_context().add_class("selected")
            self.selected_index = new_index
            self.scroll_to_selected(new_button)
        else:
            self.selected_index = -1

    def scroll_to_selected(self, button) -> bool:
        def scroll():
            adj = self.scrolled_window.get_vadjustment()
            alloc = button.get_allocation()
            if alloc.height == 0:
                return False  # Retry if allocation isn't ready

            y = alloc.y
            height = alloc.height
            page_size = adj.get_page_size()
            current_value = adj.get_value()

            # Calculate visible boundaries
            visible_top = current_value
            visible_bottom = current_value + page_size

            if y < visible_top:
                # Item above viewport - align to top
                adj.set_value(y)
            elif y + height > visible_bottom:
                # Item below viewport - align to bottom
                new_value = y + height - page_size
                adj.set_value(new_value)

            # No action if already fully visible
            return False

        GLib.idle_add(scroll)

    def on_search_entry_activate(self, text) -> None:
        children = self.viewport.get_children()
        if children:
            # Only activate if we have selection or non-empty query
            if text.strip() == "" and self.selected_index == -1:
                return  # Prevent accidental activation when empty
            selected_index = self.selected_index if self.selected_index != -1 else 0
            if 0 <= selected_index < len(children):
                children[selected_index].clicked()

    def on_search_entry_key_press(self, widget, event) -> bool:
        keyval = event.keyval
        if keyval == Gdk.KEY_Down:
            self.move_selection(1)
            return True
        elif keyval == Gdk.KEY_Up:
            self.move_selection(-1)
            return True
        elif keyval == Gdk.KEY_Escape:
            self.close_launcher()
            return True
        return False

    def move_selection(self, delta: int) -> None:
        children = self.viewport.get_children()
        if not children:
            return

        # Allow starting selection from nothing when empty
        if self.selected_index == -1 and delta == 1:
            new_index = 0
        else:
            new_index = self.selected_index + delta

        new_index = max(0, min(new_index, len(children) - 1))
        self.update_selection(new_index)

    def _clear_box_children(self, box: Box) -> None:
        try:
            for child in list(box.get_children()):
                with contextlib.suppress(Exception):
                    box.remove(child)
                with contextlib.suppress(Exception):
                    child.destroy()
        except Exception:
            # Fallback to direct property clear if available in Fabric
            with contextlib.suppress(Exception):
                box.children = []
