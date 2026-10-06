from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="🧮 Калькулятор стоимости"), KeyboardButton(text="📈 Текущий курс")],
        [KeyboardButton(text="📦 Оформить заказ"), KeyboardButton(text="📋 Мои заказы")],
        [KeyboardButton(text="🔔 Пул ВЛГ"), KeyboardButton(text="ℹ️ О сервисе")],
    ]
    if is_admin:
        keyboard.append([KeyboardButton(text="⚙️ Админка")])
    else:
        keyboard.append([KeyboardButton(text="📖 Гайд клиента")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def step_menu(has_back: bool = True) -> ReplyKeyboardMarkup:
    buttons = [[KeyboardButton(text="❌ Отмена")]]
    if has_back:
        buttons = [[KeyboardButton(text="⬅️ Назад"), KeyboardButton(text="❌ Отмена")]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def city_keyboard(weight_kg: float = 5.0) -> InlineKeyboardMarkup:
    buttons = []
    if weight_kg >= 5.0:
        buttons.append(InlineKeyboardButton(text="🏢 Москва ($4/кг, от 5 кг)", callback_data="city_msk"))
    buttons.append(InlineKeyboardButton(text="🏙 Волгоград ($6/кг, сборный)", callback_data="city_vlg"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons])



def delivery_keyboard(city_code: str) -> InlineKeyboardMarkup:
    methods = [
        ("📦 СДЭК", "cdek"),
        ("📦 Boxberry", "boxberry"),
        ("🚚 Энергия", "energy"),
        ("🚚 КИТ", "kit"),
    ]
    if city_code == "vlg":
        methods.extend([("🛍 Авито", "avito"), ("🟣 OZON", "ozon")])
    rows = []
    for i in range(0, len(methods), 2):
        rows.append([InlineKeyboardButton(text=label, callback_data=f"delivery:{code}") for label, code in methods[i:i + 2]])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def order_from_calc_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📦 Оформить этот заказ", callback_data="order_from_calc")
    ]])


def user_history_keyboard(orders: list[dict] | None = None) -> InlineKeyboardMarkup:
    buttons = []
    for order in (orders or [])[:12]:
        media_count = len(order.get("media", []))
        suffix = f" · 📷 {media_count}" if media_count else ""
        buttons.append([InlineKeyboardButton(text=f"🎫 Открыть тикет #{order['order_id']}{suffix}", callback_data=f"user_order_view:{order['order_id']}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def user_ticket_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️ К истории заказов", callback_data="user_orders_back")
    ]])


def user_ticket_notice_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"🎫 Открыть тикет #{order_id}", callback_data=f"user_order_view:{order_id}")
    ]])


def pool_notifications_keyboard(enabled: bool) -> InlineKeyboardMarkup:
    if enabled:
        text = "🔕 Отключить уведомления пула"
        data = "pool_notify:off"
    else:
        text = "🔔 Включить уведомления пула"
        data = "pool_notify:on"
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=data)]])


def manager_ticket_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"adm_acc:{order_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm_rej:{order_id}"),
        ],
        [
            InlineKeyboardButton(text="📍 Добавить трекер", callback_data=f"adm_add_track:{order_id}"),
            InlineKeyboardButton(text="⚖️ Изменить вес", callback_data=f"adm_edit_w_btn:{order_id}"),
        ],
        [InlineKeyboardButton(text="🎫 Открыть тикет", callback_data=f"adm_order_view:{order_id}")],
    ])


def manager_ticket_processed_keyboard(order_id: int, status: str) -> InlineKeyboardMarkup:
    label = {
        "accepted": "🔒 Тикет принят",
        "rejected": "🔒 Тикет отклонён",
    }.get(status, "🔒 Тикет уже обработан")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data=f"adm_processed:{order_id}")],
        [InlineKeyboardButton(text="🎫 Открыть тикет", callback_data=f"adm_order_view:{order_id}")],
    ])


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Курсы валют", callback_data="admin_menu_rates")],
        [InlineKeyboardButton(text="🎫 Управление тикетами", callback_data="admin_menu_tickets")],
        [InlineKeyboardButton(text="🚚 Рейсы и отправления", callback_data="admin_shipments_menu")],
        [InlineKeyboardButton(text="👥 Клиенты (бан/разбан)", callback_data="admin_menu_users")],
        [InlineKeyboardButton(text="📚 Гайд администратора", callback_data="admin_guide")],
        [InlineKeyboardButton(text="❌ Закрыть панель", callback_data="admin_close")],
    ])


def admin_rates_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ CNY (< 5 000 ₽)", callback_data="admin_set_cny_low"),
            InlineKeyboardButton(text="✏️ CNY (≥ 5 000 ₽)", callback_data="admin_set_cny_high"),
        ],
        [InlineKeyboardButton(text="✏️ Курс USD", callback_data="admin_set_usd")],
        [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="admin_back_main")],
    ])


