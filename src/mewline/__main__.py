import argparse
import sys

import setproctitle
from fabric import Application
from fabric.utils import monitor_file

from mewline import constants as cnst
from mewline.config import cfg
from mewline.config import generate_default_config
from mewline.utils.misc import disable_logging
from mewline.utils.theming import copy_theme
from mewline.utils.theming import process_and_apply_css
from mewline.widgets.dynamic_island import DynamicIsland
from mewline.widgets.screen_corners import ScreenCorners
from mewline.widgets.status_bar import StatusBar


def generate():
    generate_default_config()


def main():
    disable_logging()

    ##==> Creating App
    ##############################
    app = Application(
        cnst.APPLICATION_NAME,
        ScreenCorners(),
        StatusBar(),
        DynamicIsland()
    )

    setproctitle.setproctitle(cnst.APPLICATION_NAME)
    cnst.APP_CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)

    ##==> Theming
    ##############################
    copy_theme(path=cnst.MEWLINE_THEMES_FOLDER / (cfg.theme.name + ".scss"))

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

    args = parser.parse_args()
    if args.generate_default_config:
        generate()
        sys.exit(0)

    main()
