import asyncio
import logging
from html import escape

import texts
from config import config
from database import db
from ui import manager_ticket_processed_keyboard, rate_notifications_keyboard

logger = logging.getLogger(__name__)

RATE_META = {
    "cny_low": ("🇨🇳", "Курс юаня (¥, до 5 000 ₽)"),
    "cny_high": ("🇨🇳", "Курс юаня (¥, от 5 000 ₽)"),
    "usd": ("🇺🇸", "Курс доллара ($)"),
}


async def sync_admin_order_notification_buttons(bot, order_id: int, status: str) -> None:
    markup = manager_ticket_processed_keyboard(order_id, status)
    for item in db.get_admin_order_notifications(order_id):
        try:
            await bot.edit_message_reply_markup(
                chat_id=item["chat_id"],
                message_id=item["message_id"],
                reply_markup=markup,
            )
        except Exception as exc:
            logger.info(
                "Не удалось синхронизировать кнопки тикета #%s у админа %s: %s",
                order_id,
                item["admin_id"],
                exc,
            )


async def notify_admin_order_resolution(
    bot,
    order_id: int,
    status: str,
    actor_id: int,
    actor_username: str | None = None,
    reason: str | None = None,
) -> None:
    await sync_admin_order_notification_buttons(bot, order_id, status)
    status_text = "принят" if status == "accepted" else "отклонён"
    actor = f"@{escape(actor_username)}" if actor_username else f"<code>{int(actor_id)}</code>"
    text = (
        f"🔄 <b>Новый тикет #{int(order_id)} {status_text}.</b>\n"
        f"Обработал администратор: {actor}"
    )
    if status == "rejected" and reason:
        text += f"\nПричина: <i>{escape(reason)}</i>"
    for admin_id in config.admin_ids:
        try:
            await bot.send_message(admin_id, text)
        except Exception as exc:
            logger.info("Не удалось отправить обновление тикета #%s админу %s: %s", order_id, admin_id, exc)


async def notify_pool_change(bot, before: dict, after: dict, reason: str = "", exclude_user_ids: set[int] | None = None) -> None:
    old = float(before.get("current", 0.0))
    new = float(after.get("current", 0.0))
    delta = round(new - old, 2)
    if abs(delta) < 0.001:
        return
    direction = "пополнился" if delta > 0 else "уменьшился"
    sign = "+" if delta > 0 else "−"
    text = (
        f"📦 <b>Пул Волгограда {direction}</b>\n\n"
        f"Изменение: <b>{sign}{abs(delta):.2f} кг</b>\n"
        f"Сейчас в пуле: <b>{new:.2f} / {float(after['target']):.2f} кг</b>"
    )
    if reason:
        text += f"\n{reason}"
    excluded = exclude_user_ids or set()
    for user_id in db.pool_notification_recipients():
        if user_id in excluded:
            continue
        try:
            await bot.send_message(user_id, text)
        except Exception as exc:
            logger.info("Не удалось отправить уведомление пула пользователю %s: %s", user_id, exc)


async def notify_rate_change(
    bot,
    rate_key: str,
    old_value: float,
    new_value: float,
    exclude_user_ids: set[int] | None = None,
) -> tuple[int, int]:
    meta = RATE_META.get(rate_key)
    if not meta:
        return 0, 0
    old = round(float(old_value), 4)
    new = round(float(new_value), 4)
    delta = round(new - old, 4)
    if abs(delta) < 0.0001:
        return 0, 0

    flag, title = meta
    if delta > 0:
        trend_icon = "📈"
        direction = "повысился"
        sign = "+"
    else:
        trend_icon = "📉"
        direction = "снизился"
        sign = "−"

    text = (
        f"{trend_icon} <b>{flag} {title} {direction}</b>\n\n"
        f"Было: <b>{texts.format_rate(old)} ₽</b>\n"
        f"Стало: <b>{texts.format_rate(new)} ₽</b> "
        f"(<b>{sign}{texts.format_rate(abs(delta))} ₽</b>)\n\n"
        "<i>Новый курс уже действует в калькуляторе и при оформлении заказов.</i>"
    )
    markup = rate_notifications_keyboard(True, include_home=False)

    excluded = exclude_user_ids or set()
    sent = 0
    failed = 0
    for user_id in db.rate_notification_recipients():
        if user_id in excluded:
            continue
        try:
            await bot.send_message(user_id, text, reply_markup=markup)
            sent += 1
        except Exception as exc:
            failed += 1
            logger.info("Не удалось отправить уведомление о курсе пользователю %s: %s", user_id, exc)
        await asyncio.sleep(0.03)
    return sent, failed
