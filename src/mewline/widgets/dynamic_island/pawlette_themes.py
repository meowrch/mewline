import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from fabric.widgets.box import Box
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.entry import Entry
from fabric.widgets.scrolledwindow import ScrolledWindow
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import Gtk
from loguru import logger
from PIL import Image
from PIL import ImageChops
from PIL import ImageDraw

from mewline.widgets.dynamic_island.base import BaseDiWidget


class PawletteThemes(BaseDiWidget, Box):
    focuse_kb: bool = True
    checking_changes_lock = Lock()

    def __init__(self):
        Box.__init__(
            self,
            name="pawlette-themes",
            spacing=10,
            orientation="v",
            h_expand=False,
            v_expand=False,
        )

        self.themes_data = {}
        self.thumbnails = []
        self.thumbnail_queue = []
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.selected_index = -1

        if not self._check_pawlette_installed():
            logger.error("pawlette command not found")
            return

        self.themes_data = self._get_themes_data()

        self.list_store = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str)

        self.viewport = Gtk.IconView(
            name="theme-icons",
            model=self.list_store,
            pixbuf_column=0,
            text_column=1,
            item_width=120,
            item_padding=10,
            margin=10,
        )
        self.viewport.connect("item-activated", self.on_theme_selected)

        self.viewport.set_item_orientation(Gtk.Orientation.VERTICAL)
        self.viewport.set_columns(0)
        self.viewport.set_row_spacing(15)
        self.viewport.set_column_spacing(20)

        self.scrolled_window = ScrolledWindow(
            name="scrolled-window",
            h_expand=True,
            v_expand=True,
            child=self.viewport,
        )

        self.search_entry = Entry(
            name="search-entry-themes",
            placeholder="Search Themes...",
            h_expand=True,
            notify_text=lambda entry, *_: self.arrange_viewport(entry.get_text()),
            on_key_press_event=self.on_search_entry_key_press,
        )
        self.search_entry.props.xalign = 0.5
        self.search_entry.connect("focus-out-event", self.on_search_entry_focus_out)

        self.header_box = CenterBox(
            name="header-box",
            spacing=8,
            orientation="h",
            center_children=[self.search_entry],
        )

        self.add(self.header_box)
        self.add(self.scrolled_window)
        self._reload_themes()
        self.show_all()
        self.search_entry.grab_focus()

    def _check_pawlette_installed(self):
        try:
            subprocess.run(["which", "pawlette"], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def _get_themes_data(self):
        try:
            output = subprocess.check_output(
                ["pawlette", "get-themes-info"],
                stderr=subprocess.DEVNULL,
                text=True,
            )
            return json.loads(output)
        except Exception as e:
            logger.error(f"Failed to get themes info: {e}")
            return {}

    def open_widget_from_di(self) -> None:
        if not self.get_mapped() or not self.get_visible():
            return
        GLib.Thread.new("pawlette_themes_checking_for_changes", self._check_changes)

    def _check_changes(self) -> None:
        with self.checking_changes_lock:
            new_themes = self._get_themes_data()

            if not self.themes_data:
                self.themes_data = new_themes
                self._reload_themes()
                return

            new_theme_names = list(new_themes.keys())
            old_theme_names = list(self.themes_data.keys())

            if set(old_theme_names) != set(new_theme_names):
                self.themes_data = new_themes
                self._reload_themes()
                return

    def arrange_viewport(self, query: str = ""):
        self.list_store.clear()
        filtered = [
            (pixbuf, name, name)
            for pixbuf, name in self.thumbnails
            if query.casefold() in name.casefold()
        ]
        filtered.sort(key=lambda x: x[1].lower())
        for item in filtered:
            self.list_store.append(item)
        if query.strip() and self.list_store:
            self.update_selection(0)

    def on_theme_selected(self, iconview, path):
        GLib.Thread.new(
            "pawlette_select_theme", self._on_theme_selected, iconview, path
        )

    def _on_theme_selected(self, iconview, path):
        theme_name = iconview.get_model()[path][1]
        if theme_name not in self.themes_data:
            return

        try:
            subprocess.run(
                ["pawlette", "set-theme", theme_name],
                check=True,
            )
            logger.info(f"Theme {theme_name} applied successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to apply theme {theme_name}: {e}")

    def on_search_entry_key_press(self, widget, event):
        if event.keyval in (Gdk.KEY_Up, Gdk.KEY_Down, Gdk.KEY_Left, Gdk.KEY_Right):
            self.move_selection_2d(event.keyval)
            return True
        elif (
            event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter)
            and self.selected_index != -1
        ):
            path = Gtk.TreePath.new_from_indices([self.selected_index])
            self.on_theme_selected(self.viewport, path)
            return True
        return False

    def move_selection_2d(self, keyval):
        model = self.viewport.get_model()
        if not model:
            return

        if self.selected_index == -1:
            new_index = 0 if keyval in (Gdk.KEY_Down, Gdk.KEY_Right) else len(model) - 1
        else:
            cols = max(1, self.viewport.get_allocation().width // 108)
            delta = {
                Gdk.KEY_Right: 1,
                Gdk.KEY_Left: -1,
                Gdk.KEY_Down: cols,
                Gdk.KEY_Up: -cols,
            }[keyval]
            new_index = max(0, min(len(model) - 1, self.selected_index + delta))

        self.update_selection(new_index)

    def update_selection(self, index: int):
        self.viewport.unselect_all()
        path = Gtk.TreePath.new_from_indices([index])
        self.viewport.select_path(path)
        self.viewport.scroll_to_path(path, False, 0.5, 0.5)
        self.selected_index = index

    def _start_thumbnail_thread(self):
        GLib.Thread.new("thumbnail-loader", self._preload_thumbnails, None)

    def _preload_thumbnails(self, _):
        for theme_name in self.themes_data:
            self.executor.submit(self._process_theme, theme_name)

    def _reload_themes(self):
        self.thumbnails = []
        self.thumbnail_queue = []
        self.viewport.get_model().clear()
        self._start_thumbnail_thread()

    def _process_theme(self, theme_name):
        if theme_name not in self.themes_data:
            return

        theme_info = self.themes_data[theme_name]
        logo_path = theme_info.get("logo", "")

        if not logo_path or not os.path.exists(logo_path):
            logger.warning(f"Logo not found for theme {theme_name}")
            return

        try:
            # Загружаем изображение с сохранением альфа-канала
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(logo_path)

            # Если изображение не имеет альфа-канала, добавляем его
            if not pixbuf.get_has_alpha():
                pixbuf = pixbuf.add_alpha(False, 0, 0, 0)

            # Создаем квадратное изображение с прозрачным фоном
            size = max(pixbuf.get_width(), pixbuf.get_height())
            result = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, size, size)

            # Заливаем полностью прозрачным
            result.fill(0x00000000)

            # Центрируем оригинальное изображение
            x = (size - pixbuf.get_width()) // 2
            y = (size - pixbuf.get_height()) // 2
            pixbuf.copy_area(
                0, 0, pixbuf.get_width(), pixbuf.get_height(), result, x, y
            )

            # Добавляем скругленные углы
            result = self._apply_rounded_corners(result, 15)

            # Масштабируем до нужного размера
            result = result.scale_simple(96, 96, GdkPixbuf.InterpType.BILINEAR)

            self.thumbnail_queue.append((result, theme_name))
            GLib.idle_add(self._process_batch)
        except Exception as e:
            logger.error(f"Error processing theme {theme_name} logo: {e}")

    def _process_batch(self):
        processed = []
        for pixbuf, theme_name in self.thumbnail_queue:
            self.thumbnails.append((pixbuf, theme_name))
            processed.append(
                (pixbuf, theme_name, theme_name)
            )  # Добавляем название в третью колонку

        if processed:
            for item in processed:
                self.list_store.append(item)
        self.thumbnail_queue = []

    @staticmethod
    def _apply_rounded_corners(pixbuf, radius):
        # Конвертируем GdkPixbuf в PIL Image
        width = pixbuf.get_width()
        height = pixbuf.get_height()
        data = pixbuf.get_pixels()
        stride = pixbuf.get_rowstride()
        mode = "RGBA" if pixbuf.get_has_alpha() else "RGB"

        img = Image.frombytes(mode, (width, height), data, "raw", mode, stride)

        # Создаем маску с закругленными углами
        mask = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([0, 0, width, height], radius, fill=255)

        # Применяем маску к альфа-каналу
        if img.mode == "RGBA":
            r, g, b, a = img.split()
            img = Image.merge("RGBA", (r, g, b, ImageChops.multiply(a, mask)))
        else:
            img.putalpha(mask)

        # Конвертируем обратно в GdkPixbuf
        data = img.tobytes()
        return GdkPixbuf.Pixbuf.new_from_bytes(
            GLib.Bytes.new(data),
            GdkPixbuf.Colorspace.RGB,
            True,
            8,
            width,
            height,
            width * 4,
        )

    def on_search_entry_focus_out(self, widget, _):
        if self.get_mapped():
            widget.grab_focus()
        return False
