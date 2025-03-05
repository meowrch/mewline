import concurrent.futures
import hashlib
import json
import os
import subprocess
import traceback
from concurrent.futures import ThreadPoolExecutor

from fabric.widgets.box import Box
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.entry import Entry
from fabric.widgets.scrolledwindow import ScrolledWindow
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk
from loguru import logger
from PIL import Image
from PIL import ImageDraw

from mewline import constants as cnst
from mewline.config import cfg
from mewline.widgets.dynamic_island.base import BaseDiWidget


class WallpaperApply:
    @staticmethod
    def apply_with_swww(wallpaper: str):
        transition_fps = 60
        cursor_pos = "0,0"

        try:
            output = subprocess.check_output(  # noqa: S603
                ["wlr-randr", "--json"],  # noqa: S607
                stderr=subprocess.DEVNULL,
                text=True,
            )
            for output_info in json.loads(output):
                for mode in output_info["modes"]:
                    if mode.get("current"):
                        transition_fps = int(round(mode["refresh"]))
                        break
                else:
                    continue
                break
        except Exception:
            logger.warning(
                f"Couldn't get the screen frequency using wlr-randr: {traceback.format_exc()}"
            )

        try:
            output = subprocess.check_output(  # noqa: S603
                ["hyprctl", "cursorpos"],  # noqa: S607
                text=True,
            ).strip()

            if output:
                cursor_pos = output
        except Exception:
            logger.warning(
                f"Couldn't get the cursor position: {traceback.format_exc()}"
            )

        try:
            subprocess.run(  # noqa: S603
                [  # noqa: S607
                    "swww",
                    "img",
                    str(wallpaper),
                    "--transition-bezier",
                    ".43,1.19,1,.4",
                    "--transition-type",
                    "grow",
                    "--transition-duration",
                    "0.4",
                    "--transition-fps",
                    str(transition_fps),
                    "--invert-y",
                    "--transition-pos",
                    cursor_pos,
                ],
                check=True,
            )
        except Exception:
            logger.error(
                f"Unknown error when installing wallpaper (swww): {traceback.format_exc()}"
            )


