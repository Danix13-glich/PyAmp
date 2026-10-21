from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable
from pathlib import Path

from dbus_next import Variant
from dbus_next.aio import MessageBus
from dbus_next.constants import PropertyAccess
from dbus_next.service import ServiceInterface, dbus_property, method, signal

from app.core.player import STATE_PAUSED, STATE_PLAYING, Player
from app.core.settings import Settings
from app.library.models import Track

logger = logging.getLogger(__name__)

BUS_NAME = "org.mpris.MediaPlayer2.pyamp"
OBJECT_PATH = "/org/mpris/MediaPlayer2"
NO_TRACK_PATH = "/org/mpris/MediaPlayer2/TrackList/NoTrack"
_TRACK_ID_PREFIX = "/net/pyamp/Track/"

_STATUS_PLAYING = "Playing"
_STATUS_PAUSED = "Paused"
_STATUS_STOPPED = "Stopped"

_MIME_TYPES = [
    "audio/mpeg",
    "audio/mp4",
    "audio/x-wav",
    "audio/ogg",
    "audio/flac",
]


def track_object_path(track: Track) -> str:
    identifier = track.id if track.id is not None else abs(hash(track.path)) % 1_000_000_000
    return f"{_TRACK_ID_PREFIX}{identifier}"


class _RootInterface(ServiceInterface):

    def __init__(self, adapter: MprisAdapter):
        super().__init__("org.mpris.MediaPlayer2")
        self._adapter = adapter

    @method()
    def Raise(self):  # noqa: N802 - nombre D-Bus
        self._adapter.request_raise()

    @method()
    def Quit(self):  # noqa: N802 - nombre D-Bus
        self._adapter.request_quit()

    @dbus_property(access=PropertyAccess.READ)
    def CanQuit(self) -> "b":  # noqa: F821 - tipo D-Bus
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanRaise(self) -> "b":  # noqa: F821 - tipo D-Bus
        return True

    @dbus_property(access=PropertyAccess.READ)
    def HasTrackList(self) -> "b":  # noqa: F821 - tipo D-Bus
        return False

    @dbus_property(access=PropertyAccess.READ)
    def Identity(self) -> "s":  # noqa: F821 - tipo D-Bus
        return "PyAmp"

    @dbus_property(access=PropertyAccess.READ)
    def DesktopEntry(self) -> "s":  # noqa: F821 - tipo D-Bus
        return "pyamp"

    @dbus_property(access=PropertyAccess.READ)
    def SupportedUriSchemes(self) -> "as":  # noqa: F821 - tipo D-Bus
        return ["file"]

    @dbus_property(access=PropertyAccess.READ)
    def SupportedMimeTypes(self) -> "as":  # noqa: F821 - tipo D-Bus
        return _MIME_TYPES

    @dbus_property(access=PropertyAccess.READ)
    def CanSetFullscreen(self) -> "b":  # noqa: F821 - tipo D-Bus
        return False

    @dbus_property(access=PropertyAccess.READWRITE)
    def Fullscreen(self) -> "b":  # noqa: F821 - tipo D-Bus
        return False

    @Fullscreen.setter
    def Fullscreen(self, value: "b"):  # noqa: F821 - tipo D-Bus
        return  # PyAmp no es fullscreen; el setter es obligatorio por READWRITE


