<div align="center">
	<h1> ✨ Mewline </h1>
	<a href="https://github.com/meowrch/mewline/issues">
		<img src="https://img.shields.io/github/issues/meowrch/mewline?color=ffb29b&labelColor=1C2325&style=for-the-badge">
	</a>
	<a href="https://github.com/meowrch/mewline/stargazers">
		<img src="https://img.shields.io/github/stars/meowrch/mewline?color=fab387&labelColor=1C2325&style=for-the-badge">
	</a>
	<a href="./LICENSE">
		<img src="https://img.shields.io/github/license/meowrch/mewline?color=FCA2AA&labelColor=1C2325&style=for-the-badge">
	</a>
	<br>
	<br>
	<a href="./README.ru.md">
		<img src="https://img.shields.io/badge/README-RU-blue?color=cba6f7&labelColor=1C2325&style=for-the-badge">
	</a>
	<a href="./README.md">
		<img src="https://img.shields.io/badge/README-ENG-blue?color=C9CBFF&labelColor=C9CBFF&style=for-the-badge">
	</a>
</div>
<br>
<br>

An elegant, extensible status bar for the [meowrch](https://github.com/meowrch/meowrch) distribution, written in Python using the [Fabric](https://github.com/Fabric-Development/fabric) framework. It combines a minimalist design with powerful functionality.

<table align="center">
  <tr>
    <td colspan="3"><img src="./assets/preview.png"></td>
  </tr>
  <tr>
    <td colspan="1"><img src="./assets/preview1.png"></td>
    <td colspan="1"><img src="./assets/preview2.png"></td>
    <td colspan="1"><img src="./assets/preview3.png"></td>
  </tr>
  <tr>
    <td colspan="1"><img src="./assets/preview4.png"></td>
    <td colspan="1"><img src="./assets/preview5.png"></td>
    <td colspan="1"><img src="./assets/preview6.png"></td>
  </tr>
  <tr>
    <td colspan="3"><img src="./assets/preview7.png"></td>
  </tr>
</table>

## 🌟 Features
- [X] **Modular architecture**
- [X] **Customization** via a JSON config
- [X] **Theme** support
- [X] Full integration with the [meowrch](https://github.com/meowrch/meowrch) distribution
- [X] Animated transitions and effects
- [X] Low resource usage
- [X] Keyboard control

## ⚙️ Configuration
See [English configuration docs](docs/configuration.md) for detailed configuration info.

## 🧩 Install dependencies
```bash
sudo pacman -S dart-sass tesseract tesseract-data-eng tesseract-data-rus slurp grim cliphist
yay -S gnome-bluetooth-3.0 gray-git fabric-cli-git
```

## ⚡ Quick start
```bash
# Install the package
yay -S mewline-git

# Generate the default config
mewline --generate-default-config

# Generate keybindings for Hyprland
mewline --create-keybindings

# Tweak config.json to your liking
micro ~/.config/mewline/config.json

# Run MewLine
mewline
```

## 🛠 For developers
```bash
# Clone the repo
git clone https://github.com/meowrch/mewline && cd mewline

# Install the package manager
pip install uv # Or: sudo pacman -S uv

# Install dependencies
uv sync

# Generate the default config
uv run generate_default_config

# Generate keybindings for Hyprland
uv run create_keybindings

# Tweak config.json to your liking
micro ~/.config/mewline/config.json

# Run MewLine
uv run mewline
```

## 🎨 Widgets
### ℹ️ Status Bar

| Component    | Description                            |
| ------------ | -------------------------------------- |
| `tray`       | System tray                             |
| `workspaces` | Workspace management                    |
| `datetime`   | Date and time display                   |
| `brightness` | Screen brightness control               |
| `volume`     | Audio volume control                    |
| `battry`     | Battery charge information              |
| `power`      | Button to open the `power_menu`         |
| `ocr`        | Text recognition from a screenshot      |

## 🏝 Dynamic Island

| Component           | Description                                                 | Keybinding        |
| ------------------- | ----------------------------------------------------------- | ----------------- |
| `compact`           | Shows active window and currently playing music             | -                 |
| `notifications`     | Notifications                                               | -                 |
| `power_menu`        | Power management menu                                       | `Super+Alt+P`     |
| `date_notification` | Calendar and notifications history                          | `Super+Alt+D`     |
| `bluetooth`         | Bluetooth manager                                           | `Super+Alt+B`     |
| `app_launcher`      | Application launcher                                        | `Super+Alt+A`     |
| `wallpapers`        | Wallpaper picker                                            | `Super+Alt+W`     |
| `emoji`             | Emoji picker                                                | `Super+Alt+.`     |
| `clipbpard`         | Clipboard manager                                           | `Super+Alt+V`     |
| `network`           | Wi-Fi and Ethernet manager                                  | `Super+Alt+N`     |
| `workspaces`        | Open windows/workspaces manager                             | `Super+Alt+Tab`   |

### ⌨️ Keybindings
You can control the Dynamic Island using keybindings. If you haven't generated the Hyprland config yet, run:
```bash
mewline --create-keybindings
```

## ❓ Other

| Component | Description                                             |
| --------- | ------------------------------------------------------- |
| `osd`     | On-screen display for volume/brightness change events   |

## 🐾 Special Thanks
This project is inspired by and borrows great ideas from:

- **[HyDePanel](https://github.com/rubiin/HyDePanel)** \
  Modular system architecture, some styles and widgets.

- **[Ax-Shell](https://github.com/Axenide/Ax-Shell)** \
  Approach to handling system events, IPC mechanisms, some styles and widgets.

We are grateful to the authors of these projects for their contribution to the open-source community. Some components were adapted and improved to integrate with MewLine.

## 🚀 Contributing
Want to add a new widget or improve an existing one?

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-widget`
3. Push your changes: `git push origin feature/amazing-widget`
4. Open a Pull Request

We recommend discussing the idea in Issues first.

## ☕ Support the project
If you like MewLine, you can support its development:

| Cryptocurrency | Address                                              |
| -------------- | ---------------------------------------------------- |
| **TON**        | `UQB9qNTcAazAbFoeobeDPMML9MG73DUCAFTpVanQnLk3BHg3` |
| **Ethereum**   | `0x56e8bf8Ec07b6F2d6aEdA7Bd8814DB5A72164b13`       |
| **Bitcoin**    | `bc1qt5urnw7esunf0v7e9az0jhatxrdd0smem98gdn`       |
| **Tron**       | `TBTZ5RRMfGQQ8Vpf8i5N8DZhNxSum2rzAs`               |

Your support motivates us to build more great features! ❤️

## 📊 Stats
[![Star History Chart](https://api.star-history.com/svg?repos=meowrch/mewline&type=Date)](https://star-history.com/#meowrch/mewline&Date)
