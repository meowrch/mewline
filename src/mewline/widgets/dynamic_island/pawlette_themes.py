import math
import os
import random as random_mod
import re
import subprocess
import tomllib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock

from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.entry import Entry
from fabric.widgets.image import Image as FabricImage
from fabric.widgets.label import Label
from fabric.widgets.scrolledwindow import ScrolledWindow
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import Gtk
from loguru import logger
from PIL import Image
from PIL import ImageChops
from PIL import ImageDraw

from mewline import constants as cnst
from mewline.widgets.dynamic_island.base import BaseDiWidget

# ---------------------------------------------------------------------------
#   Paths & constants
# ---------------------------------------------------------------------------
_ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets"
_THEMES_DIR = cnst.XDG_DATA_HOME / "pawlette" / "themes"
_DYNAMIC_STATE_FILE = cnst.XDG_STATE_HOME / "meowrch" / "dynamic_theme"
_CURRENT_WALL = cnst.DEFAULT_CURRENT_WALL_PATH

_DEFAULT_LOGO = _ASSETS_DIR / "default-theme-logo.png"
_RANDOM_ICON = _ASSETS_DIR / "random.png"
_DYNAMIC_ON_ICON = _ASSETS_DIR / "dynamic-theme-on-logo.png"
_DYNAMIC_OFF_ICON = _ASSETS_DIR / "dynamic-theme-off-logo.png"

# Sentinel names for special grid items
_SPECIAL_DYNAMIC = "__dynamic_theme__"
_SPECIAL_RANDOM = "__random_theme__"


# ---------------------------------------------------------------------------
#   Helpers
# ---------------------------------------------------------------------------
def _read_dynamic_state() -> bool:
    """Return True if dynamic theme is enabled."""
    try:
        return _DYNAMIC_STATE_FILE.read_text().strip() == "1"
    except Exception:
        return False


def _write_dynamic_state(enabled: bool) -> None:
    _DYNAMIC_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _DYNAMIC_STATE_FILE.write_text("1" if enabled else "0")


def _parse_variants(theme_path: str) -> dict[str, str | None]:
    """Parse colors.toml → {variant_name: primary_color_hex}.

    Always includes 'default'; returns empty dict when no file found.
    """
    toml_path = Path(theme_path) / "colors.toml"
    if not toml_path.exists():
        return {}

    try:
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        return {}

    result: dict[str, str | None] = {}

    colors = data.get("colors", {})
    default_color = (
        colors.get("color_primary")
        or colors.get("color_border_active")
        or colors.get("color_cursor")
    )
    result["default"] = default_color

    for name, section in data.get("variants", {}).items():
        color = (
            section.get("color_primary")
            or section.get("color_border_active")
            or section.get("color_cursor")
        )
        result[name] = color

    return result


def _is_valid_hex(color: str | None) -> bool:
    if not color:
        return False
    return bool(re.match(r"^#[0-9a-fA-F]{6}$", color))


