import os
import select
import threading


class OutputCapture:
    """Захватывает только C-библиотеки (GTK/GLib) вывод, не трогая Python логи."""

    def __init__(self):
        self.capture_active = False
        self.log_file = None

    def _write_to_log(self, text, stream_type="stderr"):
        """Записывает захваченный вывод напрямую в файл и журнал."""
        if not text.strip():
            return

        text = text.strip()

        # Записываем в файл без использования loguru (избегаем цикла)
        if self.log_file:
            try:
                self.log_file.write(f"[{stream_type.upper()}] {text}\n")
                self.log_file.flush()
            except Exception: ...

        # Также отправляем в systemd journal напрямую
        try:
            from systemd import journal

            if any(
                word in text.lower()
                for word in ["error", "critical", "fatal", "segfault"]
            ):
                journal.send(
                    f"[GTK/{stream_type.upper()}] {text}", PRIORITY=journal.LOG_ERR
                )
            elif any(word in text.lower() for word in ["warning", "warn"]):
                journal.send(
                    f"[GTK/{stream_type.upper()}] {text}", PRIORITY=journal.LOG_WARNING
                )
            else:
                journal.send(
                    f"[GTK/{stream_type.upper()}] {text}", PRIORITY=journal.LOG_INFO
                )
        except Exception: ...

    def start_capture(self):
        """Начинает захват только stderr (где GTK выводит сообщения)."""
        if self.capture_active:
            return

        try:
            # Открываем файл для GTK логов
            from pathlib import Path

            log_dir = Path.home() / ".local/share/mewline/logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            self.log_file = open(log_dir / "gtk_capture.log", "a")  # noqa: SIM115

            self.capture_active = True

            # Создаем pipe только для stderr (где GTK обычно выводит)
            self.stderr_read, self.stderr_write = os.pipe()

            # Сохраняем оригинальный stderr
            self.original_stderr_fd = os.dup(2)  # stderr = fd 2

            # Создаем tee - дублируем в оригинальный stderr и наш pipe
            def tee_stderr():
                try:
                    while self.capture_active:
                        try:
                            # Ждем данных в pipe с таймаутом
                            ready, _, _ = select.select([self.stderr_read], [], [], 0.1)
                            if ready:
                                data = os.read(self.stderr_read, 4096)
                                if not data:
                                    break

                                text = data.decode("utf-8", errors="replace")

                                # Записываем в оригинальный stderr
                                os.write(self.original_stderr_fd, data)

                                # И логируем наш захват
                                for line in text.splitlines():
                                    if line.strip():
                                        self._write_to_log(line, "stderr")
                        except (OSError, ValueError):
                            break
                except Exception: ...

            # Запускаем поток tee
            self.tee_thread = threading.Thread(target=tee_stderr, daemon=True)
            self.tee_thread.start()

            # Перенаправляем stderr в наш pipe
            os.dup2(self.stderr_write, 2)

            print("[CAPTURE] GTK/GLib output capture started")

        except Exception as e:
            print(f"[CAPTURE] Failed to start capture: {e}")


# Глобальный экземпляр
_capture = OutputCapture()


def start_output_capture():
    """Запускает захват вывода GTK/GLib."""
    _capture.start_capture()
