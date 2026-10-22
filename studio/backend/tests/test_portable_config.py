from pathlib import Path

from app.config import REPO_ROOT, Settings


def test_clean_install_defaults_are_local_and_opt_in():
    settings = Settings(_env_file=None)
    assert settings.studio_host == "127.0.0.1"
    assert settings.studio_port == 8220
    assert settings.comfy_url == "http://127.0.0.1:8218"
    assert settings.experimental_comfy_url == settings.comfy_url
    assert not settings.director_enabled
    assert not settings.director_openai_managed_gpu
    assert settings.director_openai_model_path == "optional-model.gguf"
    assert settings.director_openai_mmproj_path == "optional-mmproj.gguf"
    assert settings.data_dir == REPO_ROOT / "data"


def test_relative_directories_are_rooted_in_studio(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    settings = Settings(_env_file=None, data_dir="runtime", frontend_dist="frontend/dist")
    assert settings.data_dir == REPO_ROOT / "runtime"
    assert settings.frontend_dist == REPO_ROOT / "frontend/dist"


def test_prompt_chat_uses_neutral_creator_guidance():
    from app.services.director import H3_PROMPTING_GUIDE
    assert "Pachecodes : Kinjutsu" in H3_PROMPTING_GUIDE
    assert "Do not moralize" not in H3_PROMPTING_GUIDE
    assert "treat them as an adult" not in H3_PROMPTING_GUIDE