# ---------------------------------------------------------------------------
#   Widget
# ---------------------------------------------------------------------------
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

        # {theme_name: [variant, ...]} — parsed from `pawlette list`
        self.themes_data: dict[str, list[str]] = {}
        self.thumbnails: list[tuple] = []  # (pixbuf, display, internal)
        self.thumbnail_queue: list[tuple] = []
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.selected_index = -1
        self._current_theme_name: str | None = None
        self._reload_generation = 0  # stale-batch guard

        if not self._check_pawlette_installed():
            logger.error("pawlette command not found")
            return

        self.themes_data = self._parse_pawlette_list()

        # ======================== Main View ========================
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
        self.viewport.connect("item-activated", self._on_grid_item_activated)
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
            notify_text=lambda entry, *_: self._arrange_main_viewport(entry.get_text()),
            on_key_press_event=self._on_search_entry_key_press,
        )
        self.search_entry.props.xalign = 0.5
        self.search_entry.connect("focus-out-event", self._on_focus_out)

        self.header_box = CenterBox(
            name="header-box",
            spacing=8,
            orientation="h",
            center_children=[self.search_entry],
        )

        self.main_view = Box(
            name="pawlette-main-view",
            orientation="v",
            spacing=10,
            h_expand=True,
            v_expand=True,
        )
        self.main_view.add(self.header_box)
        self.main_view.add(self.scrolled_window)

        # ==================== Variant Picker View ====================
        self.variant_back_btn = Button(
            name="variant-back-btn",
            child=Box(
                orientation="h",
                spacing=6,
                children=[
                    FabricImage(icon_name="go-previous-symbolic", icon_size=16),
                    Label(label="Back"),
                ],
            ),
            on_clicked=lambda *_: self._show_main_view(),
        )

        self.variant_title_label = Label(
            name="variant-title-label",
            label="Select Accent",
        )

        self.variant_header = CenterBox(
            name="variant-header",
            spacing=8,
            orientation="h",
            start_children=[self.variant_back_btn],
            center_children=[self.variant_title_label],
        )

        self.variant_list_box = Gtk.ListBox(name="variant-list")
        self.variant_list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.variant_list_box.connect("row-activated", self._on_variant_row_activated)

        self.variant_scrolled = ScrolledWindow(
            name="variant-scrolled",
            h_expand=True,
            v_expand=True,
            child=self.variant_list_box,
        )

        self.variant_view = Box(
            name="pawlette-variant-view",
            orientation="v",
            spacing=10,
            h_expand=True,
            v_expand=True,
        )
        self.variant_view.add(self.variant_header)
        self.variant_view.add(self.variant_scrolled)

        # ======================= View Stack =======================
        self.view_stack = Gtk.Stack(name="pawlette-view-stack")
        self.view_stack.set_transition_type(
            Gtk.StackTransitionType.SLIDE_LEFT_RIGHT,
        )
        self.view_stack.set_transition_duration(200)
        self.view_stack.add_named(self.main_view, "main")
        self.view_stack.add_named(self.variant_view, "variants")

        self.add(self.view_stack)
        self._reload_themes()
        self.show_all()
        self.search_entry.grab_focus()

    # ================================================================
    #   Pawlette CLI helpers
    # ================================================================
    def _check_pawlette_installed(self):
        try:
            subprocess.run(["which", "pawlette"], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False

    @staticmethod
    def _parse_pawlette_list() -> dict[str, list[str]]:
        """Run `pawlette list` and parse output.

        Output format:  theme-name (var1, var2, ...)
                        theme-without-variants
        Returns {name: [variant, ...]} (empty list = no variants).
        """
        try:
            output = subprocess.check_output(
                ["pawlette", "list"],
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except Exception as e:
            logger.error(f"Failed to run 'pawlette list': {e}")
            return {}

        result: dict[str, list[str]] = {}
        for line in output.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            # "catppuccin-mocha (blue, flamingo, green)"
            match = re.match(r"^(\S+)\s*(?:\(([^)]+)\))?$", line)
            if match:
                name = match.group(1)
                variants_raw = match.group(2)
                variants = (
                    [v.strip() for v in variants_raw.split(",") if v.strip()]
                    if variants_raw
                    else []
                )
                result[name] = variants
        return result

    # ================================================================
    #   Lifecycle (called by DynamicIsland)
    # ================================================================
    def open_widget_from_di(self) -> None:
        self._show_main_view()
        GLib.Thread.new("pawlette_themes_checking_for_changes", self._check_changes)

    def _check_changes(self) -> None:
        with self.checking_changes_lock:
            new_themes = self._parse_pawlette_list()

            if not self.themes_data:
                self.themes_data = new_themes
                self._reload_themes()
                return

            if set(self.themes_data.keys()) != set(new_themes.keys()):
                self.themes_data = new_themes
                self._reload_themes()

    # ================================================================
    #   Main view — theme grid
    # ================================================================
    def _show_main_view(self):
        self.view_stack.set_visible_child_name("main")
        self.search_entry.set_text("")
        self.search_entry.grab_focus()
        self.selected_index = -1

    def _arrange_main_viewport(self, query: str = ""):
        self.list_store.clear()
        q = query.casefold()
        specials = []
        themes = []
        for pixbuf, display, internal in self.thumbnails:
            if internal in (_SPECIAL_DYNAMIC, _SPECIAL_RANDOM):
                specials.append((pixbuf, display, internal))
            elif q in display.casefold():
                themes.append((pixbuf, display, internal))
        themes.sort(key=lambda x: x[1].lower())
        for item in specials + themes:
            self.list_store.append(list(item))
        if query.strip() and self.list_store:
            # Select first real theme (skip specials)
            idx = min(len(specials), len(self.list_store) - 1)
            self.update_selection(idx)

    def _on_grid_item_activated(self, iconview, path):
        internal_name = iconview.get_model()[path][2]

        if internal_name == _SPECIAL_DYNAMIC:
            self._toggle_dynamic_theme()
            return
        if internal_name == _SPECIAL_RANDOM:
            GLib.Thread.new("pawlette_random", self._apply_random)
            return

        if internal_name not in self.themes_data:
            return

        theme_variants = self.themes_data[internal_name]

        if not theme_variants:
            # No variants — apply directly
            GLib.Thread.new(
                "pawlette_apply",
                self._execute_apply,
                internal_name,
                "default",
            )
        else:
            # Build variant → color map from colors.toml
            theme_path = str(_THEMES_DIR / internal_name)
            colors = _parse_variants(theme_path)
            # Ensure all variants from `pawlette list` are present
            for v in theme_variants:
                if v not in colors:
                    colors[v] = None
            self._show_variant_picker(internal_name, colors)

    # ================================================================
    #   Dynamic theme toggle
    # ================================================================
    def _toggle_dynamic_theme(self):
        is_on = _read_dynamic_state()
        _write_dynamic_state(not is_on)

        if not is_on and _CURRENT_WALL.exists():
            GLib.Thread.new(
                "pawlette_dynamic",
                self._run_pawlette_apply_image,
                str(_CURRENT_WALL),
            )

        # Swap dynamic icon in-place — no full reload needed
        self._update_dynamic_icon()

    @staticmethod
    def _run_pawlette_apply_image(wall_path):
        try:
            subprocess.run(
                ["pawlette", "apply", "image", wall_path],
                check=True,
                capture_output=True,
            )
        except Exception as e:
            logger.error(f"Failed to apply dynamic wallpaper theme: {e}")

    # ================================================================
    #   Random theme
    # ================================================================
    def _apply_random(self):
        if not self.themes_data:
            return
        theme_name = random_mod.choice(list(self.themes_data.keys()))  # noqa: S311
        theme_variants = self.themes_data[theme_name]
        if theme_variants:
            all_options = ["default", *theme_variants]
            variant = random_mod.choice(all_options)  # noqa: S311
        else:
            variant = "default"
        self._execute_apply(theme_name, variant)

    # ================================================================
    #   Apply
    # ================================================================
    def _execute_apply(self, theme_name: str, variant: str = "default"):
        was_dynamic_on = _read_dynamic_state()
        _write_dynamic_state(False)
        try:
            cmd = ["pawlette", "apply", "theme", theme_name]
            if variant and variant != "default":
                cmd.extend(["--variant", variant])
            subprocess.run(cmd, check=True)
            logger.info(f"Theme {theme_name} (variant={variant}) applied")
            # Only update dynamic icon if state changed (dynamic was on, now off)
            if was_dynamic_on:
                self._update_dynamic_icon()
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to apply theme {theme_name}: {e}")

    # ================================================================
    #   Variant picker
    # ================================================================
    def _show_variant_picker(self, theme_name: str, variants: dict[str, str | None]):
        self._current_theme_name = theme_name

        display = theme_name.replace("-", " ").title()
        self.variant_title_label.set_label(display)

        # Clear old rows
        for child in self.variant_list_box.get_children():
            self.variant_list_box.remove(child)

        for variant_name, color_hex in variants.items():
            row = self._create_variant_row(variant_name, color_hex)
            self.variant_list_box.add(row)

        self.variant_list_box.show_all()
        self.view_stack.set_visible_child_name("variants")

        first = self.variant_list_box.get_row_at_index(0)
        if first:
            self.variant_list_box.select_row(first)
            first.grab_focus()

    def _create_variant_row(
        self, variant_name: str, color_hex: str | None
    ) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow(name="variant-row")
        row._variant_name = variant_name

        hbox = Box(orientation="h", spacing=12, h_expand=True)
        hbox.set_margin_top(8)
        hbox.set_margin_bottom(8)
        hbox.set_margin_start(16)
        hbox.set_margin_end(16)

        # Color indicator
        if _is_valid_hex(color_hex):
            dot = Gtk.DrawingArea(name="variant-color-dot")
            dot.set_size_request(20, 20)
            dot.connect("draw", self._draw_color_dot, color_hex)
            hbox.add(dot)
        else:
            spacer = Box()
            spacer.set_size_request(20, 20)
            hbox.add(spacer)

        label_text = variant_name.replace("-", " ").replace("_", " ").title()
        label = Label(
            name="variant-label",
            label=label_text,
            h_expand=True,
            h_align="start",
        )
        hbox.add(label)

        row.add(hbox)
        return row

    @staticmethod
    def _draw_color_dot(widget, cr, color_hex):
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        radius = min(w, h) / 2.0

        r = int(color_hex[1:3], 16) / 255.0
        g = int(color_hex[3:5], 16) / 255.0
        b = int(color_hex[5:7], 16) / 255.0

        cr.arc(w / 2.0, h / 2.0, radius - 1, 0, 2 * math.pi)
        cr.set_source_rgb(r, g, b)
        cr.fill()
        return False

    def _on_variant_row_activated(self, _listbox, row):
        if not row or not self._current_theme_name:
            return
        variant_name = row._variant_name
        GLib.Thread.new(
            "pawlette_apply_variant",
            self._execute_apply,
            self._current_theme_name,
            variant_name,
        )

    # ================================================================
    #   Keyboard navigation
    # ================================================================
    def _on_search_entry_key_press(self, widget, event):
        if self.view_stack.get_visible_child_name() == "variants":
            if event.keyval == Gdk.KEY_Escape:
                self._show_main_view()
                return True
            return False

        if event.keyval in (Gdk.KEY_Up, Gdk.KEY_Down, Gdk.KEY_Left, Gdk.KEY_Right):
            self._move_selection_2d(event.keyval)
            return True
        elif (
            event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter)
            and self.selected_index != -1
        ):
            path = Gtk.TreePath.new_from_indices([self.selected_index])
            self._on_grid_item_activated(self.viewport, path)
            return True
        return False

    def _move_selection_2d(self, keyval):
        model = self.viewport.get_model()
        if not model:
            return

        if self.selected_index == -1:
            new_index = 0 if keyval in (Gdk.KEY_Down, Gdk.KEY_Right) else len(model) - 1
        else:
            cols = self._get_columns()
            delta = {
                Gdk.KEY_Right: 1,
                Gdk.KEY_Left: -1,
                Gdk.KEY_Down: cols,
                Gdk.KEY_Up: -cols,
            }[keyval]
            new_index = max(0, min(len(model) - 1, self.selected_index + delta))

        self.update_selection(new_index)

    def _get_columns(self) -> int:
        """Return the real number of columns the IconView currently lays out.

        The previous ``width // 150`` heuristic did not match GTK's actual
        layout (which depends on item/label width, padding, spacing and
        margins), so it was frequently off by one. That made Down jump
        down-and-right and Up jump up-and-left. Instead, derive the column
        count from real item geometry: the index of the first item that wraps
        onto the second row equals the number of columns.
        """
        model = self.viewport.get_model()
        n = len(model) if model is not None else 0
        if n <= 1:
            return 1

        first_path = Gtk.TreePath.new_from_indices([0])
        ok, first_rect = self.viewport.get_cell_rect(first_path, None)
        if not ok:
            return max(1, self.viewport.get_allocation().width // 150)

        threshold = first_rect.height // 2
        for i in range(1, n):
            path = Gtk.TreePath.new_from_indices([i])
            ok, rect = self.viewport.get_cell_rect(path, None)
            if not ok:
                continue
            # First item whose top drops below row 0 starts the second row,
            # so its index is the number of columns in a full row.
            if rect.y - first_rect.y > threshold:
                return i
        return n

    def update_selection(self, index: int):
        self.viewport.unselect_all()
        path = Gtk.TreePath.new_from_indices([index])
        self.viewport.select_path(path)
        self.viewport.scroll_to_path(path, False, 0.5, 0.5)
        self.selected_index = index

    def _on_focus_out(self, widget, _):
        if self.get_mapped() and self.view_stack.get_visible_child_name() == "main":
            widget.grab_focus()
        return False

    # ================================================================
    #   Thumbnail loading
    # ================================================================
    def _update_dynamic_icon(self):
        """Swap the Dynamic icon pixbuf in list_store and thumbnails in-place."""
        dyn_on = _read_dynamic_state()
        icon_path = str(_DYNAMIC_ON_ICON if dyn_on else _DYNAMIC_OFF_ICON)
        if not os.path.exists(icon_path):
            return
        try:
            new_pixbuf = self._load_and_process_logo(icon_path)
        except Exception:
            return
        if not new_pixbuf:
            return

        # Update thumbnails list
        for i, (_pixbuf, display, internal) in enumerate(self.thumbnails):
            if internal == _SPECIAL_DYNAMIC:
                self.thumbnails[i] = (new_pixbuf, display, internal)
                break

        # Update list_store row by iterating and matching
        tree_iter = self.list_store.get_iter_first()
        while tree_iter is not None:
            if self.list_store.get_value(tree_iter, 2) == _SPECIAL_DYNAMIC:
                self.list_store.set_value(tree_iter, 0, new_pixbuf)
                break
            tree_iter = self.list_store.iter_next(tree_iter)

    def _reload_themes(self):
        self._reload_generation += 1
        gen = self._reload_generation
        self.thumbnails = []
        self.thumbnail_queue = []
        self.list_store.clear()
        self._load_special_items()
        self._start_thumbnail_thread(gen)

    def _load_special_items(self):
        dyn_on = _read_dynamic_state()
        dyn_icon = _DYNAMIC_ON_ICON if dyn_on else _DYNAMIC_OFF_ICON
        self._add_special_icon(str(dyn_icon), "Dynamic", _SPECIAL_DYNAMIC)
        self._add_special_icon(str(_RANDOM_ICON), "Random", _SPECIAL_RANDOM)

    def _add_special_icon(self, icon_path: str, display: str, internal: str):
        if not os.path.exists(icon_path):
            logger.warning(f"Special icon not found: {icon_path}")
            return
        try:
            pixbuf = self._load_and_process_logo(icon_path)
            if pixbuf:
                self.thumbnails.append((pixbuf, display, internal))
                self.list_store.append([pixbuf, display, internal])
        except Exception as e:
            logger.error(f"Error loading special icon {icon_path}: {e}")

    def _start_thumbnail_thread(self, gen: int):
        GLib.Thread.new("thumbnail-loader", self._preload_thumbnails, gen)

    def _preload_thumbnails(self, gen):
        for theme_name in self.themes_data:
            self.executor.submit(self._process_theme, theme_name, gen)

    def _process_theme(self, theme_name, gen):
        # Stale reload — discard
        if gen != self._reload_generation:
            return

        if theme_name not in self.themes_data:
            return

        # Logo lives at $THEMES_DIR/<theme>/logo.png (same as rofi script)
        logo_path = str(_THEMES_DIR / theme_name / "logo.png")

        if not os.path.exists(logo_path):
            logo_path = str(_DEFAULT_LOGO)
            if not os.path.exists(logo_path):
                logger.warning(f"Logo not found for theme {theme_name}")
                return

        try:
            pixbuf = self._load_and_process_logo(logo_path)
            if pixbuf:
                self.thumbnail_queue.append((pixbuf, theme_name, theme_name, gen))
                GLib.idle_add(self._process_batch)
        except Exception as e:
            logger.error(f"Error processing theme {theme_name} logo: {e}")

    def _load_and_process_logo(self, logo_path: str) -> GdkPixbuf.Pixbuf | None:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(logo_path)

        if not pixbuf.get_has_alpha():
            pixbuf = pixbuf.add_alpha(False, 0, 0, 0)

        size = max(pixbuf.get_width(), pixbuf.get_height())
        result = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, size, size)
        result.fill(0x00000000)

        x = (size - pixbuf.get_width()) // 2
        y = (size - pixbuf.get_height()) // 2
        pixbuf.copy_area(0, 0, pixbuf.get_width(), pixbuf.get_height(), result, x, y)

        result = self._apply_rounded_corners(result, 15)
        return result.scale_simple(96, 96, GdkPixbuf.InterpType.BILINEAR)

    def _process_batch(self):
        current_gen = self._reload_generation
        processed = []
        for pixbuf, display, internal, gen in self.thumbnail_queue:
            if gen != current_gen:
                continue  # stale entry — skip
            self.thumbnails.append((pixbuf, display, internal))
            processed.append((pixbuf, display, internal))

        if processed:
            for item in processed:
                self.list_store.append(list(item))
        self.thumbnail_queue = []

    @staticmethod
    def _apply_rounded_corners(pixbuf, radius):
        width = pixbuf.get_width()
        height = pixbuf.get_height()
        data = pixbuf.get_pixels()
        stride = pixbuf.get_rowstride()
        mode = "RGBA" if pixbuf.get_has_alpha() else "RGB"

        img = Image.frombytes(mode, (width, height), data, "raw", mode, stride)

        mask = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([0, 0, width, height], radius, fill=255)

        if img.mode == "RGBA":
            r, g, b, a = img.split()
            img = Image.merge("RGBA", (r, g, b, ImageChops.multiply(a, mask)))
        else:
            img.putalpha(mask)

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
