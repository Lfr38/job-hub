"""Load and provide access to the job_search_config.yaml file."""
import os
import yaml
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

_CONFIG: Dict[str, Any] = None
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "job_search_config.yaml")


def load_config() -> Dict[str, Any]:
    """Load the YAML config file. Cached after first call."""
    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG

    if not os.path.exists(_CONFIG_PATH):
        logger.warning(f"Config file not found at {_CONFIG_PATH}, using defaults")
        _CONFIG = _default_config()
        return _CONFIG

    with open(_CONFIG_PATH, "r") as f:
        _CONFIG = yaml.safe_load(f)

    logger.info(f"Loaded config from {_CONFIG_PATH}")
    return _CONFIG


def get_config() -> Dict[str, Any]:
    """Get the config, loading it if needed."""
    return load_config()


def _default_config() -> Dict[str, Any]:
    """Fallback default config if YAML file is missing."""
    return {
        "ai": {"provider": "gemini"},
        "search": {
            "part_time": {"required": True, "keywords": ["part-time", "part time"]},
            "remote": {"required": True, "keywords": ["remote", "work from home", "anywhere"]},
        },
        "scoring": {
            "title_match": 30,
            "keyword_match": 10,
            "remote_bonus": 20,
            "part_time_bonus": 25,
            "ai_pass_threshold": 40,
        },
    }


# Install yaml if not present
try:
    import yaml
except ImportError:
    import subprocess
    subprocess.check_call(["pip", "install", "pyyaml", "-q"])
    import yaml
