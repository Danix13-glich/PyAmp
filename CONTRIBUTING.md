# Contribuir a PyAmp

¡Gracias por querer contribuir! Este documento explica cómo trabajar en el proyecto sin fricción.

## Flujo general

1. Abre una **issue** antes de cambios grandes (para no duplicar trabajo).
2. Haz un **fork** y crea tu rama desde `develop`:
   ```bash
   git checkout develop
   git checkout -b feature/mi-funcion
   ```
3. Haz commits con **[Conventional Commits](https://www.conventionalcommits.org/es/v1.0.0/)**:
   - `feat:` nueva funcionalidad
   - `fix:` corrección de bug
   - `docs:` documentación
   - `test:` tests
   - `chore:` mantenimiento, tooling, CI
   - `refactor:` cambios sin variar comportamiento
   - Ejemplo: `feat: añadir slider de balance`
4. Ejoca las comprobaciones localmente:
   ```bash
   ruff check src tests main.py
   black src tests main.py
   mypy
   pytest
   ```
5. Abre un **Pull Request** contra `develop` usando la plantilla.

## Ramas

- `main`: estable, solo cambios aprobados y probados.
- `develop`: integración, rama por defecto de los PRs.
- `feature/*`: funcionalidades nuevas.
- `fix/*`: correcciones.

## Convenciones de código

- Python 3.11+, type hints en todo el código nuevo, docstrings en español.
- Formato: `black` (línea 100) + lint: `ruff`. No desactivéis reglas sin comentarlo.
- Archivos y módulos en `snake_case`; clases en `PascalCase`.
- Señales Qt en pasado: `track_changed`, `playback_state_changed`.
- **La UI nunca habla directamente con VLC ni con SQLite**: todo pasa por `core/` y `library/`.
- **La UI y el player nunca lanzan notificaciones directamente**: todo pasa por `notifications/notifier.py`.
- Nada de lógica de negocio dentro de widgets.
- No se crean archivos fuera de la estructura del proyecto sin consultarlo en una issue.

## Tests

- Cada `fix` debe incluir test que lo reproduzca (si aplica).
- Los tests viven en `tests/` y se ejecutan con `pytest`.
- La CI ejecuta ruff, black, mypy y pytest en Linux, Windows y macOS: **el PR debe estar en verde**.

## Commits de versión y releases

- Versionado SemVer (`MAJOR.MINOR.PATCH`).
- Las releases las prepara la mantención a partir de tags `vX.Y.Z`, con artefactos publicados por GitHub Actions.
