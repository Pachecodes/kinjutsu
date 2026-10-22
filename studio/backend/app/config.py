"""Runtime configuration for MiniMax H3 Studio.

Everything is environment driven with loopback-safe defaults so a bare
`uvicorn app.main:app` on the reference RTX 4090 workstation box binds privately and talks to the
H3 W4A8 lab Comfy instance on :8218 (never the stable service on :8215).
"""

from __future__ import annotations

import os
import shutil
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Comfy instance we are explicitly forbidden from touching.
STABLE_COMFY_PORT = 8215


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="H3_",
        env_file=(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    studio_host: str = "127.0.0.1"
    studio_port: int = 8220

    comfy_url: str = "http://127.0.0.1:8218"
    experimental_comfy_url: str = "http://127.0.0.1:8218"
    comfy_timeout_seconds: float = 30.0
    capability_ttl: float = 30.0

    data_dir: Path = REPO_ROOT / "data"
    frontend_dist: Path = REPO_ROOT / "frontend" / "dist"

    @field_validator("data_dir", "frontend_dist", mode="after")
    @classmethod
    def _root_directories(cls, value: Path) -> Path:
        return value if value.is_absolute() else REPO_ROOT / value

    max_image_mb: int = 32
    max_video_mb: int = 512
    max_audio_mb: int = 128

    ffprobe_path: str | None = None
    dev_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    #: Poll interval for the owned-job worker, seconds.
    poll_interval: float = Field(default=1.0, gt=0.0, le=30.0)

    # Local-only AI Director. The model is unloaded from VRAM after each preview.
    director_enabled: bool = False
    director_ollama_url: str = "http://127.0.0.1:11434"
    director_model: str = "openbmb/minicpm-o4.5:latest"
    director_text_model: str = "qwen3.5:9b"
    director_openai_url: str = "http://127.0.0.1:8083/v1"
    director_openai_model: str = "gemma4-e2b-h3-prompts-gpu"
    director_openai_managed_gpu: bool = False
    director_openai_executable: str = "llama-server.exe"
    director_openai_model_path: str = "optional-model.gguf"
    director_openai_mmproj_path: str = "optional-mmproj.gguf"
    director_openai_context_size: int = Field(default=8192, ge=2048, le=131072)
    director_openai_gpu_layers: int = Field(default=99, ge=0, le=999)
    director_openai_idle_seconds: float = Field(default=180.0, ge=10.0, le=3600.0)
    director_timeout_seconds: float = 300.0
    # Keep Ollama strictly manual so GPU models cannot appear while H3 renders.
    # Prompt Chat uses a Studio-owned CUDA llama.cpp process on :8083 and is
    # released before H3 submission; the CPU-only :8082 lane remains rollback.
    director_autostart_ollama: bool = False
    director_ollama_executable: str = "ollama"
    director_ollama_models: str | None = None

    @field_validator("director_openai_mmproj_path")
    @classmethod
    def _require_multimodal_projector(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Prompt Chat multimodal projector path cannot be empty")
        return value.strip()

    @field_validator("comfy_url", "experimental_comfy_url")
    @classmethod
    def _guard_stable_comfy(cls, value: str) -> str:
        value = value.rstrip("/")
        if f":{STABLE_COMFY_PORT}" in value:
            raise ValueError(
                f"Refusing to target the stable ComfyUI service on port {STABLE_COMFY_PORT}. "
                "H3 Studio must use the H3 W4A8 lab instance (default :8218)."
            )
        return value

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def outputs_dir(self) -> Path:
        return self.data_dir / "outputs"

    @property
    def thumbs_dir(self) -> Path:
        return self.data_dir / "thumbs"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "studio.sqlite3"

    @property
    def dev_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.dev_origins.split(",") if origin.strip()]

    def resolve_ffprobe(self) -> str | None:
        if self.ffprobe_path:
            return self.ffprobe_path
        return shutil.which("ffprobe")

    def ensure_dirs(self) -> None:
        for directory in (self.data_dir, self.uploads_dir, self.outputs_dir, self.thumbs_dir):
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    """Test hook - drop the cached Settings so env changes take effect."""
    get_settings.cache_clear()


def settings_from_env(**overrides: object) -> Settings:
    """Build a Settings instance ignoring the on-disk .env (used by tests)."""
    env = {key: value for key, value in os.environ.items() if key.startswith("H3_")}
    merged: dict[str, object] = {
        key[3:].lower(): value for key, value in env.items() if key[3:].lower() in Settings.model_fields
    }
    merged.update(overrides)
    return Settings(_env_file=None, **merged)  # type: ignore[arg-type]
