# ✨ MewLine
Элегантный и расширяемый статус-бар для дистрибутива [meowrch](https://github.com/meowrch/meowrch), написанный на Python с использованием фреймворка [Fabric](https://github.com/Fabric-Development/fabric). Сочетает в себе минималистичный дизайн с мощной функциональностью.

> [!Warning]
> Проект находится в активной разработке.
>Некоторые функции могут работать нестабильно


<table align="center">
  <tr>
    <td colspan="4"><img src="./assets/default.png"></td>
  </tr>
  <tr>
    <td colspan="1"><img src="./assets/date_notification.png"></td>
    <td colspan="1"><img src="./assets/power.png"></td>
    <td colspan="1" align="center"><img src="./assets/notify.png"></td>
  </tr>
</table>


## 🌟 Особенности
- [X] **Модульная архитектура**
- [X] **Кастомизация** на любой вкус через JSON-конфиг
- [X] Поддержка **тем**
- [X] Полная интеграция с дистрибутивом [meowrch](https://github.com/meowrch/meowrch)
- [X] Анимированные переходы и эффекты
- [X] Низкое потребление ресурсов

## ⚡ Быстрый старт
```bash
# Склонируйте репозиторий
git clone https://github.com/meowrch/mewline && cd mewline

# Установите пакетный менеджер
pip install uv # Или sudo pacman -S uv

# Установите зависимости
uv sync

# Сгенерируйте конфиг по умолчанию
uv run generate_default_config

# Настройте config.json под свои нужды
micro ~/.config/mewline/config.json

# Запустите MewLine
uv run mewline
```

>[!IMPORTANT]
> Так-же mewline есть в AUR `mewline-git`

## 🎨 Виджеты
### Статус Бар
| Компонент          | Описание                           |
| ------------------ | ---------------------------------- |
| `tray`             | Системный трей                     |
| `workspaces`       | Управление рабочими пространствами |
| `datetime`         | Отображение даты и времени         |
| `brightness`       | Управление яркостью                |
| `volume`           | Управление громкостью звука        |
| `battry`           | Информация о заряде аккумулятора   |
| `power`            | Кнопка для вызова `power_menu`     |

## Динамический остров
| Компонент          | Описание                                 |
| ------------------ | -----------------------------------------|
| `notifications`    | Уведомления                              |
| `power_menu`       | Меню для управления питанием             |
| `date_notification`| Меню с календарем и историей уведомлений |
| `bluetooth`        | Меню для управления bluetooth            |

## Другое
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
| **TON**      | `UQCsIhKtqCnh0Mp76X_5qfh66TPBoBsYx_FihgInw-Auk5BA` |
| **Ethereum** | `0x56e8bf8Ec07b6F2d6aEdA7Bd8814DB5A72164b13`       |
| **Bitcoin**  | `bc1qt5urnw7esunf0v7e9az0jhatxrdd0smem98gdn`       |
| **Tron**     | `TBTZ5RRMfGQQ8Vpf8i5N8DZhNxSum2rzAs`               |


Ваша поддержка мотивирует нас делать больше крутых фич! ❤️

## 📊 Статистика
[![Star History Chart](https://api.star-history.com/svg?repos=meowrch/mewline&type=Date)](https://star-history.com/#meowrch/mewline&Date)
