import json
from typing import Optional, Tuple


class Regions:
    def __init__(self) -> None:
        self.HEALTH_BAR_REGION: Optional[Tuple[int, int, int, int]] = None
        self.LOOT_REGION: Optional[Tuple[int, int, int, int]] = None


REGIONS = Regions()


def save_calibration(path: str = 'region_config.json') -> None:
    config = {
        'HEALTH_BAR_REGION': REGIONS.HEALTH_BAR_REGION,
        'LOOT_REGION': REGIONS.LOOT_REGION,
    }
    with open(path, 'w') as f:
        json.dump(config, f)


def load_calibration(path: str = 'region_config.json') -> bool:
    try:
        with open(path, 'r') as f:
            config = json.load(f)
        REGIONS.HEALTH_BAR_REGION = tuple(config['HEALTH_BAR_REGION'])  # type: ignore[arg-type]
        REGIONS.LOOT_REGION = tuple(config['LOOT_REGION'])  # type: ignore[arg-type]
        return True
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError):
        return False


