import io
import logging
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

import texts
from config import config
from database import db
from middleware import AdminFilter
from notifications import notify_admin_order_resolution, notify_pool_change, sync_admin_order_notification_buttons
from states import AdminStates
from ui import (
    accepted_db_keyboard,
    admin_cancel_keyboard,
    admin_keyboard,
    admin_order_card_keyboard,
    admin_order_delete_confirm_keyboard,
    admin_orders_keyboard,
    admin_search_results_keyboard,
    admin_media_keyboard,
    admin_delivered_confirm_keyboard,
    admin_sent_client_confirm_keyboard,
    admin_guide_keyboard,
    admin_guide_back_keyboard,
    admin_rates_keyboard,
    admin_tickets_keyboard,
    admin_users_keyboard,
    main_menu,
    pool_manage_keyboard,
    pool_notifications_keyboard,
    shipment_card_keyboard,
    shipment_delete_confirm_keyboard,
    shipments_keyboard,
    user_ticket_notice_keyboard,
)

router = Router()
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())
logger = logging.getLogger(__name__)


def _callback_id(data: str | None, prefix: str) -> int | None:
    if not data or not data.startswith(prefix):
        return None
    try:
        value = int(data[len(prefix):])
    except ValueError:
        return None
    return value if value > 0 else None


async def _notify(bot, user_id: int, text: str, reply_markup=None) -> bool:
    try:
        await bot.send_message(user_id, text, reply_markup=reply_markup)
        return True
    except Exception as exc:
        logger.info("Не удалось уведомить пользователя %s: %s", user_id, exc)
        return False


def _order_card(order: dict) -> str:
    trackers = ", ".join(order.get("trackers", [])) or "нет"
    reason = f"\n• Причина: <i>{escape(order['reject_reason'])}</i>" if order.get("reject_reason") else ""
    shipment = order.get("shipment")
    shipment_text = "\n• Отправление: <i>не назначено</i>"
    if shipment:
        shipment_text = (
            f"\n• Отправление #{shipment['id']}: <b>{escape(shipment['name'])}</b>"
            f"\n• Карго-номер: <code>{escape(shipment['track_number'])}</code>"
            f"\n• Статус отправления: <b>{escape(texts.shipment_status_label(shipment['status']))}</b>"
            + (f"\n• 📍 Прибыло: <b>{escape(shipment['arrived_at'])}</b>" if shipment.get("arrived_at") else "")
        )
    return (
        f"🧾 <b>Тикет #{order['order_id']}</b>\n\n"
        f"• Telegram ID: <code>{order['user_id']}</code>\n"
        f"• Статус: <b>{escape(texts.order_status_label(order['status']))}</b>\n"
        f"• Город прибытия: <b>{escape(order['city_name'])}</b>\n"
        f"• Последняя миля: <b>{escape(order.get('delivery_method') or 'не указана')}</b>\n"
        f"• Получатель: <b>{escape(order.get('recipient_name') or 'не указан')}</b>\n"
        f"• Телефон: <b>{escape(order.get('recipient_phone') or 'не указан')}</b>\n"
        f"• Адрес: <b>{escape(order.get('recipient_address') or 'не указан')}</b>\n"
        f"• Вес: <b>{order['weight_kg']} кг</b>\n"
        f"• Сумма: <b>{order['total_rub']:.2f} ₽</b>\n"
        f"• Трекеры товара: <code>{escape(trackers)}</code>\n"
        f"• Фото/медиа: <b>{len(order.get('media', []))}</b>\n"
        f"• Детали: {escape(order.get('item_desc') or 'не указаны')}\n"
        f"• Создан: <b>{escape(order['created_at'])}</b>"
        + (f"\n• 📣 Статус для клиента: <b>{escape(order['status_message'])}</b>" if order.get("status_message") else "")
        + (f"\n• 📤 Отправлен клиенту: <b>{escape(order['sent_to_client_at'])}</b>" if order.get("sent_to_client_at") else "")
        + (f"\n• Доставлен: <b>{escape(order['delivered_at'])}</b>" if order.get("delivered_at") else "")
        + f"{shipment_text}{reason}"
    )


