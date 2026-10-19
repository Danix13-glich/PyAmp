from __future__ import annotations


def format_time(ms: int | float | None) -> str:
    total = 0 if ms is None or ms != ms else max(0, int(ms)) // 1000  # None o NaN -> 0
    hours, rest = divmod(total, 3600)
    minutes, seconds = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def format_remaining(ms: int | float | None) -> str:
    return f"-{format_time(ms)}"


def parse_time(text: str) -> int:
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
