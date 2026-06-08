"""Atlas20 Rotation research package."""

from ._version import __version__
from .config import ResearchConfig, load_config

__all__ = ["ResearchConfig", "__version__", "load_config"]
