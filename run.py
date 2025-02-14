import os
import runpy
import sys

if __name__ == "__main__":
    src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "src"))
    sys.path.insert(0, src_path)

    # Запускаем модуль
    runpy.run_module("mewline.__main__", run_name="__main__")
