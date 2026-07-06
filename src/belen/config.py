"""Configuración de Belen cargada desde .env + variables de entorno."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class HotkeyMode(StrEnum):
    PUSH_TO_TALK = "push_to_talk"
    TOGGLE = "toggle"


class STTEngine(StrEnum):
    VIBEVOICE_ASR = "vibevoice-asr"
    FASTER_WHISPER = "faster-whisper"


class TTSEngine(StrEnum):
    VIBEVOICE_REALTIME = "vibevoice-realtime"
    PIPER = "piper"
    MACOS_SAY = "macos-say"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    opencode_bin: str = Field(default="opencode", alias="OPENCODE_BIN")
    opencode_model: str = Field(default="ollama-cloud/glm-5.1", alias="OPENCODE_MODEL")
    opencode_base_url: str = Field(default="http://localhost:11434/v1", alias="OPENCODE_BASE_URL")
    opencode_agent: str = Field(default="", alias="OPENCODE_AGENT")

    belen_hotkey: str = Field(default="option+z+comma", alias="BELEN_HOTKEY")
    belen_hotkey_mode: HotkeyMode = Field(default=HotkeyMode.PUSH_TO_TALK, alias="BELEN_HOTKEY_MODE")

    belen_wakeword_enabled: bool = Field(default=True, alias="BELEN_WAKEWORD_ENABLED")
    belen_wakeword: str = Field(default="belen", alias="BELEN_WAKEWORD")

    belen_stt_engine: STTEngine = Field(default=STTEngine.VIBEVOICE_ASR, alias="BELEN_STT_ENGINE")
    belen_stt_lang: str = Field(default="es", alias="BELEN_STT_LANG")
    belen_whisper_model: str = Field(default="base", alias="BELEN_WHISPER_MODEL")

    belen_tts_engine: TTSEngine = Field(default=TTSEngine.VIBEVOICE_REALTIME, alias="BELEN_TTS_ENGINE")
    belen_tts_voice: str = Field(default="es_female", alias="BELEN_TTS_VOICE")

    belen_projects_dir: Path = Field(
        default=Path.home() / "Documents" / "Codigos Varios",
        alias="BELEN_PROJECTS_DIR",
    )
    belen_default_project: str = Field(default="", alias="BELEN_DEFAULT_PROJECT")

    belen_floating_ui: bool = Field(default=True, alias="BELEN_FLOATING_UI")

    belen_input_device: str = Field(default="", alias="BELEN_INPUT_DEVICE")
    belen_sample_rate: int = Field(default=16000, alias="BELEN_SAMPLE_RATE")

    belen_allow_file_edit: bool = Field(default=True, alias="BELEN_ALLOW_FILE_EDIT")
    belen_allowed_root: str = Field(default="", alias="BELEN_ALLOWED_ROOT")

    belen_save_recordings: bool = Field(default=False, alias="BELEN_SAVE_RECORDINGS")
    belen_log_level: str = Field(default="INFO", alias="BELEN_LOG_LEVEL")


_settings: Settings | None = None


def get_settings() -> Settings:
    """Singleton de configuración."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Recarga la configuración (útil en tests)."""
    global _settings
    _settings = Settings()
    return _settings
