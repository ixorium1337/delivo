import io
import math
import re
from datetime import datetime

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from calculator import calculate_order
from config import config
from database import db

ORDER_HEADERS = [
    "ID тикета",
    "Telegram ID",
    "Статус",
    "Город",
    "Код города",
    "Вес (кг)",
    "Цена (CNY)",
    "Товар (RUB)",
    "Комиссия (RUB)",
    "Курс USD",
    "Итого (RUB)",
    "Способ доставки",
    "Получатель (ФИО)",
    "Телефон",
    "Адрес",
    "Описание / ссылка",
    "Трекеры",
    "В пуле ВЛГ",
    "ID отправления",
    "Карго-номер",
    "Название отправления",
    "Причина отказа",
    "Статус для клиента",
    "Создан",
    "Отправлен клиенту",
    "Доставлен",
]

SHIPMENT_HEADERS = [
    "ID отправления",
    "Город",
    "Название",
    "Карго-номер",
    "Статус",
    "Создан",
    "Прибыло",
    "Тикеты в составе",
]

STATUS_EXPORT_LABELS = {
    "pending": "На проверке",
    "accepted": "Принят",
    "shipped": "В пути",
    "delivered": "Доставлен",
    "rejected": "Отклонён",
}

SHIPMENT_STATUS_EXPORT_LABELS = {
    "forming": "Формируется",
    "sent_from_china": "Отправлено из Китая",
    "arrived": "Прибыло",
    "sorted": "Разобрано",
    "closed": "Закрыто",
}

ORDER_HEADER_ALIASES = {
    "id тикета": "order_id",
    "id заказа": "order_id",
    "тикет": "order_id",
    "номер заказа": "order_id",
    "order_id": "order_id",
    "id": "order_id",
    "telegram id": "user_id",
    "tg id": "user_id",
    "user_id": "user_id",
    "userid": "user_id",
    "клиент id": "user_id",
    "id клиента": "user_id",
    "id пользователя": "user_id",
    "телеграм id": "user_id",
    "статус": "status",
    "status": "status",
    "город": "city_name",
    "город прибытия": "city_name",
    "city": "city_name",
    "city_name": "city_name",
    "код города": "city_code",
    "city_code": "city_code",
    "вес (кг)": "weight_kg",
    "вес": "weight_kg",
    "weight": "weight_kg",
    "weight_kg": "weight_kg",
    "масса": "weight_kg",
    "цена (cny)": "price_cny",
    "цена в юанях": "price_cny",
    "цена cny": "price_cny",
    "стоимость (cny)": "price_cny",
    "стоимость cny": "price_cny",
    "cny": "price_cny",
    "price_cny": "price_cny",
    "цена": "price_cny",
    "стоимость": "price_cny",
    "товар (rub)": "goods_rub",
    "стоимость товара (rub)": "goods_rub",
    "goods_rub": "goods_rub",
    "товар руб": "goods_rub",
    "комиссия (rub)": "service_fee_rub",
    "комиссия": "service_fee_rub",
    "service_fee_rub": "service_fee_rub",
    "комиссия руб": "service_fee_rub",
    "курс usd": "usd_rate",
    "usd_rate": "usd_rate",
    "курс доллара": "usd_rate",
    "итого (rub)": "total_rub",
    "итого": "total_rub",
    "сумма": "total_rub",
    "сумма (rub)": "total_rub",
    "total_rub": "total_rub",
    "итого руб": "total_rub",
    "способ доставки": "delivery_method",
    "доставка": "delivery_method",
    "последняя миля": "delivery_method",
    "delivery_method": "delivery_method",
    "служба доставки": "delivery_method",
    "получатель (фио)": "recipient_name",
    "получатель": "recipient_name",
    "фио": "recipient_name",
    "recipient_name": "recipient_name",
    "имя": "recipient_name",
    "телефон": "recipient_phone",
    "номер телефона": "recipient_phone",
    "recipient_phone": "recipient_phone",
    "тел": "recipient_phone",
    "адрес": "recipient_address",
    "адрес доставки": "recipient_address",
    "recipient_address": "recipient_address",
    "описание / ссылка": "item_desc",
    "описание": "item_desc",
    "ссылка": "item_desc",
    "детали": "item_desc",
    "товар": "item_desc",
    "item_desc": "item_desc",
    "ссылка на товар": "item_desc",
    "трекеры": "trackers",
    "трек": "trackers",
    "трек-номер": "trackers",
    "трек-номера": "trackers",
    "trackers": "trackers",
    "tracker": "trackers",
    "в пуле влг": "in_pool",
    "в пуле": "in_pool",
    "пул": "in_pool",
    "in_pool": "in_pool",
    "id отправления": "shipment_id",
    "отправление id": "shipment_id",
    "shipment_id": "shipment_id",
    "карго-номер": "shipment_track_number",
    "название отправления": "shipment_name",
    "причина отказа": "reject_reason",
    "причина": "reject_reason",
    "reject_reason": "reject_reason",
    "статус для клиента": "status_message",
    "обновление статуса": "status_message",
    "status_message": "status_message",
    "создан": "created_at",
    "дата создания": "created_at",
    "дата": "created_at",
    "created_at": "created_at",
    "отправлен клиенту": "sent_to_client_at",
    "sent_to_client_at": "sent_to_client_at",
    "доставлен": "delivered_at",
    "delivered_at": "delivered_at",
}