class _PlayerInterface(ServiceInterface):

    def __init__(self, adapter: MprisAdapter):
        super().__init__("org.mpris.MediaPlayer2.Player")
        self._adapter = adapter

    # ------------------------------------------------------------- comandos
    @method()
    def Play(self):  # noqa: N802 - nombre D-Bus
        self._adapter.player.play()

    @method()
    def Pause(self):  # noqa: N802 - nombre D-Bus
        self._adapter.player.pause()

    @method()
    def PlayPause(self):  # noqa: N802 - nombre D-Bus
        self._adapter.player.toggle_pause()

    @method()
    def Stop(self):  # noqa: N802 - nombre D-Bus
        self._adapter.player.stop()

    @method()
    def Next(self):  # noqa: N802 - nombre D-Bus
        self._adapter.player.next()

    @method()
    def Previous(self):  # noqa: N802 - nombre D-Bus
        self._adapter.player.prev()

    @method()
    def Seek(self, offset: "x"):  # noqa: F821 - tipo D-Bus
        player = self._adapter.player
        player.seek(player.position_ms() + int(offset) // 1000)

    @method()
    def SetPosition(self, track_id: "o", position: "x"):  # noqa: F821
        del track_id  # la UI solo tiene una pista en reproducción
        self._adapter.player.seek(int(position) // 1000)

    @signal()
    def Seeked(self, position: "x") -> "x":  # noqa: F821 - tipo D-Bus
        return position

    # ----------------------------------------------------------- propiedades
    @dbus_property(access=PropertyAccess.READ)
    def PlaybackStatus(self) -> "s":  # noqa: F821 - tipo D-Bus
        return self._adapter.playback_status

    @dbus_property(access=PropertyAccess.READWRITE)
    def LoopStatus(self) -> "s":  # noqa: F821 - tipo D-Bus
        return "None"

    @LoopStatus.setter
    def LoopStatus(self, value: "s"):  # noqa: F821 - tipo D-Bus
        return  # sin bucles en PyAmp

    @dbus_property(access=PropertyAccess.READ)
    def Rate(self) -> "d":  # noqa: F821 - tipo D-Bus
        return 1.0

    @dbus_property(access=PropertyAccess.READWRITE)
    def Shuffle(self) -> "b":  # noqa: F821 - tipo D-Bus
        return False

    @Shuffle.setter
    def Shuffle(self, value: "b"):  # noqa: F821 - tipo D-Bus
        return  # sin aleatorio en PyAmp

    @dbus_property(access=PropertyAccess.READ)
    def Metadata(self) -> "a{sv}":  # noqa: F821 - tipo D-Bus
        return self._adapter.metadata()

    @dbus_property(access=PropertyAccess.READ)
    def MinimumRate(self) -> "d":  # noqa: F821 - tipo D-Bus
        return 1.0

    @dbus_property(access=PropertyAccess.READ)
    def MaximumRate(self) -> "d":  # noqa: F821 - tipo D-Bus
        return 1.0

    @dbus_property(access=PropertyAccess.READ)
    def CanGoNext(self) -> "b":  # noqa: F821 - tipo D-Bus
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanGoPrevious(self) -> "b":  # noqa: F821 - tipo D-Bus
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanPlay(self) -> "b":  # noqa: F821 - tipo D-Bus
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanPause(self) -> "b":  # noqa: F821 - tipo D-Bus
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanSeek(self) -> "b":  # noqa: F821 - tipo D-Bus
        return not self._adapter.player.is_stream

    @dbus_property(access=PropertyAccess.READ)
    def CanControl(self) -> "b":  # noqa: F821 - tipo D-Bus
        return True

    @dbus_property(access=PropertyAccess.READWRITE)
    def Position(self) -> "x":  # noqa: F821 - tipo D-Bus
        return self._adapter.position_us

    @Position.setter
    def Position(self, value: "x"):  # noqa: F821 - tipo D-Bus
        return  # Position es de solo lectura según el spec MPRIS

    @dbus_property(access=PropertyAccess.READWRITE)
    def Volume(self) -> "d":  # noqa: F821 - tipo D-Bus
        return self._adapter.volume

    @Volume.setter
    def Volume(self, value: "d"):  # noqa: F821 - tipo D-Bus
        self._adapter.set_volume(float(value))


class MprisAdapter:

    def __init__(
        self,
        player: Player,
        settings: Settings,
        *,
        on_raise: Callable[[], None] | None = None,
        on_quit: Callable[[], None] | None = None,
    ) -> None:
        self.player = player
        self._settings = settings
        self._on_raise = on_raise
        self._on_quit = on_quit
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._root: _RootInterface | None = None
        self._player_iface: _PlayerInterface | None = None
        self._art_path = ""

    # ------------------------------------------------------------ ciclo vida
    def start(self) -> bool:
        self._thread = threading.Thread(target=self._run_loop, name="pyamp-mpris", daemon=True)
        self._thread.start()
        return True

    def shutdown(self):
        loop = self._loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        thread = self._thread
        if thread is not None:
            thread.join(timeout=2.0)
        self._loop = None
        self._thread = None

    def _run_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            loop.run_until_complete(self._export())
        except Exception as exc:  # noqa: BLE001 - sin D-Bus la app sigue
            logger.info("MPRIS no disponible: %s", exc)
            return
        loop.run_forever()

    async def _export(self):
        bus = await MessageBus().connect()
        self._root = _RootInterface(self)
        self._player_iface = _PlayerInterface(self)
        bus.export(OBJECT_PATH, self._root)
        bus.export(OBJECT_PATH, self._player_iface)
        await bus.request_name(BUS_NAME)
        logger.info("MPRIS registrado (%s)", BUS_NAME)

    # ------------------------------------------------------- updates (UI)
    def update_playback_status(self):
        self._emit_properties_changed(["PlaybackStatus"])

    def update_metadata(self, art_path: str = ""):
        if art_path:
            self._art_path = art_path
        self._emit_properties_changed(["Metadata"])

    def update_volume(self):
        self._emit_properties_changed(["Volume"])

    def emit_seeked(self, position_ms: int):
        self._call_in_loop(lambda: self._safe_seeked(int(position_ms) * 1000))

    def _emit_properties_changed(self, names: list[str]):
        self._call_in_loop(lambda: self._safe_emit_changed(names))

    def _call_in_loop(self, callback: Callable[[], None]):
        loop = self._loop
        if loop is None or not loop.is_running():
            return
        loop.call_soon_threadsafe(callback)

    def _safe_emit_changed(self, names: list[str]):
        iface = self._player_iface
        if iface is None:
            return
        try:
            iface.emit_properties_changed({name: getattr(iface, name) for name in names})
        except Exception as exc:  # noqa: BLE001 - el bus nunca rompe la app
            logger.debug("MPRIS emit falló: %s", exc)

    def _safe_seeked(self, position_us: int):
        iface = self._player_iface
        if iface is None:
            return
        try:
            iface.emit_seeked(position_us)
        except Exception as exc:  # noqa: BLE001
            logger.debug("MPRIS Seeked falló: %s", exc)

    # ------------------------------------------------------------ getters
    @property
    def playback_status(self) -> str:
        state = self.player.state
        if state == STATE_PLAYING:
            return _STATUS_PLAYING
        if state == STATE_PAUSED:
            return _STATUS_PAUSED
        return _STATUS_STOPPED

    @property
    def position_us(self) -> int:
        return self.player.position_ms() * 1000

    @property
    def volume(self) -> float:
        return self._settings.volume / 100.0

    def set_volume(self, value: float):
        self.player.set_volume(max(0, min(100, int(round(value * 100)))))

    def metadata(self) -> dict[str, Variant]:
        track = self.player.current_track
        if track is None or not track.path:
            return {
                "mpris:trackid": Variant("o", NO_TRACK_PATH),
                "mpris:length": Variant("x", 0),
                "xesam:title": Variant("s", "PyAmp"),
            }
        duration_ms = track.duration_ms or self.player.duration_ms()
        result: dict[str, Variant] = {
            "mpris:trackid": Variant("o", track_object_path(track)),
            "mpris:length": Variant("x", int(duration_ms) * 1000),
            "xesam:title": Variant("s", track.display_title),
        }
        if track.artist:
            result["xesam:artist"] = Variant("as", [track.artist])
        if track.album:
            result["xesam:album"] = Variant("s", track.album)
        if self._art_path:
            art = Path(self._art_path)
            if art.is_file():
                result["mpris:artUrl"] = Variant("s", art.as_uri())
        return result

    # ------------------------------------------------------------ callbacks
    def request_raise(self):
        if self._on_raise is not None:
            self._on_raise()

    def request_quit(self):
        if self._on_quit is not None:
            self._on_quit()
