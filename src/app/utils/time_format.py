"""Formato de tiempo para el display y la playlist."""

from __future__ import annotations


def format_time(ms: int | float | None) -> str:
    """Convierte milisegundos a ``m:ss`` (o ``h:mm:ss`` si supera la hora).

    Valores negativos, None o no disponibles se muestran como ``0:00``.

    Args:
        ms: Tiempo en milisegundos.

    Returns:
        Texto tipo ``"3:45"``, ``"1:02:03"`` u ``"0:00"``.
    """
    total = 0 if ms is None or ms != ms else max(0, int(ms)) // 1000  # None o NaN -> 0
    hours, rest = divmod(total, 3600)
    minutes, seconds = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def format_remaining(ms: int | float | None) -> str:
    """Igual que :func:`format_time` pero con signo menos (estilo Winamp).

    Args:
        ms: Tiempo restante en milisegundos.

    Returns:
        Texto tipo ``"-3:45"``.
    """
    return f"-{format_time(ms)}"


def parse_time(text: str) -> int:
    """Convierte ``m:ss`` o ``h:mm:ss`` a milisegundos.

    Args:
        text: Texto de tiempo.

    Returns:
        Tiempo en milisegundos.

    Raises:
        ValueError: Si el texto no tiene un formato de tiempo válido.
    """
    parts = text.strip().split(":")
    if not 2 <= len(parts) <= 3:
        raise ValueError(f"Tiempo no válido: {text!r}")
    numbers = [int(p) for p in parts]
    if len(numbers) == 2:
        minutes, seconds = numbers
        hours = 0
    else:
        hours, minutes, seconds = numbers
    return ((hours * 60 + minutes) * 60 + seconds) * 1000
