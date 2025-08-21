import json
import subprocess
from copy import deepcopy
from pathlib import Path

from loguru import logger
from pydantic import ValidationError

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
            logger.info(
                "[Config] Keyboard shortcuts already included in Hyprland configuration."
            )

    # Reload Hyprland configuration
    try:
        subprocess.run(["hyprctl", "reload"], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to send notification: {e}")


def _deep_merge_dicts(d1: dict, d2: dict) -> dict:
    """Recursively merges d2 into a copy of d1."""
    result = deepcopy(d1)
    for key, value in d2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def _get_nested_value(d: dict, path: tuple):
    for key in path:
        if not isinstance(d, dict):
            return None
        d = d.get(key)
    return d


def _set_nested_value(d: dict, path: tuple, value):
    for key in path[:-1]:
        if key not in d or not isinstance(d[key], dict):
            d[key] = {}
        d = d[key]
    if path:
        d[path[-1]] = value


def load_config(path: Path) -> Config:
    default_config = cnst.DEFAULT_CONFIG
    user_config = {}

    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                user_config = json.load(f)
        except json.JSONDecodeError as e:
            logger.warning(
                f"Warning: The config file '{path}' is not valid JSON. Using default values. Error: {e}"
            )

    merged_config = _deep_merge_dicts(default_config, user_config)

    try:
        return Config.model_validate(merged_config)
    except ValidationError as e:
        logger.warning(
            "Invalid values found in configuration. Reverting invalid fields to their default values."
        )

        error_locations = [error["loc"] for error in e.errors()]

        for loc in error_locations:
            default_value = _get_nested_value(default_config, loc)
            _set_nested_value(merged_config, loc, default_value)
            field_path = ".".join(map(str, loc))
            logger.info(f"Reverted '{field_path}' to its default value.")

        try:
            return Config.model_validate(merged_config)
        except ValidationError as final_e:
            logger.error(
                "Configuration is still invalid after attempting to fix. "
                f"Using the default configuration. Please check your config file. Error: {final_e}"
            )
            return Config.model_validate(default_config)


cfg: Config = load_config(cnst.APP_CONFIG_PATH)
