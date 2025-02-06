import json
import setproctitle
from fabric import Application
from fabric.utils import monitor_file
from loguru import logger

from . import constants as cnst
from .config import cfg, generate_default_config
from .utils.theming import copy_theme, process_and_apply_css
from .widgets.screen_corners import ScreenCorners
from .widgets.status_bar import StatusBar
from .widgets.dynamic_island import DynamicIsland


def disable_logging():
    for log in [
        "fabric.hyprland.widgets",
        "fabric.audio.service",
        "fabric.bluetooth.service",
    ]:
        logger.disable(log)


def generate():
    generate_default_config()


def main():
    disable_logging()

    ##==> Creating App
    ##############################
    dynamic_island = DynamicIsland()
    screen_corners = ScreenCorners()
    status_bar = StatusBar(dynamic_island)

    app = Application(cnst.APPLICATION_NAME, screen_corners, status_bar, dynamic_island)
    setproctitle.setproctitle(cnst.APPLICATION_NAME)
    cnst.APP_CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)

    ##==> Theming
    ##############################
    copy_theme(
        path=cnst.MEWLINE_THEMES_FOLDER / (cfg.theme.name + ".scss")
    )

    main_css_file = monitor_file(str(cnst.STYLES_FOLDER))
    main_css_file.connect(
        "changed", lambda *_: process_and_apply_css(app)
    )

    process_and_apply_css(app)

    ##==> Run the application
    ##############################
    app.run()


if __name__ == "__main__":
    main()
