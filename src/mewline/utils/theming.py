import re
from pathlib import Path

from fabric import Application
from fabric.utils import exec_shell_command
from loguru import logger

import mewline.constants as cnst
from mewline.errors.settings import ExecutableNotFoundError
from mewline.utils.misc import executable_exists

# Matches top-level SCSS variable declarations: $name: value;
_SCSS_VAR_RE = re.compile(r"^\$([a-zA-Z0-9_-]+)\s*:\s*(.+?)\s*;", re.MULTILINE)


def _parse_scss_vars(content: str) -> dict[str, str]:
    """Return {var_name: value} for every SCSS variable declaration in *content*."""
    return {m.group(1): m.group(2) for m in _SCSS_VAR_RE.finditer(content)}


def process_and_apply_css(app: Application):
    # Raise an error if sass is not found and exit the application
    if not executable_exists("sass"):
        raise ExecutableNotFoundError("sass")

    logger.info("[Main] Compiling CSS")
    exec_shell_command(f"sass {cnst.MAIN_STYLE} {cnst.COMPILED_STYLE} --no-source-map")
    logger.info("[Main] CSS applied")
    app.set_stylesheet_from_file(cnst.COMPILED_STYLE)


def copy_theme(path: Path):
    """Merge default theme variables with user overrides and write to theme.scss.

    Variables present in the user theme file override the defaults; any
    variable not defined by the user falls back to the value from
    default_theme.scss.  This guarantees that newly-introduced variables
    (e.g. $privacy-dot-*) work correctly for existing themes that were
    created before those variables existed.
    """
    if path.stem == "default":
        path = cnst.DEFAULT_THEME_STYLE

    if not path.exists():
        logger.warning(
            f"Warning: The theme file '{path}' was not found. Using default theme."
        )
        path = cnst.DEFAULT_THEME_STYLE

    try:
        with open(cnst.DEFAULT_THEME_STYLE) as f:
            default_vars = _parse_scss_vars(f.read())

        user_vars: dict[str, str] = {}
        if path != cnst.DEFAULT_THEME_STYLE:
            with open(path) as f:
                user_vars = _parse_scss_vars(f.read())

        # User values take priority; missing keys fall back to defaults
        merged = {**default_vars, **user_vars}

        with open(cnst.THEME_STYLE, "w") as f:
            for name, value in merged.items():
                f.write(f"${name}: {value};\n")

        logger.info(f"[THEME] '{path}' applied successfully.")

    except FileNotFoundError:
        logger.error(f"Error: The theme file '{path}' was not found.")
        exit(1)
