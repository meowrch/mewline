from pathlib import Path

from fabric import Application
from fabric.utils import exec_shell_command
from loguru import logger

from .. import constants as cnst
from ..errors.settings import ExecutableNotFoundError
from .misc import executable_exists


def process_and_apply_css(app: Application):
    # Raise an error if sass is not found and exit the application
    if not executable_exists("sass"):
        raise ExecutableNotFoundError("sass")

    logger.info("[Main] Compiling CSS")
    exec_shell_command(
        f"sass {cnst.MAIN_STYLE} {cnst.COMPILED_STYLE} --no-source-map"
    )
    logger.info("[Main] CSS applied")
    app.set_stylesheet_from_file(cnst.COMPILED_STYLE)


def copy_theme(path: Path):
    """Function to get the system icon theme

    Args:
        path (Path): path to theme
    """
    if path.stem == "default":
        path = cnst.DEFAULT_THEME_STYLE

    if not path.exists():
        logger.warning(
            f"Warning: The theme file '{path}' was not found."
            "Using default theme."
        )
        path = cnst.DEFAULT_THEME_STYLE

    try:
        with open(path, "r") as f:
            content = f.read()

        with open(cnst.THEME_STYLE, "w") as f:
            f.write(content)
            logger.info(
                f"[THEME] '{path}' applied successfully."
            )

    except FileNotFoundError:
        logger.error(
            f"Error: The theme file '{path}' was not found."
        )
        exit(1)
