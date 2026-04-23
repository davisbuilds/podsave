from __future__ import annotations

from pathlib import Path

import pytest

from src.errors import ConfigInvalidError, ConfigMissingError
from src.storage import config as config_store
from src.storage import paths


def test_load_config_missing_file_raises(podsave_home: Path) -> None:
    with pytest.raises(ConfigMissingError) as ei:
        config_store.load_config()
    assert "podsave init" in str(ei.value)
    assert str(paths.config_path()) in str(ei.value)


def test_write_skeleton_creates_file_with_placeholders(podsave_home: Path) -> None:
    target = config_store.write_skeleton()
    assert target.exists()
    body = target.read_text()
    assert config_store.PLACEHOLDER in body


def test_write_skeleton_does_not_overwrite_existing(podsave_home: Path) -> None:
    config_store.write_skeleton(openai_api_key="first", assemblyai_api_key="first")
    config_store.write_skeleton(openai_api_key="second", assemblyai_api_key="second")
    assert "first" in paths.config_path().read_text()
    assert "second" not in paths.config_path().read_text()


def test_write_skeleton_overwrites_when_flagged(podsave_home: Path) -> None:
    config_store.write_skeleton(openai_api_key="first", assemblyai_api_key="first")
    config_store.write_skeleton(
        openai_api_key="second", assemblyai_api_key="second", overwrite=True
    )
    assert "second" in paths.config_path().read_text()


def test_load_config_with_placeholders_raises_invalid(podsave_home: Path) -> None:
    config_store.write_skeleton()
    with pytest.raises(ConfigInvalidError) as ei:
        config_store.load_config()
    msg = str(ei.value)
    assert "openai" in msg
    assert "assemblyai" in msg


def test_load_config_with_real_keys_succeeds(podsave_home: Path) -> None:
    config_store.write_skeleton(
        openai_api_key="sk-test", assemblyai_api_key="aa-test", vault_path="/tmp/vault"
    )
    cfg = config_store.load_config()
    assert cfg.openai_api_key == "sk-test"
    assert cfg.assemblyai_api_key == "aa-test"
    assert cfg.vault_path == Path("/tmp/vault")
    assert cfg.extraction_model == config_store.DEFAULT_EXTRACTION_MODEL


def test_env_vars_override_file_values(
    podsave_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_store.write_skeleton(openai_api_key="from-file", assemblyai_api_key="from-file")
    monkeypatch.setenv("PODSAVE_OPENAI_API_KEY", "from-env")
    monkeypatch.setenv("PODSAVE_ASSEMBLYAI_API_KEY", "from-env")
    monkeypatch.setenv("PODSAVE_EXTRACTION_MODEL", "gpt-test")
    cfg = config_store.load_config()
    assert cfg.openai_api_key == "from-env"
    assert cfg.assemblyai_api_key == "from-env"
    assert cfg.extraction_model == "gpt-test"
