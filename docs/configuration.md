# Mewline configuration

The `mewline` configuration file is located at `~/.config/mewline/config.json`.
If the file is missing, the default configuration will be used.
You can generate a default configuration file by running `mewline --generate-default-config`.

Mewline uses a resilient configuration system. If your config contains errors or missing fields, they will be automatically filled or corrected with values from the default configuration to keep the app stable.

## Configuration structure

### `theme`

| Key | Type | Description |
|---|---|---|
| `name` | `str` | Theme name. |

### `options`

| Key | Type | Description |
|---|---|---|
| `screen_corners` | `bool` | Enable rounded screen corners. |
| `intercept_notifications` | `bool` | Intercept system notifications. |
| `osd_enabled` | `bool` | Enable OSD (On-Screen Display). |

### `modules`

#### `osd`

| Key | Type | Description |
|---|---|---|
| `timeout` | `int` | Time in milliseconds before OSD hides. |
| `anchor` | `str` | OSD anchor on screen (e.g. `bottom-center`). |

#### `workspaces`

| Key | Type | Description |
|---|---|---|
| `count` | `int` | Number of workspaces. |
| `hide_unoccupied` | `bool` | Hide empty workspaces. |
| `ignored` | `list[int]` | Workspace IDs to ignore. |
| `reverse_scroll` | `bool` | Invert scroll direction. |
| `empty_scroll` | `bool` | Allow scrolling through empty workspaces. |
| `navigate_empty` | `bool` | Allow switching to empty workspaces during navigation. |
| `icon_map` | `dict[str, str]` | Mapping of workspace to icon/label. |

#### `system_tray`

| Key | Type | Description |
|---|---|---|
| `icon_size` | `int` | System tray icon size. |
| `ignore` | `list[str]` | Applications to ignore. |

#### `power`

| Key | Type | Description |
|---|---|---|
| `icon` | `str` | Icon for the power button. |
| `icon_size` | `str` | Icon size. |
| `tooltip` | `bool` | Show tooltip. |

#### `dynamic_island`

##### `power_menu`

| Key | Type | Description |
|---|---|---|
| `lock_icon` | `str` | Icon for lock. |
| `lock_icon_size` | `str` | Icon size. |
| `suspend_icon` | `str` | Icon for suspend. |
| `suspend_icon_size` | `str` | Icon size. |
| `logout_icon` | `str` | Icon for logout. |
| `logout_icon_size` | `str` | Icon size. |
| `reboot_icon` | `str` | Icon for reboot. |
| `reboot_icon_size` | `str` | Icon size. |
| `shutdown_icon` | `str` | Icon for shutdown. |
| `shutdown_icon_size` | `str` | Icon size. |

##### `compact`

This module controls the compact view of the Dynamic Island that shows the active window and currently playing music.

###### `window_titles`

| Key | Type | Description |
|---|---|---|
| `enable_icon` | `bool` | Show window icon. |
| `truncation` | `bool` | Truncate window title. |
| `truncation_size` | `int` | Max title length. |
| `title_map` | `list[tuple[str, str, str]]` | Title replacement map. |

###### `music`

| Key | Type | Description |
|---|---|---|
| `enabled` | `bool` | Enable music module. |
| `truncation` | `bool` | Truncate track title. |
| `truncation_size` | `int` | Max title length. |
| `default_album_logo` | `str` | Default album cover URL. |

##### `wallpapers`

| Key | Type | Description |
|---|---|---|
| `wallpapers_dirs` | `list[str]` | Directories with wallpapers. |
| `method` | `str` | Wallpaper set method (supported: `swww`). |
| `save_current_wall` | `bool` | Save currently set wallpaper. |
| `current_wall_path` | `str` | Path to file storing the current wallpaper. |

#### `datetime`

| Key | Type | Description |
|---|---|---|
| `format` | `str` | Datetime format string. |

#### `battery`

| Key | Type | Description |
|---|---|---|
| `show_label` | `bool` | Show text label. |
| `tooltip` | `bool` | Show tooltip. |

#### `ocr`

| Key | Type | Description |
|---|---|---|
| `icon` | `str` | Icon for OCR. |
| `icon_size` | `str` | Icon size. |
| `tooltip` | `bool` | Show tooltip. |
| `default_lang` | `str` | Default language(s). |
