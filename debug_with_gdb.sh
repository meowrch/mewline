#!/bin/bash

# Скрипт для запуска mewline под GDB с автоматическим анализом падений

echo "🔧 Starting mewline with GDB for detailed crash analysis..."

# Создаем временный GDB скрипт
cat > /tmp/mewline_gdb_commands << 'EOF'
# Настройка GDB для детальной отладки GTK приложений

# Включаем Python поддержку если доступна
python
import sys
print("GDB Python support available:", sys.version)
end

# Настраиваем обработчики сигналов
handle SIGSEGV stop print
handle SIGABRT stop print
handle SIGFPE stop print

# При любом падении - показываем максимум информации
define crash_info
    echo \n=== CRASH INFORMATION ===\n
    info registers
    echo \n=== STACK TRACE ===\n
    bt full
    echo \n=== THREAD INFORMATION ===\n
    info threads
    thread apply all bt
    echo \n=== MEMORY MAPPINGS ===\n
    info proc mappings
    echo \n=== SHARED LIBRARIES ===\n
    info sharedlibrary
    echo \n=== GTK DEBUGGING ===\n
    # Пытаемся получить GTK specific информацию
    python
try:
    # Ищем GTK объекты в памяти
    frame = gdb.selected_frame()
    print("Current frame:", frame.name())

    # Пытаемся найти последний вызов из GTK
    i = 0
    while i < 20:  # Проверяем первые 20 фреймов
        try:
            frame = gdb.selected_frame()
            frame_name = frame.name()
            if frame_name and ('gtk' in frame_name.lower() or 'string_to_string' in frame_name.lower()):
                print(f"Found GTK frame {i}: {frame_name}")
                # Пытаемся вывести локальные переменные
                try:
                    gdb.execute("info locals")
                except:
                    pass
                break
            frame = frame.older()
            i += 1
        except:
            break
except Exception as e:
    print("Error in GTK debugging:", e)
end
end

# Устанавливаем точки останова на критических функциях
# break g_log_default_handler
# break g_assertion_message
# break string_to_string

# Команды для выполнения при запуске
set environment G_DEBUG=fatal-warnings,fatal-criticals
set environment G_MESSAGES_DEBUG=all
set environment MALLOC_CHECK_=2

# Запуск команды
run

# Если случилось падение - автоматически вызываем crash_info
define hook-stop
    if $_siginfo
        crash_info
    end
end

EOF

echo "📝 GDB script created, starting debugging session..."
echo "🚀 When crash occurs, detailed information will be displayed automatically"

# Получаем правильный путь к Python из uv
cd /mnt/work/MyProjects/mewline
PYTHON_PATH=$(uv run python -c "import sys; print(sys.executable)")
echo "Using Python: $PYTHON_PATH"

# Запускаем GDB с правильными аргументами
exec gdb -batch -x /tmp/mewline_gdb_commands --args "$PYTHON_PATH" -m mewline --debug
