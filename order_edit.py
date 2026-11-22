"""Общие валидаторы и форматирование для редактирования тикетов клиентом и менеджером."""
import re
from html import escape

from config import config


class EditError(ValueError):
    """Ошибка валидации введённого значения (текст показывается пользователю)."""


CLIENT_NOT_EDITABLE = (
    "Этот заказ уже отправлен, отменён или доставлен — самостоятельно изменить его нельзя. "
    "Если нужно что-то поправить, напишите менеджеру."
)


def _number(raw: str | None) -> float:
    try:
        return float((raw or "").replace(",", ".").replace(" ", "").strip())
    except ValueError as exc:
        raise EditError("Введите число.") from exc


def parse_weight(raw: str | None) -> float:
    value = _number(raw)
    if not 0 < value <= config.max_weight_kg:
        raise EditError(f"Вес должен быть больше 0 и не более {config.max_weight_kg:g} кг.")
    return round(value, 2)


def parse_price(raw: str | None) -> float:
    value = _number(raw)
    if not 0 < value <= config.max_price_cny:
        raise EditError(f"Стоимость должна быть больше 0 и не более {config.max_price_cny:,.0f} ¥.".replace(",", " "))
    return round(value, 2)


def parse_total(raw: str | None) -> float:
    value = _number(raw)
    if not 0 <= value <= 100_000_000:
        raise EditError("Введите сумму от 0 до 100 000 000 ₽.")
    return round(value, 2)


def clean_text(raw: str | None, label: str, max_len: int) -> str:
    value = (raw or "").strip()
    if not value or len(value) > max_len:
        raise EditError(f"{label}: введите текст длиной от 1 до {max_len} символов.")
    return value


def clean_phone(raw: str | None) -> str:
    value = (raw or "").strip()
    digits = re.sub(r"\D", "", value)
    if not 7 <= len(digits) <= 15 or len(value) > 100:
        raise EditError("Введите корректный номер телефона (7–15 цифр).")
    return value


def fmt_weight(value) -> str:
    return f"{float(value):g} кг"


def fmt_cny(value) -> str:
    return f"{float(value):g} ¥"


def fmt_rub(value) -> str:
    return f"{float(value):.2f} ₽"


def change_line(label: str, old, new) -> str:
    old_text = str(old) if old not in (None, "") else "—"
    new_text = str(new) if new not in (None, "") else "—"
    return f"• {label}: {escape(old_text)} → <b>{escape(new_text)}</b>"


def reprice_lines(result: dict) -> list[str]:
    """Строки изменений после пересчёта заказа (вес/цена/город/сумма)."""
    old, new = result["old"], result["new"]
    lines = []
    if old["city_code"] != new["city_code"]:
        lines.append(change_line("Город прибытия", old["city_name"], new["city_name"]))
    if abs(float(old["weight_kg"]) - float(new["weight_kg"])) > 1e-9:
        lines.append(change_line("Вес", fmt_weight(old["weight_kg"]), fmt_weight(new["weight_kg"])))
    if abs(float(old["price_cny"]) - float(new["price_cny"])) > 1e-9:
        lines.append(change_line("Стоимость товара", fmt_cny(old["price_cny"]), fmt_cny(new["price_cny"])))
    if abs(float(old["total_rub"]) - float(new["total_rub"])) > 0.004:
        lines.append(change_line("Итоговая сумма", fmt_rub(old["total_rub"]), fmt_rub(new["total_rub"])))
    return lines
