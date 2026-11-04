from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AudioSink:
    name: str
    description: str
    is_bluetooth: bool = False

    @property
    def label(self) -> str:
        return f"🎧 {self.description}" if self.is_bluetooth else self.description


def _run_pactl(*args: str, timeout: float = 2.0) -> str:
    if sys.platform != "linux":
        return ""
    try:
        result = subprocess.run(
            ["pactl", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout if result.returncode == 0 else ""


def _pactl_ok(*args: str, timeout: float = 2.0) -> bool:
    if sys.platform != "linux":
        return False
    try:
        result = subprocess.run(
            ["pactl", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def _load_json_list(*args: str) -> list[dict[str, object]]:
    raw = _run_pactl("-f", "json", *args)
    if not raw.strip():
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _is_bluetooth(name: str, properties: dict[str, object]) -> bool:
    values = " ".join(
        [
            name,
            str(properties.get("device.bus", "")),
            str(properties.get("device.icon_name", "")),
            str(properties.get("device.description", "")),
            str(properties.get("device.api", "")),
        ]
    ).casefold()
    return any(word in values for word in ("bluez", "bluetooth", "audio-headset", "a2dp"))


def _clean_description(name: str, value: object) -> str:
    text = str(value or "").strip()
    if text and text.casefold() not in {"(null)", "null", "none"}:
        return text
    # PipeWire suele devolver description "(null)"; el nombre del sink es
    # feo pero reconocible: bluez_output.AC_12... o alsa_output....
    return name


def list_audio_sinks() -> list[AudioSink]:
    sinks: list[AudioSink] = []
    for item in _load_json_list("list", "sinks"):
        name = str(item.get("name") or "").strip()
        if not name or name.endswith(".monitor"):
            continue
        properties = item.get("properties")
        props = properties if isinstance(properties, dict) else {}
        description = _clean_description(
            name, props.get("device.description") or item.get("description")
        )
        sinks.append(AudioSink(name, description, _is_bluetooth(name, props)))
    if sinks:
        return sinks

    # Respaldo para versiones antiguas de pactl sin salida JSON.
    for line in _run_pactl("list", "short", "sinks").splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        name = parts[1].strip()
        if not name or name.endswith(".monitor"):
            continue
        sinks.append(AudioSink(name, name, _is_bluetooth(name, {})))
    return sinks


def default_sink_name() -> str:
    return _run_pactl("get-default-sink").strip()


def resolve_audio_device(preferred: str = "") -> str:
    """Devuelve el sink que debe usar PyAmp.

    - Si el usuario eligió uno y sigue disponible, se respeta.
    - Si no, se prefiere un dispositivo Bluetooth conectado.
    - Si no hay Bluetooth, se usa el destino predeterminado del sistema.
    """
    sinks = list_audio_sinks()
    names = {sink.name for sink in sinks}
    wanted = preferred.strip()
    if wanted and wanted in names:
        return wanted
    for sink in sinks:
        if sink.is_bluetooth:
            return sink.name
    fallback = default_sink_name()
    return fallback if fallback in names else ""


def _own_client_ids() -> set[str]:
    pid = str(os.getpid())
    own: set[str] = set()
    for client in _load_json_list("list", "clients"):
        properties = client.get("properties")
        props = properties if isinstance(properties, dict) else {}
        if str(props.get("application.process.id", "")) != pid:
            continue
        client_id = props.get("object.id") or client.get("index")
        if client_id is not None:
            own.add(str(client_id))
    return own


def _own_sink_inputs() -> list[tuple[int, int]]:
    own_clients = _own_client_ids()
    if not own_clients:
        return []
    result: list[tuple[int, int]] = []
    for item in _load_json_list("list", "sink-inputs"):
        properties = item.get("properties")
        props = properties if isinstance(properties, dict) else {}
        if str(props.get("client.id", "")) not in own_clients:
            continue
        try:
            index = int(str(item.get("index") or "0"))
            sink_index = int(str(item.get("sink") or "0"))
        except (TypeError, ValueError):
            continue
        if index > 0:
            result.append((index, sink_index))
    return result


def _sink_names_by_index() -> dict[int, str]:
    result: dict[int, str] = {}
    for item in _load_json_list("list", "sinks"):
        try:
            index = int(str(item.get("index") or "0"))
        except (TypeError, ValueError):
            continue
        name = str(item.get("name") or "").strip()
        if index > 0 and name:
            result[index] = name
    return result


def move_own_audio_streams(sink_name: str) -> int:
    if not sink_name:
        return 0
    sink_names = _sink_names_by_index()
    moved = 0
    for index, sink_index in _own_sink_inputs():
        # Mover un flujo que ya está en el destino provoca un pequeño corte
        # (y a veces un pitido). Se omite si no hace falta.
        if sink_names.get(sink_index) == sink_name:
            continue
        if _pactl_ok("move-sink-input", str(index), sink_name):
            moved += 1
    return moved
