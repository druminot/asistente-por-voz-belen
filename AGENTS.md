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

## Convenciones del proyecto
- Lenguaje principal: Python (asistente por voz con STT/TTS).
- Estructura sugerida:
  - `src/` — código fuente
  - `tests/` — pruebas
  - `docs/` — documentación
  - `requirements.txt` o `pyproject.toml` — dependencias
  - `README.md` — descripción general
- Usar variables de entorno (`.env`, nunca committed) para API keys (Whisper, ElevenLabs, etc.).
- Mantener `README.md` actualizado con instrucciones de uso.

## Lo que el agente NO debe hacer
- No hacer `git push --force` ni reescribir historial sin pedirlo.
- No commitear archivos con secretos reales (`.env`, credenciales, tokens).
- No crear commits vacíos.
- No saltar el push "para después" — cada cambio va a GitHub al terminar.

## Comandos útiles
- Clonar en otra máquina: `git clone https://github.com/druminot/asistente-por-voz-belen.git`
- Ver estado: `git status` (en la carpeta del proyecto)
- Ver historial: `git log --oneline -20`