def admin_tickets_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔎 Поиск тикета", callback_data="admin_ticket_search")],
        [
            InlineKeyboardButton(text="🎫 База тикетов", callback_data="admin_orders_manage"),
            InlineKeyboardButton(text="📑 Принятые / карго", callback_data="admin_accepted_db"),
        ],
        [InlineKeyboardButton(text="⚖️ Изменить вес", callback_data="adm_edit_weight_start")],
        [
            InlineKeyboardButton(text="➕ Добавить треки", callback_data="adm_add_track_start"),
            InlineKeyboardButton(text="➖ Убрать треки", callback_data="adm_rm_track_start"),
        ],
        [
            InlineKeyboardButton(text="🚫 Отменить тикеты", callback_data="adm_cancel_order_start"),
            InlineKeyboardButton(text="♻️ Восстановить тикеты", callback_data="adm_restore_order_start"),
        ],
        [InlineKeyboardButton(text="📦 Пул веса ВЛГ", callback_data="admin_pool_manage")],
        [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="admin_back_main")],
    ])


def admin_orders_keyboard(orders: list[dict], page: int = 0, page_size: int = 10, status_filter: str = "all") -> InlineKeyboardMarkup:
    page = max(0, int(page))
    start = page * page_size
    chunk = orders[start:start + page_size]
    buttons = [[
        InlineKeyboardButton(text="📋 Все", callback_data="admin_orders_filter:all"),
        InlineKeyboardButton(text="✅ Принятые", callback_data="admin_orders_filter:accepted"),
    ], [
        InlineKeyboardButton(text="🚚 В пути", callback_data="admin_orders_filter:shipped"),
        InlineKeyboardButton(text="📬 Доставленные", callback_data="admin_orders_filter:delivered"),
    ], [
        InlineKeyboardButton(text="❌ Отменённые", callback_data="admin_orders_filter:rejected"),
    ]]
    for order in chunk:
        status = {"pending": "⏳", "accepted": "✅", "shipped": "🚚", "delivered": "📬", "rejected": "❌"}.get(order["status"], "•")
        buttons.append([
            InlineKeyboardButton(
                text=(f"{status} #{order['order_id']} · "
                      f"{(order.get('shipment') or {}).get('track_number', 'без карго')} · "
                      f"{order['city_name']}"),
                callback_data=f"adm_order_view:{order['order_id']}",
            )
        ])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"admin_orders_page:{status_filter}:{page - 1}"))
    if start + page_size < len(orders):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"admin_orders_page:{status_filter}:{page + 1}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="⌨️ Удалять по ID", callback_data="adm_delete_order_start")])
    buttons.append([InlineKeyboardButton(text="⬅️ К тикетам", callback_data="admin_menu_tickets")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_search_results_keyboard(orders: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    icons = {"pending": "⏳", "accepted": "✅", "shipped": "🚚", "delivered": "📬", "rejected": "❌"}
    for order in orders[:30]:
        shipment = order.get("shipment") or {}
        buttons.append([InlineKeyboardButton(
            text=(f"{icons.get(order.get('status'), '•')} #{order['order_id']} · "
                  f"{shipment.get('track_number', 'без карго')} · "
                  f"{order.get('recipient_name') or 'без ФИО'}"),
            callback_data=f"adm_order_view:{order['order_id']}",
        )])
    buttons.append([InlineKeyboardButton(text="🔎 Новый поиск", callback_data="admin_ticket_search")])
    buttons.append([InlineKeyboardButton(text="⬅️ К тикетам", callback_data="admin_menu_tickets")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_order_card_keyboard(order_id: int, order: dict | None = None) -> InlineKeyboardMarkup:
    order = order or {}
    buttons = []
    if order.get("status") in {"accepted", "shipped"}:
        buttons.append([InlineKeyboardButton(text="📷 Прикрепить фото + пояснение", callback_data=f"adm_media_add:{order_id}")])
    media_count = len(order.get("media", []))
    if media_count:
        buttons.append([InlineKeyboardButton(text=f"🖼 Вложения ({media_count})", callback_data=f"adm_media_list:{order_id}")])
    shipment = order.get("shipment") or {}
    if order.get("shipment_id") and order.get("status") == "shipped":
        if shipment.get("arrived_at"):
            if not order.get("sent_to_client_at"):
                buttons.append([InlineKeyboardButton(text="📤 Отправлен клиенту", callback_data=f"adm_sent_client_confirm:{order_id}")])
            else:
                buttons.append([InlineKeyboardButton(text="✍️ Обновить статус клиенту", callback_data=f"adm_ship_update_text:{order_id}")])
                buttons.append([InlineKeyboardButton(text="✅ Доставлен клиенту", callback_data=f"adm_delivered_confirm:{order_id}")])
        else:
            buttons.append([InlineKeyboardButton(text="✍️ Свой статус", callback_data=f"adm_ship_update_text:{order_id}")])
    buttons.extend([
        [InlineKeyboardButton(text="🗑 Удалить навсегда", callback_data=f"adm_order_delete_confirm:{order_id}")],
        [InlineKeyboardButton(text="⬅️ К списку", callback_data="admin_orders_manage")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_media_keyboard(order_id: int, media: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for item in media:
        label = "Фото клиента" if item.get("source") == "client_item" else "Фото менеджера"
        buttons.append([
            InlineKeyboardButton(text=f"👁 {label} #{item['id']}", callback_data=f"adm_media_view:{item['id']}"),
            InlineKeyboardButton(text="🗑 Фото + текст", callback_data=f"adm_media_del:{order_id}:{item['id']}"),
        ])
    buttons.append([InlineKeyboardButton(text="📷 Добавить фото + пояснение", callback_data=f"adm_media_add:{order_id}")])
    buttons.append([InlineKeyboardButton(text="⬅️ К тикету", callback_data=f"adm_order_view:{order_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_delivered_confirm_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да, доставлен", callback_data=f"adm_delivered:{order_id}"),
        InlineKeyboardButton(text="❌ Нет", callback_data=f"adm_order_view:{order_id}"),
    ]])


def admin_sent_client_confirm_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📤 Да, отправлен клиенту", callback_data=f"adm_sent_client:{order_id}"),
        InlineKeyboardButton(text="❌ Нет", callback_data=f"adm_order_view:{order_id}"),
    ]])


def admin_guide_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧭 Схема работы", callback_data="admin_guide:workflow")],
        [InlineKeyboardButton(text="🎫 Тикеты и статусы", callback_data="admin_guide:tickets")],
        [InlineKeyboardButton(text="🚚 Отправления и статусы", callback_data="admin_guide:shipments")],
        [InlineKeyboardButton(text="📷 Фото и сообщения", callback_data="admin_guide:media")],
        [InlineKeyboardButton(text="🧯 Ошибки и что делать", callback_data="admin_guide:errors")],
        [InlineKeyboardButton(text="⚙️ Остальные функции", callback_data="admin_guide:other")],
        [InlineKeyboardButton(text="⬅️ Назад в админку", callback_data="admin_back_main")],
    ])


def admin_guide_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️ К разделам гайда", callback_data="admin_guide")
    ]])


