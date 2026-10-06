import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

DELIVERY_METHODS = {
    "cdek": "СДЭК",
    "boxberry": "Boxberry",
    "energy": "Энергия",
    "kit": "КИТ",
    "avito": "Авито",
    "ozon": "OZON",
}


def allowed_delivery_methods(city_code: str) -> set[str]:
    common = {"cdek", "boxberry", "energy", "kit"}
    return common | ({"avito", "ozon"} if city_code == "vlg" else set())

load_dotenv(BASE_DIR / ".env")


def _admin_ids() -> tuple[int, ...]:
    raw = os.getenv("ADMIN_IDS", os.getenv("ADMIN_ID", ""))
    values = []
    for part in re.split(r"[,;\s]+", raw.strip()):
        if not part:
            continue
        try:
            value = int(part)
        except ValueError as exc:
            raise RuntimeError(f"Некорректный ADMIN_IDS: {part}") from exc
        if value > 0 and value not in values:
            values.append(value)
    return tuple(values)


@dataclass(frozen=True)
class Config:
    bot_token: str = os.getenv("BOT_TOKEN", "").strip()
    admin_ids: tuple[int, ...] = _admin_ids()
    db_path: Path = BASE_DIR / "data" / "bot.db"
    legacy_cny_low: float = 13.6
    legacy_cny_high: float = 13.3
    legacy_usd: float = 93.0
    delivery_msk_usd_kg: float = 4.0
    delivery_vlg_usd_kg: float = 6.0
    service_fee_percent: float = 0.04
    service_fee_min_rub: float = 400.0
    target_pool_weight: float = 5.0
    max_price_cny: float = 999_999.0
    max_weight_kg: float = 150.0

    def is_admin(self, user_id: int | None) -> bool:
        return user_id is not None and user_id in self.admin_ids

    def validate(self) -> None:
        if not self.bot_token:
            raise RuntimeError("BOT_TOKEN не задан в .env")
        if not self.admin_ids:
            raise RuntimeError("ADMIN_IDS не задан в .env")


config = Config()
