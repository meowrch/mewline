import json
import subprocess
from pathlib import Path

from loguru import logger

import mewline.constants as cnst
from mewline.utils.config_structure import Config


def generate_default_config():
    cnst.APP_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    cnst.APP_THEMES_FOLDER.mkdir(parents=True, exist_ok=True)
    with open(cnst.APP_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(
            obj=cnst.DEFAULT_CONFIG,
            fp=f,
            indent=4,
        )


def generate_hyprconf() -> str:
    """Generate the Hypr configuration string using the current bind_vars."""
    conf = ""
    for key, (prefix, suffix, command) in cnst.KEYBINDINGS.items():
        conf += f'bind = {prefix}, {suffix}, exec, {command} # Press {prefix} + {suffix} to open the "{key}" module.\n'

    return conf


def change_hypr_config():
    """Adding generated keyboard shortcuts to the hyprland configuration."""
    cnst.HYPRLAND_CONFIG_FOLDER.mkdir(parents=True, exist_ok=True)
    mewline_kb_file_path = cnst.HYPRLAND_CONFIG_FOLDER / (
        cnst.APPLICATION_NAME + ".conf"
    )

    with open(mewline_kb_file_path, "w") as f:
        f.write(generate_hyprconf())
        logger.info("[Config] Hyprland configuration file generated.")

    with open(cnst.HYPRLAND_CONFIG_FILE) as f:
        hypr_lines = f.readlines()

    with open(cnst.HYPRLAND_CONFIG_FILE, "a+") as f:
        incl_str = f"source = {mewline_kb_file_path}\n"

        if incl_str not in hypr_lines:
            f.write(f"\n{incl_str}")
            logger.info("[Config] Keyboard shortcuts added to Hyprland configuration.")
        else:
            logger.info("[Config] Keyboard shortcuts already included in Hyprland configuration.")

    # Reload Hyprland configuration
    try:
        subprocess.run(["hyprctl", "reload"], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to send notification: {e}")


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


cfg: Config = load_config(cnst.APP_CONFIG_PATH)
