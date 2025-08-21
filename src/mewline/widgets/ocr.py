import subprocess
import traceback

import pytesseract
from gi.repository import Gdk
from gi.repository import Gtk
from loguru import logger

from mewline import constants as cnst
from mewline.config import cfg
from mewline.shared.widget_container import ButtonWidget
from mewline.utils.misc import check_tools_available
from mewline.utils.misc import ttl_lru_cache
from mewline.utils.widget_utils import text_icon


class OCRWidget(ButtonWidget):
    """A widget that provides Optical Character Recognition functionality.

    Left-click to select an area and copy recognized text to clipboard.
    Right-click to select the OCR language from available tesseract language packs.
    """

    def __init__(self, **kwargs):
        super().__init__(name="ocr", **kwargs)
        self.config = cfg.modules.ocr
        langs = self.get_available_languages()
        combined_langs = self.get_combined_languages(langs)
        all_langs = langs + combined_langs
        self.current_lang = (
            self.config.default_lang
            if self.config.default_lang in all_langs
            else langs[0]
        )

        self.children = text_icon(
            self.config.icon, self.config.icon_size, style_classes="panel-text-icon"
        )

        self.connect("button-press-event", self.on_button_press)

        if self.config.tooltip:
            self.set_tooltip_text("Left click to OCR, right click to select language")

    def on_button_press(self, _, event):
        if event.button == 3:
            self.show_language_menu()
            return

        try:
            if not self._check_prerequisites():
                return

            if (selection := self._get_selection_area()) is None:
                return

            if not self._capture_screenshot(selection):
                return

            if (text := self._extract_text_from_image()) is None:
                return

            self._handle_clipboard(text)

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            logger.debug(traceback.format_exc())
        finally:
            self._cleanup_temp_files()

    def _check_prerequisites(self):
        """Checking installed dependencies."""
        if check_tools_available(["slurp", "grim"]):
            return True

        logger.error("Required tools (slurp/grim) are not installed")
        return False

    def _get_selection_area(self, timeout=30):
        """Obtaining the selection area from the user."""
        try:
            result = subprocess.run(
                ["slurp"],
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode == 1:
                logger.debug("User cancelled area selection")
                return None
            if result.returncode != 0:
                logger.error(
                    f"Slurp error [{result.returncode}]: {result.stderr.strip()}"
                )
                return None

            if not (selection := result.stdout.strip()):
                logger.debug("Empty selection area")
                return None

            return selection

        except subprocess.TimeoutExpired:
            logger.error("Area selection timed out")
            return None

    def _capture_screenshot(self, selection, timeout=10):
        """Capture a screenshot of the selected area."""
        path_to_img = cnst.APP_CACHE_DIRECTORY / "ocr.png"

        try:
            subprocess.run(
                ["grim", "-g", selection, str(path_to_img)],
                check=True,
                timeout=timeout,
            )
            return path_to_img if path_to_img.exists() else None

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to capture area: {e}")
        except subprocess.TimeoutExpired:
            logger.error("Screenshot capture timed out")

        return None

    def _extract_text_from_image(self):
        """Extract text from an image."""
        path_to_img = cnst.APP_CACHE_DIRECTORY / "ocr.png"

        try:
            text = pytesseract.image_to_string(
                str(path_to_img), lang=self.current_lang
            ).strip()

            if not text:
                logger.warning("No text recognized in selected area")
                return None

            return text

        except pytesseract.TesseractError as e:
            logger.error(f"OCR Error: {e}")
            return None

    def _handle_clipboard(self, text):
        """Working with the clipboard."""
        try:
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(text, -1)
            clipboard.store()
            logger.info("Text successfully copied to clipboard")
            return True

        except Exception as e:
            logger.error(f"Clipboard error: {e}")
            return False

    def _cleanup_temp_files(self):
        """Очистка временных файлов."""
        path_to_img = cnst.APP_CACHE_DIRECTORY / "ocr.png"
        try:
            if path_to_img.exists():
                path_to_img.unlink()
        except OSError as e:
            logger.error(f"Failed to clean up temp file: {e}")

    def show_language_menu(self):
        menu = Gtk.Menu()
        menu.set_name("ocr-menu")  # For CSS targeting

        # Get available languages
        langs = self.get_available_languages()
        combined_langs = self.get_combined_languages(langs)

        # Add single languages
        for lang in langs:
            if lang != "osd":  # Skip the OSD option
                item = Gtk.MenuItem(label=lang)
                label = item.get_child()
                label.set_name("ocr-menu-item")  # For CSS targeting
                if lang == self.current_lang:
                    item.get_style_context().add_class("selected")
                item.connect("activate", self.on_language_selected, lang)
                menu.append(item)

        # Add separator if there are combined languages
        if combined_langs:
            separator = Gtk.SeparatorMenuItem()
            menu.append(separator)

            # Add combined languages
            for lang_combo in combined_langs:
                item = Gtk.MenuItem(label=lang_combo)
                label = item.get_child()
                label.set_name("ocr-menu-item")  # For CSS targeting
                if lang_combo == self.current_lang:
                    item.get_style_context().add_class("selected")
                item.connect("activate", self.on_language_selected, lang_combo)
                menu.append(item)

        menu.show_all()
        menu.popup_at_widget(self, Gdk.Gravity.SOUTH, Gdk.Gravity.NORTH, None)

    @ttl_lru_cache(600, 10)
    def get_available_languages(self):
        return pytesseract.get_languages()

    def get_combined_languages(self, available_langs):
        """Get available combined language options based on installed languages."""
        combined = []

        # Check if both Russian and English are available
        if "rus" in available_langs and "eng" in available_langs:
            combined.append("rus+eng")

        # Add other useful combinations if languages are available
        if "deu" in available_langs and "eng" in available_langs:
            combined.append("deu+eng")

        if "fra" in available_langs and "eng" in available_langs:
            combined.append("fra+eng")

        return combined

    def on_language_selected(self, _, lang):
        self.current_lang = lang
        self.set_tooltip_text(f"OCR ({lang})")