SHIPMENT_HEADER_ALIASES = {
    "id отправления": "id",
    "id": "id",
    "город": "city_name",
    "city_name": "city_name",
    "название": "name",
    "name": "name",
    "карго-номер": "track_number",
    "track_number": "track_number",
    "статус": "status",
    "status": "status",
    "создан": "created_at",
    "created_at": "created_at",
    "прибыло": "arrived_at",
    "arrived_at": "arrived_at",
}


def _safe_excel_text(value: object) -> str:
    text = "" if value is None else str(value)
    if text.startswith("="):
        return "'" + text
    return text


def _style_sheet(ws, headers: list[str], widths: dict[int, int]) -> None:
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(col_idx)].width = widths.get(col_idx, 18)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{max(1, ws.max_row)}"


def export_database_to_excel(orders: list[dict], shipments: list[dict]) -> bytes:
    wb = Workbook()

    # Лист 1: Заказы
    ws_orders = wb.active
    ws_orders.title = "Заказы"
    for order in orders:
        shipment = order.get("shipment") or {}
        ws_orders.append([
            int(order["order_id"]),
            int(order["user_id"]),
            STATUS_EXPORT_LABELS.get(order.get("status", ""), order.get("status", "pending")),
            _safe_excel_text(order.get("city_name", "")),
            _safe_excel_text(order.get("city_code", "")),
            round(float(order.get("weight_kg") or 0.0), 2),
            round(float(order.get("price_cny") or 0.0), 2),
            round(float(order.get("goods_rub") or 0.0), 2),
            round(float(order.get("service_fee_rub") or 0.0), 2),
            round(float(order.get("usd_rate") or 0.0), 4),
            round(float(order.get("total_rub") or 0.0), 2),
            _safe_excel_text(order.get("delivery_method") or ""),
            _safe_excel_text(order.get("recipient_name") or ""),
            _safe_excel_text(order.get("recipient_phone") or ""),
            _safe_excel_text(order.get("recipient_address") or ""),
            _safe_excel_text(order.get("item_desc") or ""),
            _safe_excel_text(", ".join(order.get("trackers") or [])),
            "Да" if order.get("in_pool") else "Нет",
            int(shipment["id"]) if shipment.get("id") else (int(order["shipment_id"]) if order.get("shipment_id") else ""),
            _safe_excel_text(shipment.get("track_number") or ""),
            _safe_excel_text(shipment.get("name") or ""),
            _safe_excel_text(order.get("reject_reason") or ""),
            _safe_excel_text(order.get("status_message") or ""),
            _safe_excel_text(order.get("created_at") or ""),
            _safe_excel_text(order.get("sent_to_client_at") or ""),
            _safe_excel_text(order.get("delivered_at") or ""),
        ])

    # Заголовок и стили применяем после заполнения (или вставкой строки 1, чтобы auto_filter охватил все строки)
    ws_orders.insert_rows(1)
    for idx, title in enumerate(ORDER_HEADERS, start=1):
        ws_orders.cell(row=1, column=idx, value=title)
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    order_widths = {
        1: 11, 2: 14, 3: 15, 4: 13, 5: 11, 6: 11, 7: 12, 8: 13, 9: 14, 10: 11,
        11: 14, 12: 17, 13: 24, 14: 17, 15: 30, 16: 34, 17: 22, 18: 12, 19: 15,
        20: 18, 21: 22, 22: 24, 23: 28, 24: 18, 25: 18, 26: 18,
    }
    for col_idx in range(1, len(ORDER_HEADERS) + 1):
        cell = ws_orders.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws_orders.column_dimensions[get_column_letter(col_idx)].width = order_widths.get(col_idx, 18)
    ws_orders.freeze_panes = "A2"
    ws_orders.auto_filter.ref = f"A1:{get_column_letter(len(ORDER_HEADERS))}{max(1, ws_orders.max_row)}"

    # Лист 2: Отправления
    ws_ship = wb.create_sheet(title="Отправления")
    _style_sheet(
        ws_ship,
        SHIPMENT_HEADERS,
        {1: 15, 2: 14, 3: 24, 4: 20, 5: 20, 6: 18, 7: 18, 8: 26},
    )
    for ship in shipments:
        ws_ship.append([
            int(ship["id"]),
            _safe_excel_text(ship.get("city_name") or ""),
            _safe_excel_text(ship.get("name") or ""),
            _safe_excel_text(ship.get("track_number") or ""),
            SHIPMENT_STATUS_EXPORT_LABELS.get(ship.get("status", ""), ship.get("status", "forming")),
            _safe_excel_text(ship.get("created_at") or ""),
            _safe_excel_text(ship.get("arrived_at") or ""),
            _safe_excel_text(", ".join(str(x) for x in ship.get("order_ids", []))),
        ])
    ws_ship.auto_filter.ref = f"A1:{get_column_letter(len(SHIPMENT_HEADERS))}{max(1, ws_ship.max_row)}"

    # Лист 3: Инструкция
    ws_info = wb.create_sheet(title="Инструкция")
    ws_info.column_dimensions["A"].width = 28
    ws_info.column_dimensions["B"].width = 80
    info_rows = [
        ("Как добавить заказы", "Добавьте новые строки на лист «Заказы» и отправьте файл боту в админке."),
        ("ID тикета", "Оставьте пустым для автоматического номера или укажите новый ID. Строки с ID, уже существующими в БД, будут пропущены."),
        ("Обязательные поля", "Telegram ID, Город (Москва/Волгоград или msk/vlg), Вес (кг) > 0 и <= 150."),
        ("Авторасчёт суммы", "Если «Итого (RUB)» пусто или 0, а «Цена (CNY)» > 0, бот сам рассчитает рубли и комиссию по текущим курсам."),
        ("Допустимые статусы", "На проверке (pending), Принят (accepted), В пути (shipped), Доставлен (delivered), Отклонён (rejected)."),
        ("Трекеры", "Указывайте через запятую или точку с запятой."),
    ]
    ws_info.append(["Поле / правило", "Описание"])
    for col_idx in (1, 2):
        c = ws_info.cell(row=1, column=col_idx)
        c.fill = header_fill
        c.font = header_font
    for row in info_rows:
        ws_info.append(list(row))

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _norm_header(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def _is_empty_cell(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _parse_int(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("Ожидалось целое число")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value) or value != int(value):
            raise ValueError("Ожидалось целое число")
        return int(value)
    text = str(value).strip().replace("\xa0", "").replace(" ", "")
    if re.fullmatch(r"[+-]?\d+\.0+", text):
        text = text.split(".", 1)[0]
    return int(text)


def _parse_float(value: object) -> float:
    if isinstance(value, bool):
        raise ValueError("Ожидалось число")
    if isinstance(value, (int, float)):
        num = float(value)
    else:
        text = str(value).strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
        num = float(text)
    if not math.isfinite(num):
        raise ValueError("Некорректное число")
    return num


def _parse_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y %H:%M")
    if isinstance(value, float) and math.isfinite(value) and value == int(value):
        return str(int(value))
    return str(value).strip()


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(int(value))
    text = str(value or "").strip().casefold()
    return text in {"да", "yes", "true", "1", "+"}


def _parse_city(city_name_raw: object, city_code_raw: object) -> tuple[str, str]:
    code = _parse_text(city_code_raw).casefold()
    name = _parse_text(city_name_raw).casefold()
    if code in {"msk", "мск"} or name.startswith("моск") or name in {"msk", "мск"}:
        return "Москва", "msk"
    if code in {"vlg", "влг"} or name.startswith("волгог") or name in {"vlg", "влг"}:
        return "Волгоград", "vlg"
    raise ValueError("Укажите город: Москва (msk) или Волгоград (vlg)")


def _parse_order_status(raw: object) -> str:
    if _is_empty_cell(raw):
        return "pending"
    text = _parse_text(raw).casefold()
    text = re.sub(r"^[⏳✅🚚📬❌•\s]+", "", text).strip()
    mapping = {
        "pending": "pending",
        "на проверке у менеджера": "pending",
        "на проверке": "pending",
        "ожидает": "pending",
        "новый": "pending",
        "accepted": "accepted",
        "принят в работу": "accepted",
        "принят": "accepted",
        "в работе": "accepted",
        "shipped": "shipped",
        "в пути": "shipped",
        "отправлен": "shipped",
        "delivered": "delivered",
        "доставлен клиенту": "delivered",
        "доставлен": "delivered",
        "rejected": "rejected",
        "отклонён": "rejected",
        "отклонен": "rejected",
        "отменён": "rejected",
        "отменен": "rejected",
    }
    if text not in mapping:
        raise ValueError(f"Неизвестный статус «{_parse_text(raw)}»")
    return mapping[text]


def _parse_shipment_status(raw: object) -> str:
    if _is_empty_cell(raw):
        return "forming"
    text = _parse_text(raw).casefold()
    mapping = {
        "forming": "forming",
        "формируется": "forming",
        "sent_from_china": "sent_from_china",
        "отправлено из китая": "sent_from_china",
        "отправлен": "sent_from_china",
        "arrived": "arrived",
        "прибыло": "arrived",
        "прибыл": "arrived",
        "sorted": "sorted",
        "разобрано": "sorted",
        "closed": "closed",
        "закрыто": "closed",
    }
    return mapping.get(text, "forming")


def _pick_orders_sheet(wb):
    preferred = {"заказы", "orders", "тикеты", "tickets"}
    for name in wb.sheetnames:
        if name.strip().casefold() in preferred:
            return wb[name]
    return wb.active


def _parse_shipments_sheet(wb) -> list[dict]:
    preferred = {"отправления", "shipments"}
    ws = None
    for name in wb.sheetnames:
        if name.strip().casefold() in preferred:
            ws = wb[name]
            break
    if ws is None:
        return []

    rows_iter = ws.iter_rows(values_only=True)
    header_map: dict[int, str] = {}
    for row in rows_iter:
        if not any(not _is_empty_cell(v) for v in row):
            continue
        for idx, cell in enumerate(row):
            canonical = SHIPMENT_HEADER_ALIASES.get(_norm_header(cell))
            if canonical:
                header_map[idx] = canonical
        break
    if not header_map or "name" not in header_map.values():
        return []

    shipments = []
    for row in rows_iter:
        if not any(not _is_empty_cell(v) for v in row):
            continue
        raw = {field: row[idx] if idx < len(row) else None for idx, field in header_map.items()}
        name = _parse_text(raw.get("name"))
        city_raw = raw.get("city_name")
        if not name or _is_empty_cell(city_raw):
            continue
        try:
            city_name, _ = _parse_city(city_raw, None)
        except ValueError:
            city_name = _parse_text(city_raw)
        sid = None
        if not _is_empty_cell(raw.get("id")):
            try:
                sid = _parse_int(raw.get("id"))
            except ValueError:
                sid = None
        shipments.append({
            "id": sid,
            "city_name": city_name,
            "name": name[:200],
            "track_number": _parse_text(raw.get("track_number"))[:200] or "Ожидает карго-номер",
            "status": _parse_shipment_status(raw.get("status")),
            "created_at": _parse_text(raw.get("created_at")),
            "arrived_at": _parse_text(raw.get("arrived_at")) or None,
        })
    return shipments


def parse_orders_excel(file_bytes: bytes, existing_order_ids: set[int]) -> dict:
    try:
        wb = load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
    except Exception:
        return {"fatal_error": "Не удалось открыть файл. Убедитесь, что это корректный документ Excel (.xlsx)."}

    try:
        ws = _pick_orders_sheet(wb)
        if ws is None:
            return {"fatal_error": "В книге Excel не найдено ни одного листа."}

        sheet_name = ws.title
        new_shipments = _parse_shipments_sheet(wb)
        rates = db.get_rates()

        rows_iter = enumerate(ws.iter_rows(values_only=True), start=1)
        header_map: dict[int, str] = {}
        for _, row in rows_iter:
            if not any(not _is_empty_cell(v) for v in row):
                continue
            for idx, cell in enumerate(row):
                canonical = ORDER_HEADER_ALIASES.get(_norm_header(cell))
                if canonical and canonical not in header_map.values():
                    header_map[idx] = canonical
            break

        found_fields = set(header_map.values())
        if "user_id" not in found_fields or "weight_kg" not in found_fields or (
            "city_name" not in found_fields and "city_code" not in found_fields
        ):
            return {
                "fatal_error": (
                    f"На листе «{sheet_name}» не найдены обязательные колонки: "
                    "«Telegram ID», «Город» (или «Код города»), «Вес (кг)»."
                )
            }

        total_rows = 0
        new_orders: list[dict] = []
        skipped_existing: list[int] = []
        errors: list[tuple[int, str]] = []
        seen_file_ids: set[int] = set()

        for row_num, row in rows_iter:
            if total_rows >= 5000:
                errors.append((row_num, "Достигнут лимит 5000 строк на один импорт"))
                break
            raw = {field: row[idx] if idx < len(row) else None for idx, field in header_map.items()}
            if not any(not _is_empty_cell(v) for v in raw.values()):
                continue
            total_rows += 1

            try:
                order_id = None
                if not _is_empty_cell(raw.get("order_id")):
                    order_id = _parse_int(raw.get("order_id"))
                    if order_id <= 0:
                        raise ValueError("ID тикета должен быть > 0")
                    if order_id in existing_order_ids:
                        skipped_existing.append(order_id)
                        continue
                    if order_id in seen_file_ids:
                        raise ValueError(f"Дублирующийся ID тикета #{order_id} внутри файла")
                    seen_file_ids.add(order_id)

                if _is_empty_cell(raw.get("user_id")):
                    raise ValueError("Не указан Telegram ID")
                user_id = _parse_int(raw.get("user_id"))
                if user_id <= 0:
                    raise ValueError("Telegram ID должен быть > 0")

                if _is_empty_cell(raw.get("weight_kg")):
                    raise ValueError("Не указан вес (кг)")
                weight_kg = round(_parse_float(raw.get("weight_kg")), 2)
                if not 0 < weight_kg <= config.max_weight_kg:
                    raise ValueError(f"Вес должен быть от 0 до {config.max_weight_kg:g} кг")

                city_name, city_code = _parse_city(raw.get("city_name"), raw.get("city_code"))
                status = _parse_order_status(raw.get("status"))
                delivery_method = _parse_text(raw.get("delivery_method"))[:100]

                price_cny = 0.0
                if not _is_empty_cell(raw.get("price_cny")):
                    price_cny = round(_parse_float(raw.get("price_cny")), 2)
                    if price_cny < 0 or price_cny > config.max_price_cny:
                        raise ValueError(f"Цена в CNY должна быть от 0 до {config.max_price_cny:g}")

                total_rub = 0.0
                if not _is_empty_cell(raw.get("total_rub")):
                    total_rub = round(_parse_float(raw.get("total_rub")), 2)
                    if total_rub < 0:
                        raise ValueError("Итоговая сумма не может быть отрицательной")

                goods_rub = round(_parse_float(raw["goods_rub"]), 2) if not _is_empty_cell(raw.get("goods_rub")) else 0.0
                service_fee_rub = round(_parse_float(raw["service_fee_rub"]), 2) if not _is_empty_cell(raw.get("service_fee_rub")) else 0.0
                usd_rate = round(_parse_float(raw["usd_rate"]), 4) if not _is_empty_cell(raw.get("usd_rate")) else 0.0

                if total_rub == 0.0 and price_cny > 0:
                    calc = calculate_order(price_cny, weight_kg, city_code, delivery_method)
                    goods_rub = calc.goods_rub
                    service_fee_rub = calc.service_fee_rub
                    usd_rate = calc.usd_rate
                    total_rub = calc.total_rub
                elif usd_rate <= 0:
                    usd_rate = float(rates["usd"])

                trackers_raw = _parse_text(raw.get("trackers"))
                trackers = [t.strip()[:200] for t in re.split(r"[,;\n]+", trackers_raw) if t.strip()]

                shipment_id = None
                if not _is_empty_cell(raw.get("shipment_id")):
                    shipment_id = _parse_int(raw.get("shipment_id"))
                    if shipment_id <= 0:
                        shipment_id = None

                if _is_empty_cell(raw.get("in_pool")):
                    in_pool = (city_code == "vlg" and status == "accepted" and shipment_id is None)
                else:
                    in_pool = _parse_bool(raw.get("in_pool"))

                new_orders.append({
                    "order_id": order_id,
                    "user_id": user_id,
                    "status": status,
                    "city_name": city_name,
                    "city_code": city_code,
                    "weight_kg": weight_kg,
                    "price_cny": price_cny,
                    "goods_rub": goods_rub,
                    "service_fee_rub": service_fee_rub,
                    "usd_rate": usd_rate,
                    "total_rub": total_rub,
                    "delivery_method": delivery_method,
                    "recipient_name": _parse_text(raw.get("recipient_name"))[:200],
                    "recipient_phone": _parse_text(raw.get("recipient_phone"))[:100],
                    "recipient_address": _parse_text(raw.get("recipient_address"))[:500],
                    "item_desc": _parse_text(raw.get("item_desc"))[:1500],
                    "trackers": trackers,
                    "in_pool": in_pool,
                    "shipment_id": shipment_id,
                    "reject_reason": _parse_text(raw.get("reject_reason"))[:1000] or None,
                    "status_message": _parse_text(raw.get("status_message"))[:1000],
                    "created_at": _parse_text(raw.get("created_at"))[:50],
                    "sent_to_client_at": _parse_text(raw.get("sent_to_client_at"))[:50] or None,
                    "delivered_at": _parse_text(raw.get("delivered_at"))[:50] or None,
                })
            except ValueError as exc:
                errors.append((row_num, str(exc)))

        return {
            "sheet_name": sheet_name,
            "total_rows": total_rows,
            "new_orders": new_orders,
            "new_shipments": new_shipments,
            "skipped_existing": skipped_existing,
            "errors": errors,
        }
    finally:
        wb.close()