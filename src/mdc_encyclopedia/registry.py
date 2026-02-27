"""Jurisdiction registry loader for MDC Open Data Encyclopedia.

Loads jurisdiction configuration from a YAML file with a fallback chain:
  1. Explicit path argument
  2. MDC_ENCYCLOPEDIA_JURISDICTIONS environment variable
  3. ~/.local/share/mdc-encyclopedia/jurisdictions.yaml (user data dir)
  4. Package default (jurisdictions.yaml shipped alongside this module)
"""

import os
from pathlib import Path

import yaml

DEFAULT_CONFIG = Path(__file__).parent / "jurisdictions.yaml"


def load_registry(config_path: str | None = None) -> dict:
    """Load jurisdiction registry from YAML config.

    Priority: explicit path > env var > user data dir > package default.

    Args:
        config_path: Optional explicit path to a jurisdictions.yaml file.

    Returns:
        Dict mapping jurisdiction slugs to their configuration dicts.
        Each value has keys: display_name, hub_url, portal_type.

    Raises:
        FileNotFoundError: If no config file is found at any location.
        ValueError: If the config file is empty or missing the
            'jurisdictions' key.
    """
    if config_path is None:
        config_path = os.environ.get("MDC_ENCYCLOPEDIA_JURISDICTIONS")
    if config_path is None:
        user_config = (
            Path.home() / ".local" / "share" / "mdc-encyclopedia" / "jurisdictions.yaml"
        )
        if user_config.exists():
            config_path = str(user_config)
    if config_path is None:
        config_path = str(DEFAULT_CONFIG)

    with open(config_path) as f:
        data = yaml.safe_load(f)

    if not data or "jurisdictions" not in data:
        raise ValueError(
            f"Invalid jurisdiction config at {config_path}: "
            "file is empty or missing 'jurisdictions' key"
        )

    return data["jurisdictions"]


def get_jurisdiction(slug: str, config_path: str | None = None) -> dict:
    """Get configuration for a single jurisdiction by slug.

    Args:
        slug: Jurisdiction slug (e.g., 'miami-dade', 'broward', 'miami').
        config_path: Optional explicit path to a jurisdictions.yaml file.

    Returns:
        Dict with keys: display_name, hub_url, portal_type.

    Raises:
        KeyError: If the slug is not found. The error message lists
            all available slugs.
    """
    registry = load_registry(config_path)
    if slug not in registry:
        available = ", ".join(sorted(registry.keys()))
        raise KeyError(
            f"Unknown jurisdiction '{slug}'. Available: {available}"
        )
    return registry[slug]
