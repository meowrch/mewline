# ✨ MewLine 
Элегантный и расширяемый статус-бар для дистрибутива [meowrch](https://github.com/meowrch/meowrch), написанный на Python с использованием фреймворка [Fabric](https://github.com/Fabric-Development/fabric). Сочетает в себе минималистичный дизайн с мощной функциональностью.

> [!Warning]
> Проект находится в активной разработке.
>Некоторые функции могут работать нестабильно

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
pip install uv

# Установите зависимости
uv sync

# Сгенерируйте конфиг по умолчанию
python mewline/app.py --generate-default-config

# Настройте config.json под свои нужды
micro ~/.config/mewline/config.json

# Запустите MewLine
python mewline/app.py
```

## 🎨 Виджеты
| Компонент          | Описание                           |
| ------------------ | ---------------------------------- |
| `tray`             | Системный трей                     |
| `workspaces`       | Управление рабочими пространствами |
| `dynamic_island`   | Динамический остров                |
| `power_menu`       | Меню для управления питанием       |


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