class WallpaperSelector(BaseDiWidget, Box):
    focuse_kb: bool = True

    def __init__(self):
        Box.__init__(
            self,
            name="wallpapers",
            spacing=10,
            orientation="v",
            h_expand=False,
            v_expand=False,
        )
        self.config = cfg.modules.dynamic_island.wallpapers
        self.CACHE_DIR = cnst.WALLPAPERS_THUMBS_DIR
        self.WALLPAPERS_DIR = cnst.WALLPAPERS_DIR
        os.makedirs(self.CACHE_DIR, exist_ok=True)

        # Process old wallpapers: use os.scandir for efficiency and only loop
        # over image files that actually need renaming (they're not already lowercase
        # and with hyphens instead of spaces)
        with os.scandir(self.WALLPAPERS_DIR) as entries:
            for entry in entries:
                if entry.is_file() and self._is_image(entry.name):  # noqa: SIM102
                    # Check if the file needs renaming:
                    # №file should be lowercase and have hyphens instead of spaces
                    if entry.name != entry.name.lower() or " " in entry.name:
                        new_name = entry.name.lower().replace(" ", "-")
                        full_path = os.path.join(self.WALLPAPERS_DIR, entry.name)
                        new_full_path = os.path.join(self.WALLPAPERS_DIR, new_name)
                        try:
                            os.rename(full_path, new_full_path)
                            print(
                                f"Renamed old wallpaper '{full_path}' to '{new_full_path}'"
                            )
                        except Exception as e:
                            print(f"Error renaming file {full_path}: {e}")

        # Refresh the file list after potential renaming
        self.files = sorted(
            [f for f in os.listdir(self.WALLPAPERS_DIR) if self._is_image(f)]
        )
        self.thumbnails = []
        self.thumbnail_queue = []
        self.executor = ThreadPoolExecutor(max_workers=4)  # Shared executor

        # Variable to control the selection (similar to AppLauncher)
        self.selected_index = -1

        # Initialize UI components
        self.viewport = Gtk.IconView(name="wallpaper-icons")
        self.viewport.set_model(Gtk.ListStore(GdkPixbuf.Pixbuf, str))
        self.viewport.set_pixbuf_column(0)
        # Hide text column so only the image is shown
        self.viewport.set_text_column(-1)
        self.viewport.set_item_width(0)
        self.viewport.connect("item-activated", self.on_wallpaper_selected)

        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            #wallpaper-icons {
                background-color: transparent;
            }
        """)

        context = self.viewport.get_style_context()
        context.add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.scrolled_window = ScrolledWindow(
            name="scrolled-window",
            spacing=10,
            h_expand=True,
            v_expand=True,
            child=self.viewport,
        )

        self.search_entry = Entry(
            name="search-entry-walls",
            placeholder="Search Wallpapers...",
            h_expand=True,
            notify_text=lambda entry, *_: self.arrange_viewport(entry.get_text()),
            on_key_press_event=self.on_search_entry_key_press,
        )
        self.search_entry.props.xalign = 0.5
        self.search_entry.connect("focus-out-event", self.on_search_entry_focus_out)

        # Add the switcher to the header_box's start_children
        self.header_box = CenterBox(
            name="header-box",
            spacing=8,
            orientation="h",
            center_children=[self.search_entry],
        )

        self.add(self.header_box)
        self.add(self.scrolled_window)
        self._start_thumbnail_thread()
        self.setup_file_monitor()  # Initialize file monitoring
        self.show_all()
        # Ensure the search entry gets focus when starting
        self.search_entry.grab_focus()

    def setup_file_monitor(self):
        gfile = Gio.File.new_for_path(str(self.WALLPAPERS_DIR))
        self.file_monitor = gfile.monitor_directory(Gio.FileMonitorFlags.NONE, None)
        self.file_monitor.connect("changed", self.on_directory_changed)

    def on_directory_changed(self, monitor, file, _other_file, event_type):
        file_name = file.get_basename()
        if event_type == Gio.FileMonitorEvent.DELETED:
            if file_name in self.files:
                self.files.remove(file_name)
                cache_path = self._get_cache_path(file_name)
                if os.path.exists(cache_path):
                    try:
                        os.remove(cache_path)
                    except Exception as e:
                        print(f"Error deleting cache {cache_path}: {e}")
                self.thumbnails = [(p, n) for p, n in self.thumbnails if n != file_name]
                GLib.idle_add(self.arrange_viewport, self.search_entry.get_text())
        elif event_type == Gio.FileMonitorEvent.CREATED:
            if self._is_image(file_name):
                # Convert filename to lowercase and replace spaces with "-"
                new_name = file_name.lower().replace(" ", "-")
                full_path = os.path.join(self.WALLPAPERS_DIR, file_name)
                new_full_path = os.path.join(self.WALLPAPERS_DIR, new_name)
                if new_name != file_name:
                    try:
                        os.rename(full_path, new_full_path)
                        file_name = new_name
                        print(f"Renamed file '{full_path}' to '{new_full_path}'")
                    except Exception as e:
                        print(f"Error renaming file {full_path}: {e}")
                if file_name not in self.files:
                    self.files.append(file_name)
                    self.files.sort()
                    self.executor.submit(self._process_file, file_name)
        elif event_type == Gio.FileMonitorEvent.CHANGED:  # noqa: SIM102
            if self._is_image(file_name) and file_name in self.files:
                cache_path = self._get_cache_path(file_name)
                if os.path.exists(cache_path):
                    try:
                        os.remove(cache_path)
                    except Exception as e:
                        print(f"Error deleting cache for changed file {file_name}: {e}")
                self.executor.submit(self._process_file, file_name)

    def arrange_viewport(self, query: str = ""):
        model = self.viewport.get_model()
        model.clear()
        filtered_thumbnails = [
            (thumb, name)
            for thumb, name in self.thumbnails
            if query.casefold() in name.casefold()
        ]
        filtered_thumbnails.sort(key=lambda x: x[1].lower())
        for pixbuf, file_name in filtered_thumbnails:
            model.append([pixbuf, file_name])
        # If the search entry is empty, no icon is selected;
        # otherwise, select the first one.
        if query.strip() == "":
            self.viewport.unselect_all()
            self.selected_index = -1
        elif len(model) > 0:
            self.update_selection(0)

    def on_wallpaper_selected(self, iconview, path):
        model = iconview.get_model()
        file_name = model[path][1]
        full_path = os.path.join(self.WALLPAPERS_DIR, file_name)

        if self.config.method == "swww":
            logger.info(f'Installing wallpaper "{full_path}" using method sww')
            WallpaperApply.apply_with_swww(full_path)
        else:
            logger.warning(
                f"Installing wallpaper \"{full_path}\" using default method (swww)."
                f"Because there is no implementation for method \"{self.config.method}\"."
            )

    def on_search_entry_key_press(self, widget, event):
        if event.keyval in (Gdk.KEY_Up, Gdk.KEY_Down, Gdk.KEY_Left, Gdk.KEY_Right):
            self.move_selection_2d(event.keyval)
            return True
        elif event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            if self.selected_index != -1:
                path = Gtk.TreePath.new_from_indices([self.selected_index])
                self.on_wallpaper_selected(self.viewport, path)
            return True
        return False

    def move_selection_2d(self, keyval):
        model = self.viewport.get_model()
        total_items = len(model)
        if total_items == 0:
            return

        if self.selected_index == -1:
            new_index = (
                0 if keyval in (Gdk.KEY_Down, Gdk.KEY_Right) else total_items - 1
            )
        else:
            current_index = self.selected_index
            allocation = self.viewport.get_allocation()
            item_width = 108  # Approximate item width including margins
            columns = max(1, allocation.width // item_width)
            if keyval == Gdk.KEY_Right:
                new_index = current_index + 1
            elif keyval == Gdk.KEY_Left:
                new_index = current_index - 1
            elif keyval == Gdk.KEY_Down:
                new_index = current_index + columns
            elif keyval == Gdk.KEY_Up:
                new_index = current_index - columns
            if new_index < 0:
                new_index = 0
            if new_index >= total_items:
                new_index = total_items - 1

        self.update_selection(new_index)

    def update_selection(self, new_index: int):
        self.viewport.unselect_all()
        path = Gtk.TreePath.new_from_indices([new_index])
        self.viewport.select_path(path)
        self.viewport.scroll_to_path(
            path, False, 0.5, 0.5
        )  # Ensure the selected icon is visible
        self.selected_index = new_index

    def _start_thumbnail_thread(self):
        GLib.Thread.new("thumbnail-loader", self._preload_thumbnails, None)

    def _preload_thumbnails(self, _):
        futures = [
            self.executor.submit(self._process_file, file_name)
            for file_name in self.files
        ]
        concurrent.futures.wait(futures)
        GLib.idle_add(self._process_batch)

    def _process_file(self, file_name):
        full_path = os.path.join(self.WALLPAPERS_DIR, file_name)
        cache_path = self._get_cache_path(file_name)
        if not os.path.exists(cache_path):
            try:
                with Image.open(full_path) as img:
                    width, height = img.size
                    side = min(width, height)
                    left = (width - side) // 2
                    top = (height - side) // 2
                    right = left + side
                    bottom = top + side
                    img_cropped = img.crop((left, top, right, bottom)).convert("RGBA")
                    img_cropped.thumbnail((96, 96), Image.Resampling.LANCZOS)
                    img_cropped = self._add_rounded_corners(img_cropped, radius=15)
                    img_cropped.save(cache_path, "PNG")
            except Exception as e:
                print(f"Error processing {file_name}: {e}")
                return
        self.thumbnail_queue.append((cache_path, file_name))
        GLib.idle_add(self._process_batch)

    def _process_batch(self):
        batch = self.thumbnail_queue[:10]
        del self.thumbnail_queue[:10]
        for cache_path, file_name in batch:
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(cache_path)
                self.thumbnails.append((pixbuf, file_name))
                self.viewport.get_model().append([pixbuf, file_name])
            except Exception as e:
                print(f"Error loading thumbnail {cache_path}: {e}")
        if self.thumbnail_queue:
            GLib.idle_add(self._process_batch)
        return False

    def _get_cache_path(self, file_name: str) -> str:
        file_hash = hashlib.md5(  # noqa: S324
            f"{file_name}".encode()
        ).hexdigest()
        return os.path.join(self.CACHE_DIR, f"{file_hash}.png")

    def _add_rounded_corners(self, im: Image.Image, radius: int) -> Image.Image:
        mask = Image.new("L", im.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([(0, 0), im.size], radius=radius, fill=255)
        im.putalpha(mask)
        return im

    @staticmethod
    def _is_image(file_name: str) -> bool:
        return file_name.lower().endswith(
            (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")
        )

    def on_search_entry_focus_out(self, widget, _):
        if self.get_mapped():
            widget.grab_focus()
        return False
