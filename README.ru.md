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
		<img src="https://img.shields.io/badge/README-RU-blue?color=cba6f7&labelColor=cba6f7&style=for-the-badge">
	</a>
	<a href="./README.md">
		<img src="https://img.shields.io/badge/README-ENG-blue?color=C9CBFF&labelColor=1C2325&style=for-the-badge">
	</a>
</div>
<br>
<br>

Элегантный и расширяемый статус-бар для дистрибутива [meowrch](https://github.com/meowrch/meowrch), написанный на Python с использованием фреймворка [Fabric](https://github.com/Fabric-Development/fabric). Сочетает в себе минималистичный дизайн с мощной функциональностью.


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


## 🌟 Особенности
- [X] **Поддержка Hyprland и bspwm**: Полная интеграция с современными тайловыми оконными менеджерами.
- [X] **Мультимониторность**: Поддержка автоматического развертывание панелей на всех обнаруженных дисплеях (в данный момент реализовано только для Hyprland).
- [X] **Индикаторы приватности (Privacy Dots)**: Визуальное оповещение об использовании микрофона, камеры, геопозиции или записи экрана в реальном времени.
- [X] **Модульная архитектура и кастомизация** через JSON-конфиг
- [X] Поддержка **тем**
- [X] Полная интеграция с дистрибутивом [meowrch](https://github.com/meowrch/meowrch)
- [X] Анимированные переходы и эффекты
- [X] Низкое потребление ресурсов
- [X] Управление с клавиатуры

## ⚙️ Конфигурация

Подробную информацию о конфигурации можно найти в [документации](docs/configuration.ru.md).

## 🧩 Установка зависимостей
```bash
sudo pacman -S dart-sass tesseract tesseract-data-eng tesseract-data-rus slurp grim cliphist
yay -S gnome-bluetooth-3.0 gray-git fabric-cli-git
```

## ⚡ Быстрый старт
```bash
# Установите пакет
yay -S mewline-git

# Сгенерируйте конфиг по умолчанию
mewline --generate-default-config

# Сгенерируйте сочетания клавиш для hyprland
mewline --create-keybindings

# Настройте config.json под свои нужды
micro ~/.config/mewline/config.json

# Запустите MewLine
mewline
```

## 🛠 Для разработчиков
```bash
# Склонируйте репозиторий
git clone https://github.com/meowrch/mewline && cd mewline

# Установите пакетный менеджер
pip install uv # Или sudo pacman -S uv

# Установите зависимости
uv sync

# Сгенерируйте конфиг по умолчанию
uv run generate_default_config

# Сгенерируйте сочетания клавиш для hyprland
uv run create_keybindings

# Настройте config.json под свои нужды
micro ~/.config/mewline/config.json

# Запустите MewLine
uv run mewline
```


## 🎨 Виджеты
### ℹ️ Статус Бар
| Компонент          | Описание                           |
| ------------------ | ---------------------------------- |
| `tray`             | Системный трей                     |
| `workspaces`       | Управление рабочими пространствами |
| `datetime`         | Отображение даты и времени         |
| `combined_controls` | Групповой виджет управления, объединяющий звук, яркость и Privacy Dots (точки уведомлений, которые загораются, когда приложения получают доступ к вашим медиа-устройствам). |
| `language`         | Информация о раскладке клавиатуры  |
| `battry`           | Информация о заряде аккумулятора   |
| `power`            | Кнопка для вызова `power_menu`     |
| `ocr`              | Распознавание текста с скриншота   |

## 🏝 Динамический остров
| Компонент          | Описание                                                  | Сочетание клавиш   |
| ------------------ | ----------------------------------------------------------| ------------------ |
| `compact`          | Отображает информацию о активном окне и включенной музыке | -                  |
| `notifications`    | Уведомления                                               | -                  |
| `power_menu`       | Меню для управления питанием                              | `Super+Alt+P`      |
| `date_notification`| Меню с календарем и историей уведомлений                  | `Super+Alt+D`      |
| `bluetooth`        | Меню для управления bluetooth                             | `Super+Alt+B`      |
| `app_launcher`     | Лаунчер приложений                                        | `Super+Alt+A`      |
| `wallpapers`       | Выбор обоев                                               | `Super+Alt+W`      |
| `emoji`            | Выбор emoji                                               | `Super+Alt+.`      |
| `clipbpard`        | Управление Буфером обмена                                 | `Super+Alt+V`      |
| `network`          | Управление wifi сетями и Ethernet                         | `Super+Alt+N`      |
| `workspaces`       | Управление открытыми окнами                               | `Super+Alt+Tab`    |

### ⌨️ Сочетания клавиш
Динамическим островом можно управлять с помощью сочетаний клавиш.
Если вы еще не сгенерировали конфигурацию для hyprland, то выполните:
```bash
mewline --create-keybindings
```

## ❓ Другое
| Компонент          | Описание                                             |
| ------------------ | -----------------------------------------------------|
| `osd`              | Уведомления о событиях изменения громкости/яркости   |


## 🐾 Особые Благодарности
Проект вдохновлён и использует лучшие идеи из:

- **[HyDePanel](https://github.com/rubiin/HyDePanel)** \
    Архитектура модульной системы, некоторые стили и виджеты.

- **[Ax-Shell](https://github.com/Axenide/Ax-Shell)** \
    Подход к обработке системных событий, IPC-механизмы, некоторые стили и виджеты.

Мы глубоко признательны авторам этих проектов за их вклад в open-source сообщество.
Отдельные компоненты были адаптированы и улучшены для интеграции с MewLine.

## 🚀 Развитие проекта
Хотите добавить новый виджет или улучшить существующий?

1. Форкните репозиторий
2. Создайте ветку с фичей: `git checkout -b feature/amazing-widget`
3. Залейте изменения: `git push origin feature/amazing-widget`
4. Откройте Pull Request

Рекомендуем сначала обсудить идею в Issues.

## ☕ Поддержать проект
Если вам нравится MewLine, вы можете помочь его развитию:
| Криптовалюта | Адрес                                              |
| ------------ | -------------------------------------------------- |
| **TON**      | `UQB9qNTcAazAbFoeobeDPMML9MG73DUCAFTpVanQnLk3BHg3` |
| **Ethereum** | `0x56e8bf8Ec07b6F2d6aEdA7Bd8814DB5A72164b13`       |
| **Bitcoin**  | `bc1qt5urnw7esunf0v7e9az0jhatxrdd0smem98gdn`       |
| **Tron**     | `TBTZ5RRMfGQQ8Vpf8i5N8DZhNxSum2rzAs`               |


Ваша поддержка мотивирует нас делать больше крутых фич! ❤️

## 📊 Статистика
[![Star History Chart](https://api.star-history.com/svg?repos=meowrch/mewline&type=Date)](https://star-history.com/#meowrch/mewline&Date)
