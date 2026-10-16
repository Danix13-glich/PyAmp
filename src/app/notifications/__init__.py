"""Notificaciones de escritorio.

`notifier.Notifier` es la ÚNICA puerta de salida hacia el sistema de
notificaciones. Ningún widget ni el player deben lanzar notificaciones de
forma directa: se emite la señal global `track_changed` y el Notifier
reacciona.
"""
