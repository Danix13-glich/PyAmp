"""Paquete de aplicación PyAmp.

Contiene la UI, la lógica de negocio y los servicios (player, biblioteca,
radio, letras, notificaciones, temas). La UI nunca habla directamente con
VLC ni con SQLite: todo pasa por `core/` y `library/`.
"""