def admin_order_delete_confirm_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"adm_order_delete:{order_id}"),
            InlineKeyboardButton(text="❌ Нет", callback_data=f"adm_order_view:{order_id}"),
        ]
    ])


def admin_users_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⛔️ Забанить", callback_data="adm_ban_user_start"),
            InlineKeyboardButton(text="🟢 Разбанить", callback_data="adm_unban_user_start"),
        ],
        [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="admin_back_main")],
    ])


def accepted_db_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Скачать базу (.txt)", callback_data="admin_export_accepted_txt")],
        [InlineKeyboardButton(text="⬅️ Назад в админку", callback_data="admin_back_main")],
    ])


def pool_manage_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Сбросить пул ВЛГ в 0", callback_data="admin_pool_reset:vlg")],
        [InlineKeyboardButton(text="⬅️ Назад в админку", callback_data="admin_back_main")],
    ])


def shipments_keyboard(shipments: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for shipment in shipments[:10]:
        buttons.append([
            InlineKeyboardButton(
                text=f"{shipment['track_number']} · {shipment['name']} ({shipment['city_name']})",
                callback_data=f"adm_ship_view:{shipment['id']}",
            )
        ])
    buttons.append([
        InlineKeyboardButton(text="🚀 Сформировать рейс (ВЛГ)", callback_data="adm_ship_create:vlg"),
        InlineKeyboardButton(text="🚀 Отправить заказ (МСК)", callback_data="adm_ship_create:msk"),
    ])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад в админку", callback_data="admin_back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def shipment_card_keyboard(shipment: dict, order_ids: list[int] | None = None) -> InlineKeyboardMarkup:
    shipment_id = int(shipment["id"])
    buttons = []
    status = shipment.get("status") or "forming"
    status_buttons = [
        ("🧩 Формируется", "forming"),
        ("🚀 Отправлено из Китая", "sent_from_china"),
        ("📍 Прибыло", "arrived"),
        ("📦 Разобрано", "sorted"),
        ("🔒 Закрыто", "closed"),
    ]
    for label, code in status_buttons:
        if code != status:
            buttons.append([InlineKeyboardButton(text=label, callback_data=f"adm_ship_status:{shipment_id}:{code}")])
    for order_id in (order_ids or [])[:10]:
        buttons.append([InlineKeyboardButton(text=f"🎫 Открыть тикет #{order_id}", callback_data=f"adm_order_view:{order_id}")])
    buttons.append([InlineKeyboardButton(text="🗑 Удалить отправление", callback_data=f"adm_ship_del_confirm:{shipment_id}")])
    buttons.append([InlineKeyboardButton(text="⬅️ К списку рейсов", callback_data="admin_shipments_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)



def shipment_delete_confirm_keyboard(shipment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"adm_ship_del:{shipment_id}"),
        InlineKeyboardButton(text="❌ Нет", callback_data=f"adm_ship_view:{shipment_id}"),
    ]])


def admin_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Отмена", callback_data="admin_cancel")
    ]])
