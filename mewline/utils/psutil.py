import time

import psutil
from fabric import Fabricator


# Function to get the system stats using psutil
def psutil_poll(_):
    while True:
        yield {
            "cpu_usage": f"{round(psutil.cpu_percent())}%",
            "cpu_freq": psutil.cpu_freq(percpu=True),
            "ram_usage": f"{round(psutil.virtual_memory().percent)}%",
            "memory": psutil.virtual_memory(),
            "battery": psutil.sensors_battery(),
        }
        time.sleep(2)


# Create a fabricator to poll the system stats
psutil_fabricator = Fabricator(poll_from=psutil_poll, stream=True)
