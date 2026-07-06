# Instalación de dependencias

## Setup rápido (macOS)

```bash
cd "Asistente por Voz (Belen)"
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Con todos los extras opcionales

```bash
pip install -e ".[all]"
```

Esto incluye:
- `[stt-vibevoice]` — transformers + torch para VibeVoice-ASR
- `[stt-whisper]` — faster-whisper como fallback STT
- `[tts-vibevoice]` — vibevoice para TTS state-of-the-art
- `[wakeword]` — openwakeword para detectar "Belen"
- `[dev]` — pytest, ruff, mypy

## Solo lo mínimo (sin modelos de IA pesados)

```bash
pip install -e .
```

Incluye: hotkey, recorder, UI flotante, feedback sonoro. Suficiente para testear el flujo de captura de audio.

## Verificar instalación

```bash
belen check
```

Esto verifica:
- Versión de Python
- Que `opencode` esté en PATH
- Micrófonos detectados
- Carpeta de proyectos exista

## Instalar opencode

```bash
curl -fsSL https://opencode.ai/install | bash
```

## Instalar Ollama (opcional, si no lo tenés)

```bash
brew install ollama
ollama serve
# En otra terminal:
ollama pull minimax-m3
```
