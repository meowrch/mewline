import json
import os
import subprocess
import threading

from fabric.core.service import Property
from fabric.core.service import Service
from gi.repository import GLib


def _get_process_name(pid: str) -> str:
    try:
        with open(f"/proc/{pid}/comm") as f:
            return f.read().strip()
    except Exception:
        return f"pid:{pid}"


class PrivacyService(Service):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._cam_active = False
        self._mic_active = False
        self._screen_active = False
        self._loc_active = False

        self.cam_apps: list[str] = []
        self.mic_apps: list[str] = []
        self.screen_apps: list[str] = []
        self.loc_apps: list[str] = []

        self._is_polling = False
        GLib.timeout_add(2000, self._poll)
        self._poll()

    @Property(bool, "readable", default_value=False)
    def cam_active(self) -> bool:
        return self._cam_active

    @Property(bool, "readable", default_value=False)
    def mic_active(self) -> bool:
        return self._mic_active

    @Property(bool, "readable", default_value=False)
    def screen_active(self) -> bool:
        return self._screen_active

    @Property(bool, "readable", default_value=False)
    def loc_active(self) -> bool:
        return self._loc_active

    def _poll(self):
        if not self._is_polling:
            self._is_polling = True
            threading.Thread(target=self._do_poll, daemon=True).start()
        return True

    def _do_poll(self):
        cam, mic, screen, loc = False, False, False, False
        cam_apps, mic_apps, screen_apps, loc_apps = [], [], [], []

        # 1. Camera – /dev/video* open by some process
        try:
            for pid in os.listdir("/proc"):
                if not pid.isdigit():
                    continue
                fd_dir = f"/proc/{pid}/fd"
                if not os.access(fd_dir, os.R_OK):
                    continue
                try:
                    for fd in os.listdir(fd_dir):
                        try:
                            if os.readlink(f"{fd_dir}/{fd}").startswith("/dev/video"):
                                cam = True
                                name = _get_process_name(pid)
                                if name not in cam_apps:
                                    cam_apps.append(name)
                                break
                        except OSError:
                            continue
                except OSError:
                    continue
        except Exception:  # noqa: S110
            pass

        # 2. PipeWire Dump parsing (Mic & Screen Sharing identical to privacy-dots.sh)
        try:
            out = subprocess.check_output(
                ["pw-dump"], stderr=subprocess.DEVNULL, text=True, timeout=1
            )
            nodes = json.loads(out)

            # First pass: check if any mic is active globally (Audio/Source running)
            # privacy_dots checks if Audio/Source or Audio/Source/Virtual is running
            any_mic_running = False
            for node in nodes:
                if node.get("type") != "PipeWire:Interface:Node":
                    continue

                info = node.get("info", {})
                state = info.get("state") or node.get("state")
                props = info.get("props", {})
                media_class = str(props.get("media.class", ""))

                if (
                    media_class in ["Audio/Source", "Audio/Source/Virtual"]
                ) and state == "running":
                    any_mic_running = True
                    break

            if any_mic_running:
                mic = True
                # Find the actual apps capturing the mic
                for node in nodes:
                    if node.get("type") != "PipeWire:Interface:Node":
                        continue

                    info = node.get("info", {})
                    state = info.get("state") or node.get("state")
                    props = info.get("props", {})
                    media_class = str(props.get("media.class", ""))
                    app_name = str(
                        props.get("application.name", "") or props.get("node.name", "")
                    ).strip()

                    # privacy_dots logic:
                    # media.class == "Stream/Input/Audio" and state == "running"
                    if (
                        media_class == "Stream/Input/Audio"
                        and state == "running"
                        and app_name
                        and app_name.lower() not in {"wireplumber", "pipewire"}
                        and app_name not in mic_apps
                    ):
                        mic_apps.append(app_name)

            # Second pass: check for screen sharing matching privacy_dots regex
            # jq logic: test("^(xdph-streaming|gsr-default|game capture)") on media.name
            for node in nodes:
                info = node.get("info", {})
                props = info.get("props", {})

                if not props:
                    continue

                media_name = str(props.get("media.name", "")).lower()

                if (
                    media_name.startswith("xdph-streaming")
                    or media_name.startswith("gsr-default")
                    or media_name.startswith("game capture")
                ):
                    screen = True
                    break

            if screen:
                # Find the actual apps/names doing the screen share
                for node in nodes:
                    if node.get("type") != "PipeWire:Interface:Node":
                        continue

                    info = node.get("info", {})
                    state = info.get("state") or node.get("state")
                    props = info.get("props", {})
                    media_class = str(props.get("media.class", ""))
                    media_name = str(props.get("media.name", ""))

                    if (
                        media_class == "Stream/Input/Video"
                        or media_name == "gsr-default_output"
                        or media_name == "game capture"
                    ) and state == "running":
                        app_name = media_name or "Screen Share"
                        if app_name not in screen_apps:
                            screen_apps.append(app_name)
        except Exception:  # noqa: S110
            pass

        # 3. wlroots direct screencopy fallback (wf-recorder, wl-screenrec, etc)
        try:
            for recorder_bin in ["wf-recorder", "wl-screenrec"]:
                try:
                    pids = subprocess.check_output(
                        ["pgrep", "-x", recorder_bin],
                        stderr=subprocess.DEVNULL,
                        text=True,
                        timeout=1,
                    ).strip()

                    if pids:
                        screen = True
                        if recorder_bin not in screen_apps:
                            screen_apps.append(recorder_bin)
                except subprocess.CalledProcessError:
                    pass
        except Exception:  # noqa: S110
            pass

        # 4. Location – geoclue running
        try:
            if subprocess.check_output(
                ["pgrep", "-f", "geoclue"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=1,
            ).strip():
                loc = True
                loc_apps = ["geoclue"]
        except Exception:  # noqa: S110
            pass

        GLib.idle_add(
            self._update_state,
            cam,
            mic,
            screen,
            loc,
            cam_apps,
            mic_apps,
            screen_apps,
            loc_apps,
        )

    def _update_state(
        self, cam, mic, screen, loc, cam_apps, mic_apps, screen_apps, loc_apps
    ):
        self.cam_apps = cam_apps
        self.mic_apps = mic_apps
        self.screen_apps = screen_apps
        self.loc_apps = loc_apps

        if cam != self._cam_active:
            self._cam_active = cam
            self.notify("cam-active")
        if mic != self._mic_active:
            self._mic_active = mic
            self.notify("mic-active")
        if screen != self._screen_active:
            self._screen_active = screen
            self.notify("screen-active")
        if loc != self._loc_active:
            self._loc_active = loc
            self.notify("loc-active")

        self._is_polling = False
        return False
