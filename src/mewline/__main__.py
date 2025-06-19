import argparse
import sys

import setproctitle
from fabric import Application
from fabric.utils import monitor_file

from mewline import constants as cnst
from mewline.config import cfg
from mewline.config import change_hypr_config
from mewline.config import generate_default_config
from mewline.utils.setup_loguru import setup_loguru
from mewline.utils.temporary_fixes import *  # noqa: F403
from mewline.utils.theming import copy_theme
from mewline.utils.theming import process_and_apply_css
from mewline.widgets import StatusBar
from mewline.widgets.dynamic_island import DynamicIsland
from mewline.widgets.osd import OSDContainer
from mewline.widgets.screen_corners import ScreenCorners

##==> Настраиваем loguru
################################
setup_loguru()


def create_keybindings():
    change_hypr_config()


def main():
    ##==> Creating App
    ##############################
    widgets = []

    if cfg.options.screen_corners:
        widgets.append(ScreenCorners())

    if cfg.options.osd_enabled:
        widgets.append(OSDContainer())

    widgets.extend((StatusBar(), DynamicIsland()))
    app = Application(cnst.APPLICATION_NAME, *widgets)

    setproctitle.setproctitle(cnst.APPLICATION_NAME)
    cnst.APP_CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    cnst.DIST_FOLDER.mkdir(parents=True, exist_ok=True)

    ##==> Theming
    ##############################
    copy_theme(path=cnst.APP_THEMES_FOLDER / (cfg.theme.name + ".scss"))

    main_css_file = monitor_file(str(cnst.STYLES_FOLDER))
    main_css_file.connect("changed", lambda *_: process_and_apply_css(app))

    process_and_apply_css(app)

    ##==> Run the application
    ##############################
    app.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Mewline: A minimalist status bar for meowrch."
    )
    parser.add_argument(
        "--generate-default-config",
        action="store_true",
        help="Generate a default configuration for mewline",
    )
    parser.add_argument(
        "--create-keybindings",
        action="store_true",
        help="Generating a config for hyprland to use keyboard shortcuts",
    )

    args = parser.parse_args()

    if args.generate_default_config:
        generate_default_config()
        sys.exit(0)
    elif args.create_keybindings:
        create_keybindings()
        sys.exit(0)
    else:
        main()
