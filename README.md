# Belen — Asistente por Voz para macOS

Asistente por voz personal que combina **STT + opencode + TTS** en un daemon para macOS. Hablale, te escucha, consulta a opencode (con GLM-5.1 o cualquier modelo), y te responde hablando. Con ventana visual estilo Siri.

## 🎙️ Cómo funciona

```
┌────────────────────────────────────────────────────────────┐
│  VENTANA VISUAL (siempre presente)                         │
│                                                            │
│              ┌──────────────────┐                          │
│              │  ◯  Belen        │  ← gris = idle           │
│              │                  │                          │
│              │  ⌥ + Z + ,       │  ← recordá la hotkey     │
│              │  o decí "Belen"  │                          │
│              │                  │                          │
│              │  tu texto...     │  ← aparece tu voz        │
│              │  respuesta...    │  ← respuesta de Belen    │
│              └──────────────────┘                          │
│                                                            │
└────────────────────────────────────────────────────────────┘

FLUJO CUANDO APRETÁS LA HOTKEY ⌥+Z+,:

  1. 🤚 Vos apretás: Option + Z + ,
  2. 🔴 El orbe se pone ROJO + texto "Escuchando..."
  3. 🗣️ Hablás mientras la hotkey está apretada
  4. 🤚 Soltás la hotkey
  5. 🟡 Orbe AMARILLO + "Pensando..." (transcribe tu voz)
  6. 🧠 Belen consulta opencode + GLM-5.1
  7. 🟢 Orbe VERDE + "Hablando..." (reproduce por audio)
  8. ⚪ Vuelve a idle, esperándote
```

## 🎬 Estados visuales del orbe

| Estado | Color | Significado |
|--------|-------|-------------|
| ⚪ IDLE | Gris | Esperando que hables |
| 🔴 LISTENING | Rojo | Estás hablando ahora |
| 🟡 PROCESSING | Amarillo | Belen está pensando |
| 🟢 SPEAKING | Verde | Belen te está respondiendo |
| ❌ ERROR | Rojo oscuro | Algo falló |

## ⌨️ Cómo usarlo

1. **Abrí la Terminal** y ejecutá:
   ```bash
   cd "/Users/druminot/Documents/Codigos Varios/Asistente por Voz (Belen)"
   source .venv/bin/activate
   belen start
   ```

2. **Aceptá los permisos** la primera vez:
   - System Settings → Privacy & Security → **Microphone** → agregar Terminal
   - System Settings → Privacy & Security → **Accessibility** → agregar Terminal

3. **Mirá la ventana** que aparece arriba en el centro de la pantalla — vas a ver el orbe gris pulsando.

4. **Apretá `Option + Z + ,` (mantener)** y hablá. Soltá cuando termines. Belen te escucha, piensa y te responde hablando.

5. **Si la hotkey no funciona** porque choca con otra app, podés cambiar a modo toggle con `BELEN_HOTKEY_MODE=toggle` en `.env` — apretás una vez para empezar, otra vez para parar.

6. **O usá el wake word**: decí "Belen" y empezá a hablar (sin apretar nada).

7. **Para salir**: `Ctrl+C` en la Terminal.

## 🛠️ Comandos disponibles

| Comando | Qué hace |
|---------|----------|
| `belen start` | Arranca el daemon con la UI visual |
| `belen start --no-ui` | Arranca sin ventana (solo terminal) |
| `belen start --project /path` | Arranca apuntando a un proyecto específico |
| `belen ask "pregunta"` | Manda una pregunta a opencode sin audio |
| `belen check` | Verifica que todo esté instalado |
| `belen models` | Lista los modelos LLM disponibles en opencode |
| `belen config` | Muestra la configuración actual |

## 🎤 Comandos de voz

Además de hablar normalmente, podés:

- **"Belen, andá al proyecto `nombre`"** — cambia el proyecto activo (lee de `BELEN_PROJECTS_DIR`)
- **"Belen, abrí `foo`"** — alias del anterior
- **"Belen, cambiá a `bar`"** — alias del anterior
- **Hablar normal** — le pasa todo a opencode + GLM-5.1

## 🧠 Cerebro

Usa **opencode** CLI con el modelo **GLM-5.1** de Zhipu AI (flagship para agentic engineering, comparable a Claude Opus 4.6). Podés cambiar el modelo editando `OPENCODE_MODEL` en `.env`:
- `ollama-cloud/glm-5.1` (default)
- `ollama-cloud/glm-5.2`
- `ollama-cloud/minimax-m3`
- `ollama-cloud/qwen3-coder-next`
- `ollama-cloud/deepseek-v3.2`
- Y muchos más (listá con `belen models`)

## ⚙️ Configuración

Toda la config se hace vía `.env`. Las claves más importantes:

| Variable | Default | Descripción |
|----------|---------|-------------|
| `OPENCODE_MODEL` | `ollama-cloud/glm-5.1` | Modelo LLM a usar |
| `BELEN_HOTKEY` | `option+z+comma` | Combinación para push-to-talk |
| `BELEN_HOTKEY_MODE` | `push_to_talk` | `push_to_talk` o `toggle` |
| `BELEN_WAKEWORD_ENABLED` | `true` | Activar wake word "Belen" |
| `BELEN_WAKEWORD` | `belen` | Palabra de activación |
| `BELEN_STT_ENGINE` | `vibevoice-asr` | Motor de STT |
| `BELEN_TTS_ENGINE` | `vibevoice-realtime` | Motor de TTS |
| `BELEN_PROJECTS_DIR` | `~/Documents/Codigos Varios` | Carpeta de proyectos |
| `BELEN_ALLOW_FILE_EDIT` | `true` | Permitir que opencode edite archivos |

Ver `.env.example` para la lista completa.

## 🏗️ Arquitectura

```
Hotkey (⌥+Z+,) o Wake word ("Belen")
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
    Brain (opencode CLI + GLM-5.1 vía Ollama cloud)
        ↓
    TTS (VibeVoice-Realtime-0.5B / Piper / macOS say)
        ↓
    Speaker + UI visual (orbe pulsante estilo Siri)
```

## 🛡️ Seguridad

- opencode corre con `--cwd=<proyecto>` para limitar el alcance.
- Comandos bash deshabilitados.
- `safety.py` bloquea `rm -rf`, `sudo`, etc. antes de enviar a opencode.

## 📦 Instalación

```bash
git clone https://github.com/druminot/asistente-por-voz-belen.git
cd asistente-por-voz-belen
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
belen check   # verificá que todo funcione
belen start   # arrancá!
```

Con modelos pesados (VibeVoice-ASR 7B + VibeVoice-Realtime 0.5B):
```bash
pip install -e ".[all]"
```

## Repo

https://github.com/druminot/asistente-por-voz-belen