@router.message(F.text == "⚙️ Админка")
@router.message(Command("admin"))
async def admin_main(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("⚙️ <b>Панель администратора</b>\n\nВыберите нужный раздел управления:", reply_markup=admin_keyboard())


@router.callback_query(F.data == "admin_back_main")
async def admin_back_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.message:
        await callback.message.edit_text("⚙️ <b>Панель администратора</b>\n\nВыберите нужный раздел управления:", reply_markup=admin_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_guide")
async def admin_guide(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.message:
        await callback.message.edit_text(texts.ADMIN_GUIDE_INDEX, reply_markup=admin_guide_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("admin_guide:"))
async def admin_guide_section(callback: CallbackQuery):
    section = (callback.data or "").split(":", 1)[-1]
    text = texts.ADMIN_GUIDE_SECTIONS.get(section)
    if not text:
        await callback.answer("Раздел гайда не найден.", show_alert=True)
        return
    if callback.message:
        await callback.message.edit_text(text, reply_markup=admin_guide_back_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_cancel")
async def admin_cancel(callback: CallbackQuery, state: FSMContext):
    await admin_back_main(callback, state)


@router.callback_query(F.data == "admin_close")
async def admin_close(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.message:
        await callback.message.delete()
    await callback.answer()


@router.callback_query(F.data == "admin_menu_rates")
async def admin_rates(callback: CallbackQuery):
    rates = db.get_rates()
    text = (
        "📈 <b>Управление курсами валют</b>\n\n"
        f"• CNY (&lt; 5 000 ₽): <b>{rates['cny_low']:.4f} ₽</b>\n"
        f"• CNY (≥ 5 000 ₽): <b>{rates['cny_high']:.4f} ₽</b>\n"
        f"• USD: <b>{rates['usd']:.4f} ₽</b>\n\n"
        "<i>Расчёт выкупа автоматически использует курс CNY до или от 5 000 ₽. Курс посредника в расчёте не участвует.</i>"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=admin_rates_keyboard())
    await callback.answer()


async def _start_rate(callback: CallbackQuery, state: FSMContext, state_value, prompt: str):
    await state.set_state(state_value)
    if callback.message:
        await callback.message.edit_text(prompt, reply_markup=admin_cancel_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_set_broker_cny")
async def set_broker_cny(callback: CallbackQuery, state: FSMContext):
    await _start_rate(callback, state, AdminStates.waiting_for_broker_cny, "Введите текущую цену юаня у посредника:")


@router.callback_query(F.data == "admin_set_cny_low")
async def set_cny_low(callback: CallbackQuery, state: FSMContext):
    await _start_rate(callback, state, AdminStates.waiting_for_cny_low, "Введите CNY для розницы (&lt; 5 000 ₽):")


@router.callback_query(F.data == "admin_set_cny_high")
async def set_cny_high(callback: CallbackQuery, state: FSMContext):
    await _start_rate(callback, state, AdminStates.waiting_for_cny_high, "Введите CNY для опта (≥ 5 000 ₽):")


@router.callback_query(F.data == "admin_set_usd")
async def set_usd(callback: CallbackQuery, state: FSMContext):
    await _start_rate(callback, state, AdminStates.waiting_for_usd, "Введите курс USD:")


async def _save_rate(message: Message, state: FSMContext, key: str, label: str):
    try:
        value = float((message.text or "").replace(",", ".").strip())
        if not 0 < value < 10000:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите положительное число:")
        return
    db.update_rate(key, value)
    await state.clear()
    await message.answer(f"✅ {label} сохранён: <b>{value:.4f} ₽</b>\n<i>Новый курс сразу используется в расчётах.</i>")


@router.message(AdminStates.waiting_for_broker_cny)
async def save_broker_cny(message: Message, state: FSMContext):
    await _save_rate(message, state, "broker_cny", "Курс юаня посредника")


@router.message(AdminStates.waiting_for_cny_low)
async def save_cny_low(message: Message, state: FSMContext):
    await _save_rate(message, state, "cny_low", "CNY (&lt; 5 000 ₽)")


@router.message(AdminStates.waiting_for_cny_high)
async def save_cny_high(message: Message, state: FSMContext):
    await _save_rate(message, state, "cny_high", "CNY (≥ 5 000 ₽)")


@router.message(AdminStates.waiting_for_usd)
async def save_usd(message: Message, state: FSMContext):
    await _save_rate(message, state, "usd", "USD")


@router.callback_query(F.data == "admin_menu_tickets")
async def admin_tickets(callback: CallbackQuery):
    pool = db.pool_info()
    text = (
        "🎫 <b>Управление тикетами</b>\n\n"
        f"• В сборном пуле ВЛГ: <b>{pool['current']:.2f} / {pool['target']:.2f} кг</b> "
        f"({len(pool['order_ids'])} заказов)\n\n"
        "Выберите необходимое действие:"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=admin_tickets_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_menu_users")
async def admin_users(callback: CallbackQuery):
    if callback.message:
        await callback.message.edit_text("👥 <b>Управление доступом клиентов</b>\n\nВыберите действие:", reply_markup=admin_users_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_ticket_search")
async def ticket_search_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_ticket_search)
    if callback.message:
        await callback.message.edit_text(
            "🔎 <b>Поиск тикета</b>\n\n"
            "Введите ID тикета, карго-номер/название отправления, трек товара, телефон, Telegram ID или ФИО получателя.",
            reply_markup=admin_cancel_keyboard(),
        )
    await callback.answer()


@router.message(AdminStates.waiting_for_ticket_search)
async def ticket_search_receive(message: Message, state: FSMContext):
    query = (message.text or "").strip()
    if not query:
        await message.answer("Введите непустой поисковый запрос:", reply_markup=admin_cancel_keyboard())
        return
    orders = db.search_orders(query)
    await state.clear()
    if not orders:
        await message.answer(
            f"🔎 По запросу <b>{escape(query)}</b> ничего не найдено.",
            reply_markup=admin_search_results_keyboard([]),
        )
        return
    await message.answer(
        f"🔎 <b>Результаты поиска</b>\n\nЗапрос: <b>{escape(query)}</b>\nНайдено: <b>{len(orders)}</b>.",
        reply_markup=admin_search_results_keyboard(orders),
    )


@router.callback_query(F.data.startswith("adm_acc:"))
async def accept_order(callback: CallbackQuery):
    order_id = _callback_id(callback.data, "adm_acc:")
    order = db.get_order(order_id) if order_id else None
    if not order:
        await callback.answer("Тикет не найден!", show_alert=True)
        return
    if order["status"] != "pending":
        await sync_admin_order_notification_buttons(callback.bot, order_id, order["status"])
        await callback.answer(f"Статус тикета уже: {texts.order_status_label(order['status'])}", show_alert=True)
        return
    pool_before = db.pool_info() if order["city_code"] == "vlg" else None
    if not db.accept_order(order_id):
        current = db.get_order(order_id)
        if current:
            await sync_admin_order_notification_buttons(callback.bot, order_id, current["status"])
            await callback.answer(f"Тикет уже обработан: {texts.order_status_label(current['status'])}", show_alert=True)
        else:
            await callback.answer("Тикет уже удалён.", show_alert=True)
        return
    await notify_admin_order_resolution(
        callback.bot,
        order_id,
        "accepted",
        callback.from_user.id,
        callback.from_user.username,
    )
    pool_text = ""
    if order["city_code"] == "vlg":
        pool = db.pool_info()
        pool_text = f"\n📦 Заказ добавлен в сборный пул ВЛГ ({pool['current']:.2f} / {pool['target']:.2f} кг)."
        await notify_pool_change(callback.bot, pool_before, pool, "Новый подтверждённый тикет добавлен в сборный груз.", {int(order["user_id"])})
    notify_enabled = db.pool_notifications_enabled(order["user_id"])
    await _notify(
        callback.bot,
        order["user_id"],
        f"🎉 <b>Ваш заказ #{order_id} принят менеджером в работу!</b>\n"
        f"• Сумма: <b>{order['total_rub']:.2f} ₽</b>\n"
        f"• Город: <b>{escape(order['city_name'])}</b>{pool_text}\n\n"
        "🔔 Уведомления о движении пула ВЛГ можно переключить кнопкой ниже.",
        reply_markup=pool_notifications_keyboard(notify_enabled),
    )
    await callback.answer("Заказ принят!")


@router.callback_query(F.data.startswith("adm_processed:"))
async def processed_order(callback: CallbackQuery):
    order_id = _callback_id(callback.data, "adm_processed:")
    order = db.get_order(order_id) if order_id else None
    if not order:
        await callback.answer("Тикет уже удалён.", show_alert=True)
        return
    await callback.answer(f"Тикет уже обработан. Статус: {texts.order_status_label(order['status'])}", show_alert=True)


@router.callback_query(F.data == "adm_cancel_order_start")
async def start_cancel_order(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_cancel_id)
    if callback.message:
        await callback.message.edit_text(
            "🚫 <b>Последовательная отмена тикетов</b>\n\n"
            "Введите ID тикета. После причины отмены режим останется активным — можно сразу отправить ID следующего тикета.",
            reply_markup=admin_cancel_keyboard(),
        )
    await callback.answer()


@router.message(AdminStates.waiting_for_cancel_id)
async def cancel_order_id(message: Message, state: FSMContext):
    try:
        order_id = int((message.text or "").replace("#", "").strip())
    except ValueError:
        await message.answer("Введите корректный номер заказа:")
        return
    order = db.get_order(order_id)
    if not order:
        await message.answer("Заказ не найден.")
        return
    await state.update_data(cancel_order_id=order_id, cancel_order_initial_status=order["status"])
    await state.set_state(AdminStates.waiting_for_cancel_reason)
    await message.answer(f"Укажите причину отмены заказа #{order_id}:")


@router.message(AdminStates.waiting_for_cancel_reason)
async def cancel_order_reason(message: Message, state: FSMContext):
    reason = (message.text or "").strip()
    if not reason or len(reason) > 1000:
        await message.answer("Укажите причину длиной до 1000 символов:")
        return
    data = await state.get_data()
    order_id = data.get("cancel_order_id")
    order = db.get_order(order_id) if order_id else None
    if not order:
        await state.set_state(AdminStates.waiting_for_cancel_id)
        await message.answer("Заказ не найден. Отправьте ID следующего тикета.", reply_markup=admin_cancel_keyboard())
        return
    pool_before = db.pool_info()
    initial_status = data.get("cancel_order_initial_status")
    if initial_status == "pending":
        if not db.reject_pending_order(order_id, reason):
            current = db.get_order(order_id)
            await state.set_state(AdminStates.waiting_for_cancel_id)
            if current:
                await sync_admin_order_notification_buttons(message.bot, order_id, current["status"])
                await message.answer(
                    f"Тикет #{order_id} уже обработан другим администратором. "
                    f"Текущий статус: {escape(texts.order_status_label(current['status']))}. Отмена не применена."
                )
            else:
                await message.answer(f"Тикет #{order_id} уже удалён.")
            return
        await notify_admin_order_resolution(
            message.bot,
            order_id,
            "rejected",
            message.from_user.id,
            message.from_user.username,
            reason,
        )
    else:
        db.reject_order(order_id, reason)
    pool_after = db.pool_info()
    await notify_pool_change(message.bot, pool_before, pool_after, "Тикет исключён из активного пула.")
    await _notify(
        message.bot,
        order["user_id"],
        f"❌ <b>Ваш заказ #{order_id} был отменён менеджером.</b>\n\n"
        f"📝 <b>Причина:</b> {escape(reason)}\n\n"
        "При необходимости вы можете связаться с поддержкой :)",
    )
    await state.set_state(AdminStates.waiting_for_cancel_id)
    await message.answer(
        f"✅ Заказ #{order_id} отменён, исключён из пула/отправления. Клиент оповещён.\n\nОтправьте ID следующего тикета или нажмите «Отмена».",
        reply_markup=admin_cancel_keyboard(),
    )


@router.callback_query(F.data == "adm_restore_order_start")
async def start_restore(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_restore_id)
    if callback.message:
        await callback.message.edit_text(
            "♻️ <b>Последовательное восстановление тикетов</b>\n\n"
            "Введите ID отменённого тикета. После восстановления можно сразу отправить следующий ID.",
            reply_markup=admin_cancel_keyboard(),
        )
    await callback.answer()


@router.message(AdminStates.waiting_for_restore_id)
async def restore_order(message: Message, state: FSMContext):
    try:
        order_id = int((message.text or "").replace("#", "").strip())
    except ValueError:
        await message.answer("Введите числовой ID заказа:")
        return
    order = db.get_order(order_id)
    if not order:
        await message.answer("Заказ не найден.")
        return
    if order["status"] != "rejected":
        await message.answer(
            f"Заказ #{order_id} не отменён (текущий статус: {escape(texts.order_status_label(order['status']))}). Отправьте другой ID.",
            reply_markup=admin_cancel_keyboard(),
        )
        return
    pool_before = db.pool_info()
    db.restore_order(order_id)
    pool_msg = ""
    if order["city_code"] == "vlg":
        pool = db.pool_info()
        pool_msg = f"\n📦 Вес ({order['weight_kg']} кг) возвращён в сборный пул ВЛГ ({pool['current']:.2f} / {pool['target']:.2f} кг)."
        await notify_pool_change(message.bot, pool_before, pool, "Тикет восстановлен и возвращён в сборный груз.")
    await _notify(message.bot, order["user_id"], f"♻️ <b>Ваш заказ #{order_id} восстановлен и возвращён в работу!</b>\nМенеджер возобновил обработку заказа :)")
    await state.set_state(AdminStates.waiting_for_restore_id)
    await message.answer(
        f"✅ Заказ #{order_id} восстановлен. Клиент оповещён.{pool_msg}\n\nОтправьте ID следующего тикета или нажмите «Отмена».",
        reply_markup=admin_cancel_keyboard(),
    )


@router.callback_query(F.data == "admin_accepted_db")
async def accepted_db(callback: CallbackQuery):
    orders = db.get_accepted_orders()
    total_weight = sum(float(order["weight_kg"]) for order in orders)
    total_rub = sum(float(order["total_rub"]) for order in orders)
    text = (
        "📑 <b>Принятые тикеты по карго-номерам</b>\n\n"
        f"• Всего в работе/отправлено: <b>{len(orders)}</b>\n"
        f"• Общий вес: <b>{total_weight:.2f} кг</b>\n"
        f"• Общая сумма: <b>{total_rub:.2f} ₽</b>\n\n"
        "<i>Сначала идут тикеты в отправлениях, отсортированные по карго-номеру; затем тикеты без отправления.</i>\n\n"
    )
    if not orders:
        text += "Принятых тикетов пока нет."
    else:
        for order in orders[:8]:
            tracks = ", ".join(order.get("trackers", [])) or "нет трекера"
            shipment = order.get("shipment")
            cargo = f"{shipment['track_number']} / отправление #{shipment['id']}" if shipment else "без отправления"
            text += (
                f"• <b>#{order['order_id']}</b> | Карго: <code>{escape(cargo)}</code> | "
                f"{escape(order['city_name'])} | {order['weight_kg']} кг | "
                f"Трек: <code>{escape(tracks)}</code>\n"
            )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=accepted_db_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_export_accepted_txt")
async def export_accepted(callback: CallbackQuery):
    orders = db.get_accepted_orders()
    if not orders:
        await callback.answer("База принятых тикетов пуста!", show_alert=True)
        return
    output = io.StringIO()
    output.write("=" * 90 + "\n")
    output.write(f"БАЗА ПРИНЯТЫХ ТИКЕТОВ ПО КАРГО-НОМЕРАМ (Всего: {len(orders)})\n")
    output.write("=" * 90 + "\n\n")
    for order in orders:
        tracks = ", ".join(order.get("trackers", [])) or "Не присвоен"
        shipment = order.get("shipment")
        shipment_text = (
            f"#{shipment['id']} | {shipment['name']} | карго {shipment['track_number']}"
            if shipment else "Не включен"
        )
        output.write(
            f"Тикет #{order['order_id']} | Статус: {texts.order_status_label(order['status'])}\n"
            f"Дата оформления: {order['created_at']}\n"
            f"Telegram ID: {order['user_id']}\n"
            f"Получатель: {order.get('recipient_name') or 'Не указан'}\n"
            f"Телефон: {order.get('recipient_phone') or 'Не указан'}\n"
            f"Адрес: {order.get('recipient_address') or 'Не указан'}\n"
            f"Последняя миля: {order.get('delivery_method') or 'Не указана'}\n"
            f"Город прибытия: {order['city_name']} ({order['city_code']})\n"
            f"Вес: {order['weight_kg']} кг\n"
            f"Товар: {order['price_cny']} CNY ({order['goods_rub']} RUB)\n"
            f"Предварительно: {order['total_rub']} RUB\n"
            f"Трек-номера товара: {tracks}\n"
            f"Отправление: {shipment_text}\n"
            f"Описание/детали: {order.get('item_desc', '')}\n"
            f"{'-' * 90}\n"
        )
    file = BufferedInputFile(output.getvalue().encode("utf-8"), filename="accepted_tickets_by_cargo.txt")
    if callback.message:
        await callback.message.answer_document(file, caption="📑 <b>Реестр тикетов выгружен по карго-номерам.</b>")
    await callback.answer()


@router.callback_query(F.data == "adm_ship_create:vlg")
async def start_vlg_shipment(callback: CallbackQuery, state: FSMContext):
    pool = db.pool_info()
    order_ids = pool["order_ids"]
    if not order_ids:
        await callback.answer("Пул Волгограда пуст!", show_alert=True)
        return
    missing = []
    for order_id in order_ids:
        order = db.get_order(order_id)
        if not order or not order.get("trackers"):
            missing.append(f"#{order_id}")
    if missing:
        if callback.message:
            await callback.message.answer(
                "❌ <b>Невозможно оформить отправление ВЛГ!</b>\n\n"
                f"Следующие тикеты не имеют трек-номеров:\n<b>{', '.join(missing)}</b>\n\n"
                "У каждого тикета должен быть хотя бы один трекер."
            )
        await callback.answer()
        return
    await state.update_data(ship_city="Волгоград", ship_order_ids=order_ids)
    await state.set_state(AdminStates.waiting_for_shipment_name)
    if callback.message:
        await callback.message.edit_text(
            f"Формирование рейса в <b>Волгоград</b> ({len(order_ids)} заказов, {pool['current']} кг).\n\n"
            "Введите название партии (например: <code>Рейс #ВЛГ-10/26</code>):",
            reply_markup=admin_cancel_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == "adm_ship_create:msk")
async def start_msk_shipment(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_msk_ship_order_id)
    if callback.message:
        await callback.message.edit_text("Введите ID заказа для отправки в Москву (например: <code>1005</code>):", reply_markup=admin_cancel_keyboard())
    await callback.answer()


@router.message(AdminStates.waiting_for_msk_ship_order_id)
async def msk_shipment_order(message: Message, state: FSMContext):
    try:
        order_id = int((message.text or "").replace("#", "").strip())
    except ValueError:
        await message.answer("Введите числовой номер заказа:")
        return
    order = db.get_order(order_id)
    if not order:
        await message.answer("Заказ не найден.")
        return
    if order["city_code"] != "msk":
        await message.answer("Этот заказ оформлен не в Москву!")
        return
    if order["status"] != "accepted" or order.get("shipment_id"):
        await message.answer("В отправление можно добавить только принятый тикет, который ещё не находится в другом отправлении.")
        return
    if not order.get("trackers"):
        await state.clear()
        await message.answer(f"❌ Невозможно отправить заказ #{order_id}: у него нет трек-номеров!\nСначала добавьте трекер через меню.")
        return
    await state.update_data(ship_city="Москва", ship_order_ids=[order_id])
    await state.set_state(AdminStates.waiting_for_shipment_name)
    await message.answer(
        f"Оформление отправки заказа #{order_id} в <b>Москву</b>.\n\n"
        f"Введите название отправления (например: <code>МСК-Посылка #{order_id}</code>):",
        reply_markup=admin_cancel_keyboard(),
    )


@router.callback_query(F.data.startswith("adm_ship_msk_single:"))
async def start_msk_shipment_button(callback: CallbackQuery, state: FSMContext):
    order_id = _callback_id(callback.data, "adm_ship_msk_single:")
    order = db.get_order(order_id) if order_id else None
    if not order:
        await callback.answer("Заказ не найден!", show_alert=True)
        return
    if order["city_code"] != "msk":
        await callback.answer("Этот заказ оформлен не в Москву!", show_alert=True)
        return
    if order["status"] != "accepted" or order.get("shipment_id"):
        await callback.answer("Тикет должен быть принят и не находиться в другом отправлении.", show_alert=True)
        return
    if not order.get("trackers"):
        await callback.answer("У заказа нет ни одного трекера! Сначала добавьте трекер.", show_alert=True)
        return
    await state.update_data(ship_city="Москва", ship_order_ids=[order_id])
    await state.set_state(AdminStates.waiting_for_shipment_name)
    if callback.message:
        await callback.message.answer(f"Оформление индивидуального отправления #{order_id} (Москва).\nВведите название партии:", reply_markup=admin_cancel_keyboard())
    await callback.answer()


@router.message(AdminStates.waiting_for_shipment_name)
async def shipment_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if not name or len(name) > 200:
        await message.answer("Введите название длиной до 200 символов:")
        return
    await state.update_data(ship_name=name)
    await state.set_state(AdminStates.waiting_for_shipment_track)
    await message.answer("Укажите общий карго-трек номер отправления (или напишите '-'):")


@router.message(AdminStates.waiting_for_shipment_track)
async def shipment_track(message: Message, state: FSMContext):
    track = (message.text or "").strip()
    if not track:
        await message.answer("Введите трек или '-':")
        return
    if len(track) > 200:
        await message.answer("Трек слишком длинный. Максимум 200 символов.")
        return
    if track == "-":
        track = "Ожидает карго-номер"
    data = await state.get_data()
    city_name = data.get("ship_city")
    order_ids = data.get("ship_order_ids")
    name = data.get("ship_name")
    if not city_name or not order_ids or not name:
        await state.clear()
        await message.answer("Данные отправления устарели. Начните заново.")
        return
    pool_before = db.pool_info()
    try:
        shipment_id = db.create_shipment(city_name, name, order_ids, track)
    except ValueError as exc:
        await state.clear()
        await message.answer(f"❌ {escape(str(exc))}")
        return
    pool_after = db.pool_info()
    await notify_pool_change(message.bot, pool_before, pool_after, "Партия сформирована и выведена из текущего пула.")
    await state.clear()
    await message.answer(
        f"✅ Отправление <b>{escape(name)}</b> (#{shipment_id}) создано со статусом <b>«Формируется»</b>.\n"
        f"В составе: {len(order_ids)} заказ(ов). Клиенты будут автоматически уведомлены при смене статуса отправления."
    )


@router.callback_query(F.data == "adm_edit_weight_start")
async def start_edit_weight(callback: CallbackQuery, state: FSMContext):
    await state.update_data(edit_weight_bulk=True)
    await state.set_state(AdminStates.waiting_for_edit_weight_id)
    if callback.message:
        await callback.message.edit_text(
            "⚖️ <b>Последовательное изменение веса</b>\n\nВведите ID тикета. После нового веса можно сразу отправить ID следующего тикета.",
            reply_markup=admin_cancel_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_edit_w_btn:"))
async def start_edit_weight_button(callback: CallbackQuery, state: FSMContext):
    order_id = _callback_id(callback.data, "adm_edit_w_btn:")
    order = db.get_order(order_id) if order_id else None
    if not order:
        await callback.answer("Заказ не найден.", show_alert=True)
        return
    await state.update_data(edit_order_id=order_id, edit_weight_bulk=False)
    await state.set_state(AdminStates.waiting_for_edit_weight_val)
    if callback.message:
        await callback.message.answer(f"Текущий вес тикета #{order_id}: {order['weight_kg']} кг.\nВведите новый вес (в кг):", reply_markup=admin_cancel_keyboard())
    await callback.answer()


@router.message(AdminStates.waiting_for_edit_weight_id)
async def edit_weight_id(message: Message, state: FSMContext):
    try:
        order_id = int((message.text or "").replace("#", "").strip())
    except ValueError:
        await message.answer("Введите числовой ID заказа:")
        return
    order = db.get_order(order_id)
    if not order:
        await message.answer("Заказ не найден. Попробуйте снова:")
        return
    await state.update_data(edit_order_id=order_id)
    await state.set_state(AdminStates.waiting_for_edit_weight_val)
    await message.answer(f"Текущий вес #{order_id}: {order['weight_kg']} кг.\nВведите новый вес (кг):")


@router.message(AdminStates.waiting_for_edit_weight_val)
async def edit_weight_value(message: Message, state: FSMContext):
    try:
        new_weight = float((message.text or "").replace(",", ".").strip())
        if not 0 < new_weight <= config.max_weight_kg:
            raise ValueError
    except ValueError:
        await message.answer(f"Введите вес от 0 до {config.max_weight_kg:g} кг:")
        return
    data = await state.get_data()
    order_id = data.get("edit_order_id")
    bulk_mode = bool(data.get("edit_weight_bulk"))
    pool_before = db.pool_info()
    result = db.update_weight(order_id, new_weight) if order_id else None
    if not result:
        if bulk_mode:
            await state.set_state(AdminStates.waiting_for_edit_weight_id)
            await message.answer("Ошибка обновления заказа. Отправьте другой ID.", reply_markup=admin_cancel_keyboard())
        else:
            await state.clear()
            await message.answer("Ошибка обновления заказа.")
        return
    _, new_weight, total = result
    order = db.get_order(order_id)
    pool_after = db.pool_info()
    await notify_pool_change(message.bot, pool_before, pool_after, "Вес тикета в активном пуле изменён.")
    await _notify(
        message.bot,
        order["user_id"],
        f"⚖️ <b>Вес вашего заказа #{order_id} был изменён администратором!</b>\n\n"
        f"• Новый вес: <b>{new_weight:.2f} кг</b>\n"
        f"• Новая итоговая стоимость заказа: <b>{total:.2f} ₽</b>",
    )
    if bulk_mode:
        await state.set_state(AdminStates.waiting_for_edit_weight_id)
        await message.answer(
            f"✅ Вес заказа #{order_id} изменён на {new_weight:.2f} кг. Новая сумма: {total:.2f} ₽. Клиент оповещён!\n\nОтправьте ID следующего тикета или нажмите «Отмена».",
            reply_markup=admin_cancel_keyboard(),
        )
    else:
        await state.clear()
        await message.answer(f"✅ Вес заказа #{order_id} изменён на {new_weight:.2f} кг. Новая сумма: {total:.2f} ₽. Клиент оповещён!")


@router.callback_query(F.data == "adm_add_track_start")
async def start_add_track(callback: CallbackQuery, state: FSMContext):
    await state.update_data(track_bulk=True, track_order_id=None)
    await state.set_state(AdminStates.waiting_for_order_track)
    if callback.message:
        await callback.message.edit_text(
            "➕ <b>Последовательное добавление треков</b>\n\n"
            "Введите ID тикета и трек через пробел (например: <code>1001 SF1429938</code>). После добавления можно сразу прислать следующую пару.",
            reply_markup=admin_cancel_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_add_track:"))
async def start_add_track_button(callback: CallbackQuery, state: FSMContext):
    order_id = _callback_id(callback.data, "adm_add_track:")
    if not order_id or not db.get_order(order_id):
        await callback.answer("Заказ не найден.", show_alert=True)
        return
    await state.update_data(track_order_id=order_id, track_bulk=False)
    await state.set_state(AdminStates.waiting_for_order_track)
    if callback.message:
        await callback.message.answer(f"Введите трек-номер для заказа #{order_id}:", reply_markup=admin_cancel_keyboard())
    await callback.answer()


@router.message(AdminStates.waiting_for_order_track)
async def add_track(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("track_order_id")
    bulk_mode = bool(data.get("track_bulk"))
    raw = (message.text or "").strip()
    if not order_id:
        parts = raw.split(maxsplit=1)
        if len(parts) != 2:
            await message.answer("Укажите номер заказа и трек через пробел:")
            return
        try:
            order_id = int(parts[0].replace("#", ""))
        except ValueError:
            await message.answer("Неверный ID заказа.")
            return
        raw = parts[1].strip()
    if not raw or len(raw) > 200:
        await message.answer("Трек должен быть длиной от 1 до 200 символов.")
        return
    order = db.get_order(order_id)
    if not order:
        if bulk_mode:
            await message.answer("Заказ не найден. Отправьте следующую пару ID + трек.", reply_markup=admin_cancel_keyboard())
        else:
            await state.clear()
            await message.answer("Заказ не найден.")
        return
    db.add_tracker(order_id, raw)
    await _notify(message.bot, order["user_id"], f"📍 <b>К заказу #{order_id} добавлен трек-номер:</b> <code>{escape(raw)}</code>")
    if bulk_mode:
        await state.update_data(track_order_id=None)
        await state.set_state(AdminStates.waiting_for_order_track)
        await message.answer(
            f"✅ Трек <code>{escape(raw)}</code> привязан к заказу #{order_id}!\n\nОтправьте следующую пару ID + трек или нажмите «Отмена».",
            reply_markup=admin_cancel_keyboard(),
        )
    else:
        await state.clear()
        await message.answer(f"✅ Трек <code>{escape(raw)}</code> привязан к заказу #{order_id}!")


@router.callback_query(F.data == "adm_rm_track_start")
async def start_remove_track(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_rm_track_id)
    if callback.message:
        await callback.message.edit_text(
            "➖ <b>Последовательное удаление треков</b>\n\nВведите ID тикета, затем трек для удаления. После этого можно сразу отправить ID следующего тикета.",
            reply_markup=admin_cancel_keyboard(),
        )
    await callback.answer()


@router.message(AdminStates.waiting_for_rm_track_id)
async def remove_track_id(message: Message, state: FSMContext):
    try:
        order_id = int((message.text or "").replace("#", "").strip())
    except ValueError:
        await message.answer("Введите число:")
        return
    order = db.get_order(order_id)
    if not order:
        await message.answer("Заказ не найден.")
        return
    tracks = order.get("trackers", [])
    if not tracks:
        await state.set_state(AdminStates.waiting_for_rm_track_id)
        await message.answer("У этого заказа нет трекеров. Отправьте ID следующего тикета.", reply_markup=admin_cancel_keyboard())
        return
    await state.update_data(rm_order_id=order_id)
    await state.set_state(AdminStates.waiting_for_rm_track_val)
    await message.answer(f"Текущие трекеры: {escape(', '.join(tracks))}\nВведите трек для удаления:")


@router.message(AdminStates.waiting_for_rm_track_val)
async def remove_track_value(message: Message, state: FSMContext):
    track = (message.text or "").strip()
    data = await state.get_data()
    order_id = data.get("rm_order_id")
    if order_id and db.remove_tracker(order_id, track):
        await message.answer(f"✅ Трек {escape(track)} удалён из заказа #{order_id}.\n\nОтправьте ID следующего тикета или нажмите «Отмена».", reply_markup=admin_cancel_keyboard())
    else:
        await message.answer("Указанный трек не найден. Отправьте ID следующего тикета или нажмите «Отмена».", reply_markup=admin_cancel_keyboard())
    await state.set_state(AdminStates.waiting_for_rm_track_id)


@router.callback_query(F.data == "admin_orders_manage")
async def orders_manage(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _show_orders_page(callback, 0, "all")


@router.callback_query(F.data.startswith("admin_orders_filter:"))
async def orders_filter(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    status_filter = (callback.data or "").split(":", 1)[-1]
    if status_filter not in {"all", "accepted", "shipped", "delivered", "rejected"}:
        await callback.answer("Неизвестный фильтр.", show_alert=True)
        return
    await _show_orders_page(callback, 0, status_filter)


@router.callback_query(F.data.startswith("admin_orders_page:"))
async def orders_manage_page(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    parts = (callback.data or "").split(":")
    if len(parts) != 3 or parts[1] not in {"all", "accepted", "shipped", "delivered", "rejected"}:
        await callback.answer("Некорректная страница.", show_alert=True)
        return
    try:
        page = max(0, int(parts[2]))
    except ValueError:
        await callback.answer("Некорректная страница.", show_alert=True)
        return
    await _show_orders_page(callback, page, parts[1])


async def _show_orders_page(callback: CallbackQuery, page: int, status_filter: str = "all", answer: bool = True):
    db_status = None if status_filter == "all" else status_filter
    orders = db.list_recent_orders(None, db_status)
    max_page = max(0, (len(orders) - 1) // 10)
    page = min(max(0, page), max_page)
    titles = {
        "all": "Все тикеты",
        "accepted": "Принятые тикеты",
        "shipped": "Тикеты в пути",
        "delivered": "Доставленные клиенту тикеты",
        "rejected": "Отменённые тикеты",
    }
    text = (
        f"🎫 <b>{titles[status_filter]}</b>\n\n"
        "Сортировка: сначала тикеты в отправлениях по карго-номеру, затем тикеты без отправления. "
        f"Всего: <b>{len(orders)}</b>. Страница <b>{page + 1}/{max_page + 1}</b>."
    )
    if not orders:
        text += "\n\nВ этом разделе тикетов нет."
    if callback.message:
        await callback.message.edit_text(text, reply_markup=admin_orders_keyboard(orders, page, status_filter=status_filter))
    if answer:
        await callback.answer()


@router.callback_query(F.data.startswith("adm_order_view:"))
async def order_view(callback: CallbackQuery, state: FSMContext):
    order_id = _callback_id(callback.data, "adm_order_view:")
    order = db.get_order(order_id) if order_id else None
    if not order:
        await callback.answer("Заказ не найден.", show_alert=True)
        return
    await state.update_data(active_order_id=order_id)
    if callback.message:
        await callback.message.answer(
            _order_card(order) + (
                "\n\n<i>Для текстового сообщения клиенту используйте кнопку «Свой статус / Обновить статус клиенту».</i>"
                if order.get("shipment_id") and order.get("status") == "shipped" else ""
            ),
            reply_markup=admin_order_card_keyboard(order_id, order),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_media_add:"))
async def media_add_start(callback: CallbackQuery, state: FSMContext):
    order_id = _callback_id(callback.data, "adm_media_add:")
    order = db.get_order(order_id) if order_id else None
    if not order:
        await callback.answer("Тикет не найден.", show_alert=True)
        return
    if order["status"] not in {"accepted", "shipped"}:
        await callback.answer("Фото можно прикрепить только к принятому или отправленному тикету.", show_alert=True)
        return
    await state.update_data(media_order_id=order_id)
    await state.set_state(AdminStates.waiting_for_ticket_photo)
    if callback.message:
        await callback.message.answer(
            f"📷 Отправьте <b>одно фото</b> для тикета #{order_id} и добавьте к нему пояснение в подписи.\n"
            "Если отправите фото без подписи, бот следующим сообщением попросит поясняющий текст. Клиент получит фото и пояснение.",
            reply_markup=admin_cancel_keyboard(),
        )
    await callback.answer()


@router.message(AdminStates.waiting_for_ticket_photo)
async def media_add_receive(message: Message, state: FSMContext):
    if not message.photo:
        await message.answer("Отправьте именно фотографию. Для выхода нажмите «Отмена».", reply_markup=admin_cancel_keyboard())
        return
    data = await state.get_data()
    order_id = data.get("media_order_id")
    order = db.get_order(order_id) if order_id else None
    if not order or order["status"] not in {"accepted", "shipped"}:
        await state.clear()
        await message.answer("Тикет уже недоступен для добавления фото.")
        return
    photo = message.photo[-1]
    caption = (message.caption or "").strip()
    if caption and len(caption) > 900:
        await message.answer("Пояснение слишком длинное. Используйте до 900 символов и отправьте фото ещё раз.", reply_markup=admin_cancel_keyboard())
        return
    if not caption:
        await state.update_data(media_photo_id=photo.file_id, media_photo_unique_id=photo.file_unique_id)
        await state.set_state(AdminStates.waiting_for_ticket_photo_caption)
        await message.answer(
            f"💬 Теперь пришлите поясняющий текст к фото для тикета #{order_id} (до 900 символов).",
            reply_markup=admin_cancel_keyboard(),
        )
        return
    await _save_manager_media(message, state, order, photo.file_id, photo.file_unique_id, caption)


@router.message(AdminStates.waiting_for_ticket_photo_caption)
async def media_add_caption_receive(message: Message, state: FSMContext):
    caption = (message.text or "").strip()
    if not caption or len(caption) > 900:
        await message.answer("Введите поясняющий текст длиной от 1 до 900 символов.", reply_markup=admin_cancel_keyboard())
        return
    data = await state.get_data()
    order_id = data.get("media_order_id")
    order = db.get_order(order_id) if order_id else None
    file_id = data.get("media_photo_id")
    file_unique_id = data.get("media_photo_unique_id")
    if not order or order["status"] not in {"accepted", "shipped"} or not file_id or not file_unique_id:
        await state.clear()
        await message.answer("Не удалось завершить прикрепление: тикет или фото больше недоступны.")
        return
    await _save_manager_media(message, state, order, file_id, file_unique_id, caption)


async def _save_manager_media(message: Message, state: FSMContext, order: dict, file_id: str, file_unique_id: str, caption: str) -> None:
    order_id = int(order["order_id"])
    try:
        media_id = db.add_media(order_id, file_id, file_unique_id, "warehouse", message.from_user.id, caption)
    except ValueError as exc:
        await state.clear()
        await message.answer(f"Не удалось сохранить фото: {escape(str(exc))}")
        return
    await state.clear()
    delivered = False
    try:
        await message.bot.send_photo(
            order["user_id"],
            file_id,
            caption=f"📷 <b>Новое фото по тикету #{order_id}</b>\n\n💬 {escape(caption)}",
            reply_markup=user_ticket_notice_keyboard(order_id),
        )
        delivered = True
    except Exception as exc:
        logger.info("Не удалось отправить фото пользователю %s: %s", order["user_id"], exc)
    refreshed = db.get_order(order_id)
    result_text = f"✅ Фото #{media_id} и пояснение прикреплены к тикету #{order_id}."
    result_text += " Клиент получил фото." if delivered else " Фото сохранено, но Telegram не доставил его клиенту."
    await message.answer(result_text, reply_markup=admin_order_card_keyboard(order_id, refreshed))


@router.callback_query(F.data.startswith("adm_media_list:"))
async def media_list(callback: CallbackQuery):
    order_id = _callback_id(callback.data, "adm_media_list:")
    order = db.get_order(order_id) if order_id else None
    if not order:
        await callback.answer("Тикет не найден.", show_alert=True)
        return
    media = order.get("media", [])
    if callback.message:
        await callback.message.answer(
            f"🖼 <b>Вложения тикета #{order_id}</b>\n\n"
            f"Всего: <b>{len(media)}</b>. Удаление вложения удаляет его привязку из БД, не затрагивая сам тикет.",
            reply_markup=admin_media_keyboard(order_id, media),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_media_view:"))
async def media_view(callback: CallbackQuery):
    media_id = _callback_id(callback.data, "adm_media_view:")
    media = db.get_media(media_id) if media_id else None
    if not media:
        await callback.answer("Вложение уже удалено.", show_alert=True)
        return
    if callback.message:
        label = "Фото клиента" if media["source"] == "client_item" else "Фото менеджера"
        try:
            await callback.message.answer_photo(
                media["file_id"],
                caption=(
                    f"📷 <b>{label}</b> · тикет #{media['order_id']} · вложение #{media['id']}"
                    + (f"\n\n💬 {escape(media.get('caption') or '')}" if media.get("caption") else "")
                ),
            )
        except Exception as exc:
            logger.warning("Не удалось показать медиа %s: %s", media_id, exc)
            await callback.answer("Telegram не смог открыть это вложение.", show_alert=True)
            return
    await callback.answer()


@router.callback_query(F.data.startswith("adm_media_del:"))
async def media_delete(callback: CallbackQuery):
    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        await callback.answer("Некорректная команда.", show_alert=True)
        return
    try:
        order_id, media_id = int(parts[1]), int(parts[2])
    except ValueError:
        await callback.answer("Некорректная команда.", show_alert=True)
        return
    removed = db.delete_media(media_id, order_id)
    if not removed:
        await callback.answer("Вложение уже удалено или относится к другому тикету.", show_alert=True)
        return
    order = db.get_order(order_id)
    if callback.message and order:
        await callback.message.answer(
            f"🗑 Фото #{media_id} и прикреплённый к нему текст удалены из тикета #{order_id}.",
            reply_markup=admin_media_keyboard(order_id, order.get("media", [])),
        )
    await callback.answer("Фото и текст удалены")


async def _publish_shipment_update(bot, order: dict, text: str) -> bool:
    updated = db.set_shipment_update(order["order_id"], text)
    if not updated:
        return False
    await _notify(
        bot,
        order["user_id"],
        f"📣 <b>Обновление по тикету #{order['order_id']}</b>\n\n"
        f"{escape(text)}\n\nОткройте тикет, чтобы посмотреть актуальный статус.",
        reply_markup=user_ticket_notice_keyboard(order["order_id"]),
    )
    return True


@router.callback_query(F.data.startswith("adm_ship_update_quick:"))
async def shipment_update_quick(callback: CallbackQuery):
    order_id = _callback_id(callback.data, "adm_ship_update_quick:")
    order = db.get_order(order_id) if order_id else None
    if not order or not order.get("shipment_id") or order.get("status") != "shipped":
        await callback.answer("Тикет не находится в активном отправлении.", show_alert=True)
        return
    text = f"Заказ прибыл в {order['city_name']}. Менеджер подтвердил прибытие по отправлению."
    if not await _publish_shipment_update(callback.bot, order, text):
        await callback.answer("Не удалось обновить статус.", show_alert=True)
        return
    await callback.answer("Клиент уведомлён.", show_alert=True)


@router.callback_query(F.data.startswith("adm_ship_update_text:"))
async def shipment_update_text_start(callback: CallbackQuery, state: FSMContext):
    order_id = _callback_id(callback.data, "adm_ship_update_text:")
    order = db.get_order(order_id) if order_id else None
    if not order or not order.get("shipment_id") or order.get("status") != "shipped":
        await callback.answer("Тикет не находится в активном отправлении.", show_alert=True)
        return
    await state.update_data(shipment_update_order_id=order_id)
    await state.set_state(AdminStates.waiting_for_shipment_update)
    if callback.message:
        await callback.message.answer(
            f"✍️ Напишите сообщение для статуса тикета #{order_id} (до 1000 символов).\n"
            "Оно будет сохранено в тикете и отправлено только владельцу этого заказа.",
            reply_markup=admin_cancel_keyboard(),
        )
    await callback.answer()


@router.message(AdminStates.waiting_for_shipment_update)
async def shipment_update_text_receive(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text or len(text) > 1000:
        await message.answer("Введите текст длиной от 1 до 1000 символов.", reply_markup=admin_cancel_keyboard())
        return
    data = await state.get_data()
    order_id = data.get("shipment_update_order_id")
    order = db.get_order(order_id) if order_id else None
    if not order or not order.get("shipment_id") or order.get("status") != "shipped":
        await state.clear()
        await message.answer("Тикет больше не находится в активном отправлении.")
        return
    ok = await _publish_shipment_update(message.bot, order, text)
    await state.clear()
    await message.answer(
        f"✅ Статус тикета #{order_id} обновлён и клиент уведомлён." if ok else "Не удалось обновить тикет.",
        reply_markup=admin_order_card_keyboard(order_id, db.get_order(order_id)) if ok else None,
    )


@router.callback_query(F.data.startswith("adm_sent_client_confirm:"))
async def sent_client_confirm(callback: CallbackQuery):
    order_id = _callback_id(callback.data, "adm_sent_client_confirm:")
    order = db.get_order(order_id) if order_id else None
    shipment = (order or {}).get("shipment") or {}
    if not order or order.get("status") != "shipped" or not shipment.get("arrived_at"):
        await callback.answer("Сначала отправление должно быть отмечено прибывшим.", show_alert=True)
        return
    if order.get("sent_to_client_at"):
        await callback.answer("Отправка клиенту уже отмечена.", show_alert=True)
        return
    if callback.message:
        await callback.message.answer(
            f"📤 <b>Отметить тикет #{order_id} отправленным клиенту?</b>\n\n"
            f"Клиент получит уведомление, что товар прибыл в {escape(order['city_name'])} и передан в {escape(order.get('delivery_method') or 'выбранную службу доставки')}.",
            reply_markup=admin_sent_client_confirm_keyboard(order_id),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_sent_client:"))
async def sent_client(callback: CallbackQuery):
    order_id = _callback_id(callback.data, "adm_sent_client:")
    order = db.mark_sent_to_client(order_id) if order_id else None
    if not order:
        await callback.answer("Не удалось отметить отправку: проверьте прибытие отправления и статус тикета.", show_alert=True)
        return
    await _notify(
        callback.bot,
        order["user_id"],
        f"📤 <b>Тикет #{order_id}: товар прибыл в {escape(order['city_name'])} и отправлен вам.</b>\n\n"
        f"🚚 Служба доставки: <b>{escape(order.get('delivery_method') or 'не указана')}</b>.\n"
        "Следите за дальнейшим движением по данным выбранной службы доставки.",
        reply_markup=user_ticket_notice_keyboard(order_id),
    )
    if callback.message:
        await callback.message.answer(
            f"✅ Тикет #{order_id} отмечен отправленным клиенту. Клиент уведомлён.",
            reply_markup=admin_order_card_keyboard(order_id, order),
        )
    await callback.answer("Отправка клиенту отмечена", show_alert=True)


@router.callback_query(F.data.startswith("adm_delivered_confirm:"))
async def delivered_confirm(callback: CallbackQuery):
    order_id = _callback_id(callback.data, "adm_delivered_confirm:")
    order = db.get_order(order_id) if order_id else None
    if not order or not order.get("shipment_id") or order.get("status") != "shipped" or not order.get("sent_to_client_at"):
        await callback.answer("Сначала отметьте отправку товара клиенту.", show_alert=True)
        return
    if callback.message:
        await callback.message.answer(
            f"⚠️ <b>Отметить тикет #{order_id} доставленным клиенту?</b>\n\n"
            "После подтверждения все фото и медиа-привязки этого тикета будут автоматически удалены из БД.",
            reply_markup=admin_delivered_confirm_keyboard(order_id),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_delivered:"))
async def delivered(callback: CallbackQuery):
    order_id = _callback_id(callback.data, "adm_delivered:")
    result = db.mark_delivered(order_id) if order_id else None
    if not result:
        await callback.answer("Тикет уже завершён или недоступен.", show_alert=True)
        return
    old_order, deleted_media = result
    await _notify(
        callback.bot,
        old_order["user_id"],
        f"📬 <b>Тикет #{order_id}: заказ отмечен доставленным.</b>\n\n"
        "Фотографии заказа очищены после завершения доставки.",
        reply_markup=user_ticket_notice_keyboard(order_id),
    )
    order = db.get_order(order_id)
    if callback.message:
        await callback.message.answer(
            f"✅ Тикет #{order_id} отмечен доставленным. Медиа удалено: {deleted_media}.",
            reply_markup=admin_order_card_keyboard(order_id, order),
        )
    await callback.answer("Заказ завершён", show_alert=True)


@router.callback_query(F.data.startswith("adm_order_delete_confirm:"))
async def order_delete_confirm(callback: CallbackQuery):
    order_id = _callback_id(callback.data, "adm_order_delete_confirm:")
    order = db.get_order(order_id) if order_id else None
    if not order:
        await callback.answer("Заказ уже удалён.", show_alert=True)
        return
    if callback.message:
        await callback.message.edit_text(
            f"⚠️ <b>Удалить заказ #{order_id} навсегда?</b>\n\nОн будет удалён из БД, пула, трекеров и состава отправлений.",
            reply_markup=admin_order_delete_confirm_keyboard(order_id),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_order_delete:"))
async def order_delete(callback: CallbackQuery):
    order_id = _callback_id(callback.data, "adm_order_delete:")
    before = db.pool_info()
    removed = db.delete_order(order_id) if order_id else None
    if not removed:
        await callback.answer("Заказ уже удалён или не найден.", show_alert=True)
        return
    after = db.pool_info()
    await notify_pool_change(callback.bot, before, after, "Тикет удалён из активного пула.")
    await _show_orders_page(callback, 0, "all", answer=False)
    await callback.answer(f"Тикет #{order_id} удалён")


@router.callback_query(F.data == "adm_delete_order_start")
async def start_delete_by_id(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_delete_order_id)
    if callback.message:
        await callback.message.edit_text(
            "⌨️ <b>Удаление тикетов по ID</b>\n\n"
            "Отправляйте ID по одному. После удаления режим останется активным, поэтому можно сразу прислать следующий ID.\n"
            "Для выхода нажмите «Отмена».",
            reply_markup=admin_cancel_keyboard(),
        )
    await callback.answer()


@router.message(AdminStates.waiting_for_delete_order_id)
async def delete_by_id(message: Message, state: FSMContext):
    try:
        order_id = int((message.text or "").replace("#", "").strip())
        if order_id <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите числовой ID. Режим удаления остаётся активным.")
        return
    before = db.pool_info()
    removed = db.delete_order(order_id)
    if removed:
        after = db.pool_info()
        await notify_pool_change(message.bot, before, after, "Тикет удалён из активного пула.")
        await message.answer(
            f"✅ Тикет #{order_id} полностью удалён. Можете сразу отправить ID следующего тикета.",
            reply_markup=admin_cancel_keyboard(),
        )
    else:
        await message.answer("Тикет не найден. Можете отправить другой ID; режим удаления остаётся активным.")


@router.callback_query(F.data == "admin_pool_manage")
async def pool_manage(callback: CallbackQuery):
    pool = db.pool_info()
    if callback.message:
        await callback.message.edit_text(
            "⚖️ <b>Управление сборным пулом (Волгоград):</b>\n\n"
            f"• Накоплено: <b>{pool['current']:.2f} / {pool['target']:.2f} кг</b>\n"
            f"• Заказов в пуле: <b>{len(pool['order_ids'])}</b>",
            reply_markup=pool_manage_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == "admin_pool_reset:vlg")
async def pool_reset(callback: CallbackQuery):
    before = db.pool_info()
    db.reset_pool()
    pool = db.pool_info()
    await notify_pool_change(callback.bot, before, pool, "Пул сброшен менеджером.")
    if callback.message:
        await callback.message.edit_text(
            "⚖️ <b>Управление сборным пулом (Волгоград):</b>\n\n"
            f"• Накоплено: <b>{pool['current']:.2f} / {pool['target']:.2f} кг</b>\n"
            f"• Заказов в пуле: <b>{len(pool['order_ids'])}</b>",
            reply_markup=pool_manage_keyboard(),
        )
    await callback.answer("Пул Волгограда сброшен в 0!", show_alert=True)


@router.callback_query(F.data == "adm_ban_user_start")
async def start_ban(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_ban_id)
    if callback.message:
        await callback.message.edit_text("Введите Telegram ID пользователя для бана:", reply_markup=admin_cancel_keyboard())
    await callback.answer()


@router.message(AdminStates.waiting_for_ban_id)
async def ban_user(message: Message, state: FSMContext):
    try:
        user_id = int((message.text or "").strip())
        if user_id <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите числовой ID.")
        return
    if config.is_admin(user_id):
        await state.clear()
        await message.answer("Администратора нельзя заблокировать через бота.")
        return
    db.ban(user_id)
    await state.clear()
    await message.answer(f"⛔️ Пользователь <code>{user_id}</code> заблокирован.")


@router.callback_query(F.data == "adm_unban_user_start")
async def start_unban(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_unban_id)
    if callback.message:
        await callback.message.edit_text("Введите Telegram ID пользователя для разбана:", reply_markup=admin_cancel_keyboard())
    await callback.answer()


@router.message(AdminStates.waiting_for_unban_id)
async def unban_user(message: Message, state: FSMContext):
    try:
        user_id = int((message.text or "").strip())
        if user_id <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите числовой ID.")
        return
    db.unban(user_id)
    await state.clear()
    await message.answer(f"🟢 Пользователь <code>{user_id}</code> разблокирован.")


@router.callback_query(F.data == "admin_shipments_menu")
async def shipments_menu(callback: CallbackQuery):
    if callback.message:
        await callback.message.edit_text("🚚 <b>Управление отправлениями и рейсами:</b>", reply_markup=shipments_keyboard(db.list_shipments()))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_ship_view:"))
async def shipment_view(callback: CallbackQuery):
    shipment_id = _callback_id(callback.data, "adm_ship_view:")
    shipment = db.get_shipment(shipment_id) if shipment_id else None
    if not shipment:
        await callback.answer("Отправление не найдено!", show_alert=True)
        return
    ticket_lines = []
    shipment_orders = shipment.get("orders", [])
    for order in shipment_orders[:10]:
        trackers = ", ".join(order.get("trackers", [])) or "нет"
        ticket_lines.append(
            f"• <b>Тикет #{order['order_id']}</b> — {escape(order.get('recipient_name') or 'получатель не указан')} | "
            f"{escape(order.get('delivery_method') or 'доставка не указана')} | "
            f"трек: <code>{escape(trackers)}</code>"
        )
    if len(shipment_orders) > 10:
        ticket_lines.append(f"• …ещё {len(shipment_orders) - 10} тикет(ов)")
    tickets = "\n".join(ticket_lines) or "• Нет тикетов"
    if callback.message:
        await callback.message.edit_text(
            f"🚚 <b>Отправление #{shipment['id']}</b>\n\n"
            f"• Рейс: <b>{escape(shipment['name'])}</b>\n"
            f"• Город: <b>{escape(shipment['city_name'])}</b>\n"
            f"• Карго-номер: <code>{escape(shipment['track_number'])}</code>\n"
            f"• Статус: <b>{escape(texts.shipment_status_label(shipment['status']))}</b>\n"
            + (f"• 📍 Прибыло: <b>{escape(shipment['arrived_at'])}</b>\n" if shipment.get("arrived_at") else "")
            + f"\n🎫 <b>Тикеты в составе:</b>\n{tickets}",
            reply_markup=shipment_card_keyboard(shipment, shipment.get("order_ids", [])),
        )
    await callback.answer()


async def _notify_shipment_status(bot, shipment: dict) -> tuple[int, int]:
    status = shipment.get("status")
    cargo = escape(shipment.get("track_number") or shipment.get("name") or f"#{shipment['id']}")
    city = escape(shipment.get("city_name") or "город назначения")
    messages = {
        "forming": f"🧩 <b>Отправление {cargo} формируется.</b>",
        "sent_from_china": f"🚀 <b>Отправление {cargo} отправлено из Китая.</b>",
        "arrived": f"📍 <b>Отправление {cargo} прибыло в {city}.</b>",
        "sorted": f"📦 <b>Отправление {cargo} разобрано в {city}.</b>",
        "closed": f"🔒 <b>Отправление {cargo} закрыто.</b>",
    }
    text = messages.get(status, f"🚚 <b>Статус отправления {cargo}: {escape(texts.shipment_status_label(status))}.</b>")
    recipients: dict[int, int] = {}
    for order in shipment.get("orders", []):
        recipients.setdefault(int(order["user_id"]), int(order["order_id"]))
    sent = failed = 0
    for user_id, order_id in recipients.items():
        ok = await _notify(
            bot,
            user_id,
            text + "\n\nОбновление относится только к отправлению, в котором находится ваш тикет.",
            reply_markup=user_ticket_notice_keyboard(order_id),
        )
        if ok:
            sent += 1
        else:
            failed += 1
    return sent, failed


@router.callback_query(F.data.startswith("adm_ship_status:"))
async def shipment_status_change(callback: CallbackQuery):
    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        await callback.answer("Некорректная команда.", show_alert=True)
        return
    try:
        shipment_id = int(parts[1])
    except ValueError:
        await callback.answer("Некорректный номер отправления.", show_alert=True)
        return
    new_status = parts[2]
    before = db.get_shipment(shipment_id)
    if not before:
        await callback.answer("Отправление не найдено.", show_alert=True)
        return
    if before.get("status") == new_status:
        await callback.answer("Этот статус уже установлен.", show_alert=True)
        return
    try:
        shipment = db.set_shipment_status(shipment_id, new_status)
    except ValueError:
        await callback.answer("Некорректный статус отправления.", show_alert=True)
        return
    sent, failed = await _notify_shipment_status(callback.bot, shipment)
    if callback.message:
        await callback.message.edit_text(
            f"🚚 <b>Отправление #{shipment_id}</b>\n\n"
            f"Статус изменён на <b>«{escape(texts.shipment_status_label(new_status))}»</b>.\n"
            f"Клиентов уведомлено: <b>{sent}</b>; ошибок доставки: <b>{failed}</b>.",
            reply_markup=shipment_card_keyboard(shipment, shipment.get("order_ids", [])),
        )
    await callback.answer("Статус отправления обновлён", show_alert=True)



@router.callback_query(F.data.startswith("adm_ship_del_confirm:"))
async def shipment_delete_confirm(callback: CallbackQuery):
    shipment_id = _callback_id(callback.data, "adm_ship_del_confirm:")
    shipment = db.get_shipment(shipment_id) if shipment_id else None
    if not shipment:
        await callback.answer("Отправление уже удалено или не найдено.", show_alert=True)
        return
    if callback.message:
        await callback.message.edit_text(
            f"⚠️ <b>Удалить отправление #{shipment_id}?</b>\n\n"
            "Тикеты не удалятся: они вернутся в статус «принят», а волгоградские — обратно в пул.",
            reply_markup=shipment_delete_confirm_keyboard(shipment_id),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_ship_del:"))
async def shipment_delete(callback: CallbackQuery):
    shipment_id = _callback_id(callback.data, "adm_ship_del:")
    before = db.pool_info()
    removed = db.delete_shipment(shipment_id) if shipment_id else None
    if not removed:
        await callback.answer("Отправление не найдено!", show_alert=True)
        return
    after = db.pool_info()
    await notify_pool_change(callback.bot, before, after, "Тикеты удалённого отправления возвращены в активный пул.")
    if callback.message:
        await callback.message.edit_text("🚚 <b>Управление отправлениями:</b>", reply_markup=shipments_keyboard(db.list_shipments()))
    await callback.answer(f"Отправление #{shipment_id} удалено. Тикеты сохранены.", show_alert=True)


@router.callback_query(F.data.startswith("adm_rej:"))
async def start_reject(callback: CallbackQuery, state: FSMContext):
    order_id = _callback_id(callback.data, "adm_rej:")
    order = db.get_order(order_id) if order_id else None
    if not order:
        await callback.answer("Заказ не найден.", show_alert=True)
        return
    if order["status"] != "pending":
        await sync_admin_order_notification_buttons(callback.bot, order_id, order["status"])
        await callback.answer(f"Тикет уже обработан: {texts.order_status_label(order['status'])}", show_alert=True)
        return
    await state.update_data(reject_order_id=order_id)
    await state.set_state(AdminStates.waiting_for_reject_reason)
    if callback.message:
        await callback.message.answer(f"Напишите причину отклонения заказа #{order_id}:", reply_markup=admin_cancel_keyboard())
    await callback.answer()


@router.message(AdminStates.waiting_for_reject_reason)
async def reject_reason(message: Message, state: FSMContext):
    reason = (message.text or "").strip()
    if not reason or len(reason) > 1000:
        await message.answer("Укажите причину длиной до 1000 символов:")
        return
    data = await state.get_data()
    order_id = data.get("reject_order_id")
    order = db.get_order(order_id) if order_id else None
    if order and order["status"] == "pending":
        pool_before = db.pool_info()
        if not db.reject_pending_order(order_id, reason):
            current = db.get_order(order_id)
            await state.clear()
            if current:
                await sync_admin_order_notification_buttons(message.bot, order_id, current["status"])
                await message.answer(f"Тикет #{order_id} уже обработан другим администратором. Текущий статус: {escape(texts.order_status_label(current['status']))}.")
            else:
                await message.answer(f"Тикет #{order_id} уже удалён.")
            return
        await notify_admin_order_resolution(
            message.bot,
            order_id,
            "rejected",
            message.from_user.id,
            message.from_user.username,
            reason,
        )
        pool_after = db.pool_info()
        await notify_pool_change(message.bot, pool_before, pool_after, "Тикет исключён из активного пула.")
        await _notify(message.bot, order["user_id"], f"❌ <b>Ваш заказ #{order_id} отклонён менеджером.</b>\nПричина: {escape(reason)}")
    elif order:
        await sync_admin_order_notification_buttons(message.bot, order_id, order["status"])
    await state.clear()
    if not order:
        await message.answer("Заказ не найден.")
    elif order["status"] != "pending":
        await message.answer(f"Тикет #{order_id} уже обработан другим администратором. Текущий статус: {escape(texts.order_status_label(order['status']))}.")
    else:
        await message.answer(f"✅ Заказ #{order_id} отклонён.")
