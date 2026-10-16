# Changelog

Todo notable de PyAmp se documenta aquí.

El formato se basa en [Keep a Changelog](https://keepachangelog.com/es-1.1.0/),
y el proyecto sigue [SemVer](https://semver.org/lang/es/spec/v2.0.0.html).

## [Unreleased]

### Added
- Estructura inicial del proyecto (Fase 0).
- `main.py` que abre una ventana vacía titulada "PyAmp".
- `src/app/version.py` con `__version__ = "0.1.0"`.
- `src/app/notifications/notifier.py`: interfaz completa y `format_track_notification` (PyAmp / título / artista).
- Configuración de proyecto: `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`.
- CI en GitHub Actions (ruff + black + mypy + pytest) en Linux, Windows y macOS (Python 3.11 y 3.12).
- Plantillas de issues y pull requests.
- Documentación inicial: README (EN/ES), CONTRIBUTING, CODE_OF_CONDUCT, SECURITY.

[Unreleased]: https://github.com/Danix13-glich/PyAmp/compare/v0.1.0...HEAD
