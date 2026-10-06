from dataclasses import asdict, dataclass

from config import config
from database import db

PRICE_LIMIT_JOKE = (
    "Лимит на одну позицию — <b>999 999 ¥</b> :)\n\n"
    "Давайте укажем реальную стоимость товара."
)

WEIGHT_LIMIT_JOKE = (
    "Лимит отправки — <b>150 кг</b>.\n\n"
    "Давайте укажем реальный вес посылки (до 150 кг) :)"
)


@dataclass
class CalculationResult:
    price_cny: float
    goods_rub: float
    weight_kg: float
    city_name: str
    city_code: str
    delivery_type: str
    delivery_usd: float
    delivery_rub: float
    service_fee_rub: float
    total_rub: float
    cny_rate: float
    usd_rate: float
    delivery_method: str = ""
    consolidated_info: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def calculate_order(price_cny: float, weight_kg: float, city_code: str, delivery_method: str = "") -> CalculationResult:
    # Для выкупа используем два настраиваемых курса из БД. Курс посредника
    # в пользовательском расчёте не участвует. Граница 5 000 ₽ определяется
    # по розничному курсу, чтобы однозначно выбрать тариф до/от 5 000 ₽.
    rates = db.get_rates()
    cny_low = rates["cny_low"]
    cny_high = rates["cny_high"]
    usd_rate = rates["usd"]

    rough_goods_rub = price_cny * cny_low
    cny_rate = cny_high if rough_goods_rub >= 5000.0 else cny_low
    goods_rub = round(price_cny * cny_rate, 2)
    service_fee_rub = round(max(config.service_fee_min_rub, goods_rub * config.service_fee_percent), 2)

    if city_code == "msk":
        rate_usd_kg = config.delivery_msk_usd_kg
        city_name = "Москва"
        delivery_type = "Индивидуальная посылка (от 5 кг)"
        consolidated_info = None
    else:
        city_code = "vlg"
        rate_usd_kg = config.delivery_vlg_usd_kg
        city_name = "Волгоград"
        delivery_type = "Сборный груз (ВЛГ)"
        consolidated_info = db.pool_info()

    delivery_usd = round(weight_kg * rate_usd_kg, 2)
    delivery_rub = round(delivery_usd * usd_rate, 2)
    total_rub = round(goods_rub + service_fee_rub + delivery_rub, 2)

    return CalculationResult(
        price_cny=price_cny,
        goods_rub=goods_rub,
        weight_kg=weight_kg,
        city_name=city_name,
        city_code=city_code,
        delivery_type=delivery_type,
        delivery_usd=delivery_usd,
        delivery_rub=delivery_rub,
        service_fee_rub=service_fee_rub,
        total_rub=total_rub,
        cny_rate=cny_rate,
        usd_rate=usd_rate,
        delivery_method=delivery_method,
        consolidated_info=consolidated_info,
    )
