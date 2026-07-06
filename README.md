# Belen — Asistente por Voz para macOS

Asistente por voz personal que combina **STT + opencode + TTS** en un daemon para macOS. Hablale, te escucha, consulta a opencode (con Ollama o cualquier modelo), y te responde hablando.

## Características

- 🎙️ **Push-to-talk**: mantené `Option + Z + ,` apretada para hablar.
- 🗣️ **Wake word** (opcional): decí "Belen" para empezar a grabar.
- 🧠 **Cerebro opencode**: cualquier modelo (Claude, GPT, Qwen, DeepSeek, Ollama local).
- 🔊 **TTS state-of-the-art**: VibeVoice-Realtime, Piper, o macOS `say` (fallback).
- 📁 **Selector de proyecto por voz**: "Belen, andá al proyecto foo".
- 🛡️ **Modo seguro**: opencode solo lee/edita archivos, sin comandos bash.
- 🎨 **UI flotante** en la barra de menús de macOS con punto de color por estado.
- 🇪🇸 **Español nativo** (también soporta 50+ idiomas vía VibeVoice-ASR).

## Requisitos

- macOS 11+ (Big Sur o superior)
- Python 3.11+
- [opencode](https://opencode.ai) instalado (`curl -fsSL https://opencode.ai/install | bash`)
- Permiso de **Micrófono** para la Terminal (Ajustes → Privacidad y seguridad)
- (Opcional) [Ollama](https://ollama.com) con un modelo local

## Instalación

```bash
git clone https://github.com/druminot/asistente-por-voz-belen.git
cd asistente-por-voz-belen
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
# Editá .env con tu config preferida
```

Con todos los extras opcionales (incluye VibeVoice-ASR, wake word, dev tools):

```bash
pip install -e ".[all]"
```

## Uso

### Iniciar el daemon

```bash
belen start
```

Esto:
1. Carga la configuración de `.env`.
2. Inicia el listener de hotkey.
3. Arranca la UI flotante (iconito en la barra superior de macOS).
4. Espera a que apretes la hotkey o digas "Belen".

### Probar el brain sin audio

```bash
belen ask "explicame este código en una línea"
belen ask "creá un script hello.py" --project /path/to/proj
belen ask "qué hace este archivo?" -m ollama-cloud/qwen3.5:397b
```

### Verificar el entorno

```bash
belen check
```

Verifica Python, opencode, micrófonos disponibles, y carpeta de proyectos.

### Listar modelos

```bash
belen models
```

Muestra todos los modelos disponibles en tu opencode (Claude, GPT, Qwen, DeepSeek, Ollama, etc.).

### Ver configuración

```bash
belen config
```

## Configuración

Toda la config se hace vía variables de entorno o `.env`. Las claves más importantes:

| Variable | Default | Descripción |
|----------|---------|-------------|
| `OPENCODE_MODEL` | `ollama-cloud/glm-5.1` | Modelo LLM a usar (Zhipu AI flagship, agentic) |
| `BELEN_HOTKEY` | `option+z+comma` | Combinación para push-to-talk |
| `BELEN_HOTKEY_MODE` | `push_to_talk` | `push_to_talk` o `toggle` |
| `BELEN_WAKEWORD_ENABLED` | `true` | Activar wake word "Belen" |
| `BELEN_WAKEWORD` | `belen` | Palabra de activación |
| `BELEN_STT_ENGINE` | `vibevoice-asr` | `vibevoice-asr` o `faster-whisper` |
| `BELEN_TTS_ENGINE` | `vibevoice-realtime` | `vibevoice-realtime`, `piper` o `macos-say` |
| `BELEN_PROJECTS_DIR` | `~/Documents/Codigos Varios` | Carpeta de proyectos |
| `BELEN_FLOATING_UI` | `true` | Mostrar indicador flotante |
| `BELEN_ALLOW_FILE_EDIT` | `true` | Permitir que opencode edite archivos |

Ver `.env.example` para la lista completa.

## Comandos de voz

- **Hablar normalmente**: "explicame qué hace este archivo"
- **Cambiar de proyecto**: "Belen, andá al proyecto smart-home" / "abrí belen" / "cambiá a medidor"
- **Comandos bash**: bloqueados por seguridad (aunque opencode no los ejecutaría igual)

## Arquitectura

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
    Safety (validar prompt)
        ↓
    Brain (opencode CLI + Ollama/minimax-m3)
        ↓
    TTS (VibeVoice-Realtime-0.5B / Piper / macOS say)
        ↓
    Speaker (sounddevice reproduce audio)
        ↓
    UI flotante (rumps)
```

## Estructura del proyecto

```
src/belen/
├── cli.py             # CLI con typer
├── config.py          # pydantic-settings
├── pipeline.py        # Orquestador principal
├── hotkey.py          # Listener de hotkey global
├── recorder.py        # Captura de micrófono
├── stt.py             # STT con VibeVoice-ASR + faster-whisper
├── brain.py           # Wrapper de opencode CLI
├── tts.py             # TTS multi-backend
├── wakeword.py        # Wake word "Belen" (openwakeword)
├── project_selector.py # Selector de proyecto por voz
├── ui.py              # UI flotante con rumps
├── feedback.py        # Beeps y status display
└── safety.py          # Validación de prompts
```

## Desarrollo

```bash
# Tests
pytest tests/           # 85 tests

# Lint
ruff check src/belen/

# Typecheck
mypy src/belen/
```

## Seguridad

- opencode corre con `--cwd=<proyecto>` para limitar el alcance.
- Comandos bash están deshabilitados en la config de opencode.
- `safety.py` bloquea patrones peligrosos (`rm -rf`, `sudo`, etc.) antes de enviar a opencode.
- Si una transcripción se interpreta mal, lo peor que puede pasar es editar/crear un archivo incorrecto.

## Roadmap

- [ ] Empaquetado como `.app` de macOS con py2app
- [ ] Streaming TTS para empezar a hablar antes de que termine la generación
- [ ] Hot-reload de skills
- [ ] Memoria persistente entre sesiones (vault estilo Obsidian)
- [ ] Speaker ID (voiceprint para que solo vos puedas activar a Belen)

## Licencia

MIT

## Repo

https://github.com/druminot/asistente-por-voz-belen
