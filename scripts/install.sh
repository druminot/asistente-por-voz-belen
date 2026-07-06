#!/bin/bash
# Script de instalación de Belen para macOS

set -e

echo "🎙️ Instalando Belen — Asistente por Voz para macOS"
echo

# 1. Verificar Python 3.11+
if ! command -v python3.11 &> /dev/null; then
    echo "❌ Python 3.11+ no encontrado."
    echo "   Instalá con: brew install python@3.11"
    exit 1
fi

# 2. Verificar opencode
if ! command -v opencode &> /dev/null; then
    echo "⚠️  opencode no encontrado. Instalando..."
    curl -fsSL https://opencode.ai/install | bash
fi

# 3. Crear venv
echo "📦 Creando entorno virtual..."
python3.11 -m venv .venv
source .venv/bin/activate

# 4. Instalar dependencias
echo "📥 Instalando dependencias..."
pip install --upgrade pip setuptools wheel
pip install -e .

# 5. Extras opcionales
read -p "¿Instalar modelos pesados (VibeVoice-ASR + wake word)? (s/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Ss]$ ]]; then
    pip install -e ".[stt-vibevoice,wakeword,dev]"
fi

# 6. Copiar .env
if [ ! -f .env ]; then
    cp .env.example .env
    echo "📝 Creado .env (editá con tu config)"
fi

# 7. Verificar
echo
echo "✅ Instalación completa. Verificando entorno:"
belen check

echo
echo "🚀 Para iniciar: belen start"
echo "   Para probar el brain sin audio: belen ask 'hola'"
