import json
from pathlib import Path

from loguru import logger

import mewline.constants as cnst
from mewline.utils.config_structure import Config


def generate_default_config():
    cnst.MEWLINE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    cnst.MEWLINE_THEMES_FOLDER.mkdir(parents=True, exist_ok=True)
    with open(cnst.MEWLINE_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(
            obj=cnst.DEFAULT_CONFIG,
            fp=f,
            indent=4,
        )


def load_config(path: Path) -> Config:
    if not path.exists():
        logger.warning(
            f"Warning: The config file '{path}' was not found. Using default config."
        )
        return Config(**cnst.DEFAULT_CONFIG)

    try:
        with open(path) as f:
            config_dict = json.load(f)
            config = Config(**config_dict)
            return config
    except Exception:
        logger.warning(
            f"Warning: The config file '{path}' is invalid. Using default config."
        )
        return Config(**cnst.DEFAULT_CONFIG)


cfg: Config = load_config(cnst.MEWLINE_CONFIG_PATH)
