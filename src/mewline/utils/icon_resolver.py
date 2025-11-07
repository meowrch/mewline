import contextlib
import json
import os
import re

from fabric.utils import DesktopApp
from fabric.utils import get_desktop_applications
from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import Gtk

from mewline import constants as cnst

# Lazy app registry
_APP_MAP: dict[str, DesktopApp] | None = None


def _build_app_identifiers_map(apps) -> dict[str, DesktopApp]:
    mapping: dict[str, DesktopApp] = {}
    for app in apps or []:
        with contextlib.suppress(Exception):
            if getattr(app, "name", None):
                mapping[app.name.lower()] = app
            if getattr(app, "display_name", None):
                mapping[app.display_name.lower()] = app
            if getattr(app, "window_class", None):
                mapping[app.window_class.lower()] = app
            if getattr(app, "executable", None):
                mapping[app.executable.split("/")[-1].lower()] = app
            if getattr(app, "command_line", None):
                mapping[app.command_line.split()[0].split("/")[-1].lower()] = app
    return mapping


def _ensure_app_registry() -> dict[str, DesktopApp]:
    global _APP_MAP
    if _APP_MAP is None:
        apps = get_desktop_applications()
        _APP_MAP = _build_app_identifiers_map(apps)
    return _APP_MAP


def find_app(ident: str) -> DesktopApp | None:
    if not ident:
        return None
    ident = ident.lower()
    app = _ensure_app_registry().get(ident)
    if app:
        return app
    # Try normalized class without suffixes
    for suf in (".bin", ".exe", ".so", "-bin", "-gtk"):
        if ident.endswith(suf):
            ident2 = ident[: -len(suf)]
            app = _ensure_app_registry().get(ident2)
            if app:
                return app
    return None


def _load_icon_cache() -> dict[str, str]:
    cache: dict[str, str] = {}
    with contextlib.suppress(Exception):
        if cnst.ICONS_CACHE_FILE.exists():
            with open(cnst.ICONS_CACHE_FILE, encoding="utf-8") as f:
                cache = json.load(f)
    return cache


def _save_icon_cache(cache: dict[str, str]) -> None:
    with contextlib.suppress(Exception):
        cnst.APP_CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)
        with open(cnst.ICONS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)


def resolve_icon_name(app_id: str) -> str | None:
    """Theme-first resolver with cache: app_id -> icon name.
    Order: cache -> theme(app_id) -> theme(app_id-desktop) -> .desktop Icon.
    """  # noqa: D205
    app_id = (app_id or "").lower()
    cache = _load_icon_cache()
    if app_id in cache:
        return cache[app_id]

    try:
        theme = Gtk.IconTheme.get_default()
        resolved: str | None = None
        if theme:
            if theme.has_icon(app_id):
                resolved = app_id
            else:
                alt = f"{app_id}-desktop"
                if theme.has_icon(alt):
                    resolved = alt
        if resolved is None:
            # Search .desktop files
            candidates = []
            user_apps = os.path.join(GLib.get_user_data_dir(), "applications")
            if os.path.isdir(user_apps):
                candidates.append(user_apps)
            for d in GLib.get_system_data_dirs():
                p = os.path.join(d, "applications")
                if os.path.isdir(p):
                    candidates.append(p)
            for base in candidates:
                files = []
                with contextlib.suppress(Exception):
                    files = os.listdir(base)
                matches = [f for f in files if app_id in f.lower()]
                if not matches:
                    parts = list(filter(None, re.split(r"[-._\s]", app_id)))
                    for w in parts:
                        sub = [f for f in files if w in f.lower()]
                        if sub:
                            matches = sub
                            break
                if not matches:
                    continue
                desktop_path = os.path.join(base, matches[0])
                with open(desktop_path, encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if line.startswith("Icon="):
                            resolved = line.strip()[5:]
                            break
                if resolved:
                    break
        if resolved:
            cache[app_id] = resolved
            _save_icon_cache(cache)
            return resolved
    except Exception:
        ...
    return None


def load_pixbuf_from_theme(icon_name: str, size: int) -> GdkPixbuf.Pixbuf | None:
    try:
        theme = Gtk.IconTheme.get_default()
        if theme and icon_name and theme.has_icon(icon_name):
            return theme.load_icon(icon_name, size, Gtk.IconLookupFlags.FORCE_SIZE)
    except Exception:
        ...
    return None


def get_icon_pixbuf_for_app(
    app_id: str, size: int
) -> tuple[GdkPixbuf.Pixbuf | None, str, str | None]:
    """Return (pixbuf, source, name).
    source in {'theme','desktop-app','generic','none'}.
    """  # noqa: D205
    app_id_l = (app_id or "").lower()

    # Theme-first universal resolver
    name = resolve_icon_name(app_id_l)
    if name:
        pix = load_pixbuf_from_theme(name, size)
        if pix is not None:
            return pix, "theme", name

    # DesktopApp fallback
    app = find_app(app_id_l)
    if app:
        with contextlib.suppress(Exception):
            pix = app.get_icon_pixbuf(size=size)
            if pix:
                iname = getattr(app, "icon_name", None) or getattr(app, "name", None)
                return pix, "desktop-app", iname

    # Generic fallback
    with contextlib.suppress(Exception):
        pix = load_pixbuf_from_theme("application-x-executable-symbolic", size)
        if pix:
            return pix, "generic", "application-x-executable-symbolic"

    return None, "none", None
