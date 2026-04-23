from __future__ import annotations

import os
import tomllib
from pathlib import Path

from pydantic import BaseModel

from src.errors import ConfigInvalidError, ConfigMissingError
from src.storage import paths

DEFAULT_EXTRACTION_MODEL = "gpt-4.1"
PLACEHOLDER = "REPLACE_ME"


class Config(BaseModel):
    openai_api_key: str
    assemblyai_api_key: str
    vault_path: Path
    extraction_model: str = DEFAULT_EXTRACTION_MODEL


def write_skeleton(
    *,
    openai_api_key: str | None = None,
    assemblyai_api_key: str | None = None,
    vault_path: str | None = None,
    extraction_model: str = DEFAULT_EXTRACTION_MODEL,
    overwrite: bool = False,
) -> Path:
    """Write a config.toml skeleton at the configured home directory.

    Missing values are written as PLACEHOLDER so the user (or test) sees what's empty.
    Returns the path written.
    """
    home = paths.get_home()
    home.mkdir(parents=True, exist_ok=True)
    target = paths.config_path()
    if target.exists() and not overwrite:
        return target

    body = (
        "# podsave config — edit api keys before running.\n"
        "\n"
        "[api_keys]\n"
        f'openai = "{openai_api_key or PLACEHOLDER}"\n'
        f'assemblyai = "{assemblyai_api_key or PLACEHOLDER}"\n'
        "\n"
        "[paths]\n"
        f'vault = "{vault_path or paths.DEFAULT_VAULT}"\n'
        "\n"
        "[extraction]\n"
        f'model = "{extraction_model}"\n'
    )
    target.write_text(body)
    return target


def load_config() -> Config:
    """Load and validate config from ~/.podsave/config.toml.

    Environment variables (PODSAVE_OPENAI_API_KEY, PODSAVE_ASSEMBLYAI_API_KEY,
    PODSAVE_VAULT_PATH, PODSAVE_EXTRACTION_MODEL) override values from the file.
    """
    cfg_path = paths.config_path()
    if not cfg_path.exists():
        raise ConfigMissingError(
            f"config not found at {cfg_path} — run `podsave init` to create it"
        )

    raw = tomllib.loads(cfg_path.read_text())
    api_keys = raw.get("api_keys", {})
    paths_section = raw.get("paths", {})
    extraction = raw.get("extraction", {})

    openai_key = os.environ.get("PODSAVE_OPENAI_API_KEY", api_keys.get("openai", ""))
    assemblyai_key = os.environ.get(
        "PODSAVE_ASSEMBLYAI_API_KEY", api_keys.get("assemblyai", "")
    )
    vault = os.environ.get("PODSAVE_VAULT_PATH", paths_section.get("vault", paths.DEFAULT_VAULT))
    model = os.environ.get(
        "PODSAVE_EXTRACTION_MODEL", extraction.get("model", DEFAULT_EXTRACTION_MODEL)
    )

    missing: list[str] = []
    if not openai_key or openai_key == PLACEHOLDER:
        missing.append("openai")
    if not assemblyai_key or assemblyai_key == PLACEHOLDER:
        missing.append("assemblyai")
    if missing:
        names = ", ".join(missing)
        raise ConfigInvalidError(
            f"missing api keys: {names} — edit {cfg_path} or set "
            "PODSAVE_OPENAI_API_KEY / PODSAVE_ASSEMBLYAI_API_KEY"
        )

    return Config(
        openai_api_key=openai_key,
        assemblyai_api_key=assemblyai_key,
        vault_path=Path(vault).expanduser(),
        extraction_model=model,
    )
