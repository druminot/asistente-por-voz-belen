# AGENTS.md — Asistente por Voz (Belen)

Reglas de operación del agente para este repositorio. El objetivo es mantener el repo en GitHub sincronizado de forma automática a medida que avanzamos.

## Sincronización automática con GitHub

Después de **cada** cambio de archivos (crear, editar o borrar), el agente DEBE ejecutar el siguiente flujo de commit + push sin pedir confirmación:

```bash
cd "/Users/druminot/Documents/Codigos Varios/Asistente por Voz (Belen)"
git add -A
git commit -m "<mensaje descriptivo corto de lo que cambió>"
git push origin main
```

Reglas del flujo:
- **Ruta fija del proyecto**: `/Users/druminot/Documents/Codigos Varios/Asistente por Voz (Belen)`
- **Remote**: `https://github.com/druminot/asistente-por-voz-belen.git` (rama `main`)
- **Commit por cada cambio lógico**: no acumular muchos cambios en un solo commit; agrupar por unidad de trabajo.
- **Mensaje en español, imperativo y breve** (ej: "Agrego script de captura de audio", "Corrijo bug en transcripción").
- **Si no hay cambios** (`nothing to commit`), omitir el commit y el push silenciosamente.
- **Si el push falla por conflicto o falta de red**, avisar al usuario con el error exacto y proponer solución; no forzar `push --force`.

## Configuración inicial (ya hecha)
1. Repo creado en GitHub: https://github.com/druminot/asistente-por-voz-belen
2. Carpeta local: `Documents/Codigos Varios/Asistente por Voz (Belen)`
3. Rama por defecto: `main`

## Arquitectura de Belen

```
Hotkey (Option+Z+,) o Wake word ("Belen")
        ↓
    Recorder (sounddevice, 16kHz, int16)
        ↓
    STT (VibeVoice-ASR / faster-whisper fallback)
        ↓
    Project selector (regex sobre transcripción)
        ↓ (si es comando de proyecto)
    Cambiar cwd del proyecto activo
        ↓ (si es prompt normal)
    Brain (opencode CLI + Ollama/minimax-m3)
        ↓
    Safety (validar prompt antes de enviar)
        ↓
    TTS (VibeVoice-Realtime-0.5B / Piper / macOS say)
        ↓
    Speaker (sounddevice reproduce audio)
        ↓
    Feedback visual (indicador flotante rumps/PyObjC)
```

## Stack técnico
- **Hotkey global**: pynput + Quartz (macOS)
- **Wake word**: openwakeword ("Belen", toggleable)
- **Captura audio**: sounddevice (PortAudio)
- **STT**: VibeVoice-ASR-7B (principal) / faster-whisper (fallback)
- **Cerebro**: opencode CLI + Ollama (minimax-m3)
- **TTS**: VibeVoice-Realtime-0.5B (principal) / Piper / macOS say (fallback)
- **UI flotante**: rumps + PyObjC (macOS status bar)
- **Orquestación**: Python 3.11+ con asyncio

## Decisiones de diseño
- Hotkey: `Option + Z + ,` (push-to-talk) + wake word "Belen" (toggleable)
- Permisos opencode: lectura + edición de archivos (sin bash)
- Directorio de trabajo: selector por voz
- Idioma principal: español (Latam)
- Feedback: indicador flotante con punto de color por estado

## Convenciones del proyecto
- Lenguaje principal: Python 3.11+
- Estructura: `src/belen/` — código fuente
- Tests: `tests/` — pytest
- Docs: `docs/` — documentación
- `pyproject.toml` — dependencias y config
- `.env` (nunca committed) para configuración
- `ruff` para linting, `mypy` para tipado, `pytest` para tests

## Optimización y compactación de contexto

Cuando el contexto de la conversación supere los **100k tokens**, el agente DEBE compactar el contexto antes de continuar:

1. **Resumir** lo realizado hasta el momento en un bloque `## Resumen de progreso` al inicio de la próxima respuesta.
2. **Cerrar archivos** que ya no se estén editando (no mantenerlos abiertos innecesariamente).
3. **No repetir** contenido que ya fue mostrado (ej: no re-imprimir todo un archivo si solo cambiaron 5 líneas).
4. **Referenciar por nombre** en vez de incluir el contenido completo (ej: "ver `src/belen/stt.py:42`" en vez de pegar 50 líneas).
5. Si el contexto supera **120k tokens**, el agente DEBE hacer un resumen agresivo: lista de archivos creados/modificados, estado de cada fase, y pendientes — SIN incluir código ya escrito.

Regla práctica: si la respuesta total (incluyendo tool calls) se acerca a los 100k tokens, compactar FIRST, THEN actuar.

## Lo que el agente NO debe hacer
- No hacer `git push --force` ni reescribir historial sin pedirlo.
- No commitear archivos con secretos reales (`.env`, credenciales, tokens).
- No crear commits vacíos.
- No saltar el push "para después" — cada cambio va a GitHub al terminar.

## Comandos útiles
- Instalar dependencias: `cd "Asistente por Voz (Belen)" && pip install -e ".[all]"`
- Lint: `ruff check src/belen/`
- Typecheck: `mypy src/belen/`
- Tests: `pytest tests/`
- Clonar en otra máquina: `git clone https://github.com/druminot/asistente-por-voz-belen.git`
- Ver estado: `git status`
- Ver historial: `git log --oneline -20`