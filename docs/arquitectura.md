# Arquitectura de Belen

## Flujo principal

```
┌──────────────────────────────────────────────────────┐
│         Belen Daemon (background Python)             │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │  Listener capa 1: Hotkey global             │    │
│  │  pynput + Quartz   (Option+Z+,)            │    │
│  └──────────────────┬──────────────────────────┘    │
│                     │ (si wake word está off)        │
│                     ▼                                │
│  ┌─────────────────────────────────────────────┐    │
│  │  Listener capa 2: Wake word (toggleable)    │    │
│  │  openwakeword  ("Belen")                    │    │
│  └──────────────────┬──────────────────────────┘    │
│                     │                                │
│                     ▼                                │
│  ┌─────────────────────────────────────────────┐    │
│  │  Recorder: captura mic → WAV                │    │
│  │  sounddevice (16kHz, int16)                 │    │
│  └──────────────────┬──────────────────────────┘    │
│                     │                                │
│                     ▼                                │
│  ┌─────────────────────────────────────────────┐    │
│  │  STT: VibeVoice-ASR (HF/local)             │    │
│  │  fallback: faster-whisper                  │    │
│  └──────────────────┬──────────────────────────┘    │
│                     │ texto del usuario              │
│                     ▼                                │
│  ┌─────────────────────────────────────────────┐    │
│  │  Detector de comando de proyecto            │    │
│  │  ("andá al proyecto X")                     │    │
│  └──────────────────┬──────────────────────────┘    │
│                     │ prompt / comando               │
│                     ▼                                │
│  ┌─────────────────────────────────────────────┐    │
│  │  Safety: validación de prompt               │    │
│  └──────────────────┬──────────────────────────┘    │
│                     │ prompt validado                │
│                     ▼                                │
│  ┌─────────────────────────────────────────────┐    │
│  │  Brain: opencode CLI subprocess             │    │
│  │  + Ollama (minimax-m3)                      │    │
│  │  permisos: read+write en cwd del proyecto   │    │
│  └──────────────────┬──────────────────────────┘    │
│                     │ respuesta texto                │
│                     ▼                                │
│  ┌─────────────────────────────────────────────┐    │
│  │  TTS: VibeVoice-Realtime-0.5B               │    │
│  │  fallback: Piper / macOS say                │    │
│  │  → audio + reproducción                     │    │
│  └─────────────────────────────────────────────┘    │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │  UI flotante: rumps + PyObjC               │    │
│  │  ⚪=idle  🔴=escuchando  🟡=pensando        │    │
│  │  🟢=hablando  ❌=error                       │    │
│  └─────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────┘
```

## Módulos

| Módulo | Responsabilidad | Fase |
|--------|----------------|------|
| `config.py` | Carga .env con pydantic-settings | 1 ✓ |
| `cli.py` | CLI con typer (`belen start`, `belen check`) | 1 ✓ |
| `hotkey.py` | Listener de hotkey global (pynput) | 2 |
| `recorder.py` | Captura de micrófono (sounddevice) | 2 |
| `stt.py` | Speech-to-text (VibeVoice-ASR + fallback) | 3 |
| `brain.py` | Wrapper de opencode CLI | 4 |
| `tts.py` | Text-to-speech (VibeVoice-Realtime + fallbacks) | 5 |
| `wakeword.py` | Wake word "Belen" (openwakeword) | 6 |
| `project_selector.py` | Selector de proyecto por voz | 7 |
| `feedback.py` | Beeps + indicador visual | 2/8 |
| `safety.py` | Validación de prompts | 1 ✓ |
| `pipeline.py` | Orquestación end-to-end | 9 |

## Seguridad

- opencode corre con `--cwd=<proyecto>` para limitar el alcance.
- Comandos bash deshabilitados en la config de opencode.
- `safety.py` bloquea patrones peligrosos antes de enviar a opencode.
- Si una transcripción se interpreta mal, lo peor que puede pasar es editar/crear un archivo incorrecto.

## Configuración

Ver `.env.example` para todas las opciones.