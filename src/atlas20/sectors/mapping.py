"""Sector resolution logic from editable YAML rules."""

from __future__ import annotations

from dataclasses import dataclass

from atlas20.config import ResearchConfig, SectorConfig


@dataclass
class SectorResolver:
    """Resolve a single primary sector for each coin."""

    sector_config: SectorConfig

    def resolve_coin_sector(self, coin_id: str, name: str, categories: list[str] | None = None) -> str:
        coin_key = coin_id.lower()
        if coin_key in {key.lower(): value for key, value in self.sector_config.manual_overrides.items()}:
            manual = {key.lower(): value for key, value in self.sector_config.manual_overrides.items()}
            return manual[coin_key]

        name_lower = name.lower()
        category_values = [str(value).lower() for value in (categories or [])]

        for sector, keywords in self.sector_config.category_keyword_rules.items():
            if any(keyword.lower() in category for category in category_values for keyword in keywords):
                return sector

        for sector, keywords in self.sector_config.name_keyword_rules.items():
            if any(keyword.lower() in name_lower for keyword in keywords):
                return sector

        return self.sector_config.default_sector


def resolve_sector_map(config: ResearchConfig, sector_config: SectorConfig) -> SectorResolver:
    """Build a resolver instance for the active run."""
    _ = config
    return SectorResolver(sector_config=sector_config)
