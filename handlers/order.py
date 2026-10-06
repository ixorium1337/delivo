import logging
import re
from html import escape

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import texts
from calculator import PRICE_LIMIT_JOKE, WEIGHT_LIMIT_JOKE, calculate_order
from config import DELIVERY_METHODS, allowed_delivery_methods, config
from database import db
from states import OrderStates
from ui import (
    city_keyboard,
    delivery_keyboard,
    main_menu,
    manager_ticket_keyboard,
    step_menu,
    user_history_keyboard,
    user_ticket_keyboard,
)

router = Router()
logger = logging.getLogger(__name__)


@router.message(OrderStates.waiting_for_price, F.text == "⬅️ Назад")
async def back_to_item(message: Message, state: FSMContext):
    await state.set_state(OrderStates.waiting_for_item)
    await message.answer("Шаг 1: Пришлите <b>ссылку на товар</b> или фото со скриншотом:", reply_markup=step_menu(False))


@router.message(OrderStates.waiting_for_weight, F.text == "⬅️ Назад")
async def back_to_price(message: Message, state: FSMContext):
    await state.set_state(OrderStates.waiting_for_price)
    await message.answer("Шаг 2: Укажите стоимость товара в <b>юанях (¥)</b>:", reply_markup=step_menu())


@router.message(OrderStates.waiting_for_city, F.text == "⬅️ Назад")
async def back_to_weight(message: Message, state: FSMContext):
    await state.set_state(OrderStates.waiting_for_weight)
    await message.answer("Шаг 3: Укажите примерный <b>вес товара в килограммах (кг)</b>:", reply_markup=step_menu())


@router.message(OrderStates.waiting_for_delivery, F.text == "⬅️ Назад")
async def back_to_city(message: Message, state: FSMContext):
    data = await state.get_data()
    weight = float(data.get("weight_kg", 5.0))
    await state.set_state(OrderStates.waiting_for_city)
    await message.answer(texts.calc_city_prompt(weight, step=4), reply_markup=city_keyboard(weight))


@router.message(OrderStates.waiting_for_details, F.text == "⬅️ Назад")
async def back_from_details(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("from_calc"):
        await state.set_state(OrderStates.waiting_for_item)
        await message.answer("Шаг 1: Пришлите <b>ссылку на товар</b> или фото со скриншотом:", reply_markup=step_menu(False))
    else:
        city_code = (data.get("last_calc") or {}).get("city_code", "vlg")
        await state.set_state(OrderStates.waiting_for_delivery)
        await message.answer("Шаг 5: Выберите способ доставки из города прибытия до вас:", reply_markup=delivery_keyboard(city_code))


@router.message(OrderStates.waiting_for_recipient, F.text == "⬅️ Назад")
async def back_to_details(message: Message, state: FSMContext):
    await state.set_state(OrderStates.waiting_for_details)
    await message.answer("Укажите <b>размер, цвет</b> или особые пожелания к товару:", reply_markup=step_menu())


@router.message(OrderStates.waiting_for_address, F.text == "⬅️ Назад")
async def back_to_recipient(message: Message, state: FSMContext):
    await state.set_state(OrderStates.waiting_for_recipient)
    await message.answer("Укажите <b>ФИО</b>:", reply_markup=step_menu())


@router.message(OrderStates.waiting_for_phone, F.text == "⬅️ Назад")
async def back_to_address(message: Message, state: FSMContext):
    await state.set_state(OrderStates.waiting_for_address)
    await message.answer("Укажите <b>адрес доставки</b> (город, улица, дом/ПВЗ — как требуется выбранной службе):", reply_markup=step_menu())


@router.callback_query(F.data == "order_from_calc")
async def start_from_calc(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if "last_calc" not in data:
        await callback.answer("Данные расчёта устарели. Начните заново :)", show_alert=True)
        return
    await state.update_data(from_calc=True)
    await state.set_state(OrderStates.waiting_for_item)
    if callback.message:
        await callback.message.answer(texts.ORDER_FROM_CALC, reply_markup=step_menu(False))
    await callback.answer()


@router.message(F.text == "📦 Оформить заказ")
async def start_direct(message: Message, state: FSMContext):
    await state.clear()
    await state.update_data(from_calc=False)
    await state.set_state(OrderStates.waiting_for_item)
    await message.answer(texts.ORDER_START, reply_markup=step_menu(False))


@router.message(OrderStates.waiting_for_item)
async def process_item(message: Message, state: FSMContext):
    if message.photo:
        photo = message.photo[-1]
        await state.update_data(
            photo_id=photo.file_id,
            photo_unique_id=photo.file_unique_id,
            is_photo=True,
        )
    elif message.text:
        item_link = message.text.strip()
        if not item_link or len(item_link) > 1500:
            await message.answer("Ссылка или описание должны быть длиной до 1500 символов.")
            return
        await state.update_data(item_link=item_link, is_photo=False)
    else:
        await message.answer("Пожалуйста, отправьте ссылку текстом или фото товара:")
        return
    data = await state.get_data()
    if data.get("from_calc"):
        await state.set_state(OrderStates.waiting_for_details)
        await message.answer("Укажите <b>размер, цвет</b> или пожелания к товару:", reply_markup=step_menu())
    else:
        await state.set_state(OrderStates.waiting_for_price)
        await message.answer("Шаг 2: Укажите стоимость товара в <b>юанях (¥)</b>:", reply_markup=step_menu())


@router.message(OrderStates.waiting_for_price)
async def process_price(message: Message, state: FSMContext):
    try:
        price = float((message.text or "").replace(",", ".").strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректное число (цена в ¥):")
        return
    if price > config.max_price_cny:
        await message.answer(PRICE_LIMIT_JOKE)
        return
    await state.update_data(price_cny=price)
    await state.set_state(OrderStates.waiting_for_weight)
    await message.answer("Шаг 3: Укажите примерный <b>вес товара в килограммах (кг)</b>:\n<i>(например: 1.2)</i>", reply_markup=step_menu())


@router.message(OrderStates.waiting_for_weight)
async def process_weight(message: Message, state: FSMContext):
    try:
        weight = float((message.text or "").replace(",", ".").strip())
        if weight <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректный вес (в кг):")
        return
    if weight > config.max_weight_kg:
        await message.answer(WEIGHT_LIMIT_JOKE)
        return
    await state.update_data(weight_kg=weight)
    await state.set_state(OrderStates.waiting_for_city)
    await message.answer(texts.calc_city_prompt(weight, step=4), reply_markup=city_keyboard(weight))


@router.callback_query(OrderStates.waiting_for_city, F.data.startswith("city_"))
async def process_city(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    price_cny = data.get("price_cny")
    weight_kg = data.get("weight_kg")
    if price_cny is None or weight_kg is None:
        await state.clear()
        await callback.answer("Данные заказа устарели. Начните заново.", show_alert=True)
        return
    city_code = "msk" if callback.data == "city_msk" else "vlg"
    if city_code == "msk" and float(weight_kg) < 5.0:
        await callback.answer("⚠️ В Москву отправка только от 5 кг!", show_alert=True)
        return
    await state.update_data(selected_city_code=city_code)
    await state.set_state(OrderStates.waiting_for_delivery)
    if callback.message:
        try:
            await callback.message.edit_text(
                "Шаг 5: Выберите способ доставки <b>из Москвы/Волгограда до вашего адреса</b>.\n\n"
                "⚠️ Эта доставка оплачивается отдельно и не входит в предварительный расчёт.",
                reply_markup=delivery_keyboard(city_code),
            )
        except TelegramBadRequest:
            await callback.message.answer("Шаг 5: Выберите способ доставки до вашего адреса:", reply_markup=delivery_keyboard(city_code))
    await callback.answer()


@router.callback_query(OrderStates.waiting_for_delivery, F.data.startswith("delivery:"))
async def process_delivery(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    city_code = data.get("selected_city_code")
    method_code = (callback.data or "").split(":", 1)[-1]
    if city_code not in {"msk", "vlg"} or method_code not in allowed_delivery_methods(city_code):
        await callback.answer("Этот способ доставки недоступен для выбранного города.", show_alert=True)
        return
    method = DELIVERY_METHODS[method_code]
    result = calculate_order(float(data["price_cny"]), float(data["weight_kg"]), city_code, method)
    await state.update_data(last_calc=result.to_dict())
    await state.set_state(OrderStates.waiting_for_details)
    if callback.message:
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            pass
        await callback.message.answer(texts.order_preview(result))
        await callback.message.answer("Шаг 6: Укажите <b>размер, цвет</b> или особые пожелания к товару:", reply_markup=step_menu())
    await callback.answer()


@router.message(OrderStates.waiting_for_details)
async def process_details(message: Message, state: FSMContext):
    details = (message.text or "Без уточнений").strip() or "Без уточнений"
    if len(details) > 1000:
        await message.answer("Описание слишком длинное. Сократите до 1000 символов.")
        return
    await state.update_data(order_details=details)
    await state.set_state(OrderStates.waiting_for_recipient)
    await message.answer("Укажите <b>ФИО</b>:", reply_markup=step_menu())


@router.message(OrderStates.waiting_for_recipient)
async def process_recipient(message: Message, state: FSMContext):
    recipient = (message.text or "").strip()
    if not recipient or len(recipient) > 200:
        await message.answer("Введите ФИО длиной до 200 символов:")
        return
    await state.update_data(recipient_name=recipient)
    await state.set_state(OrderStates.waiting_for_address)
    await message.answer("Укажите <b>адрес доставки</b> (город, улица, дом/ПВЗ — как требуется выбранной службе):", reply_markup=step_menu())


@router.message(OrderStates.waiting_for_address)
async def process_address(message: Message, state: FSMContext):
    address = (message.text or "").strip()
    if not address or len(address) > 500:
        await message.answer("Введите адрес длиной до 500 символов:")
        return
    await state.update_data(recipient_address=address)
    await state.set_state(OrderStates.waiting_for_phone)
    await message.answer("Финальный шаг: укажите <b>номер телефона получателя</b>:", reply_markup=step_menu())


@router.message(OrderStates.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    phone = (message.text or "").strip()
    digits = re.sub(r"\D", "", phone)
    if not 7 <= len(digits) <= 15 or len(phone) > 100:
        await message.answer("Введите корректный номер телефона (7–15 цифр):")
        return
    data = await state.get_data()
    last_calc = data.get("last_calc") or {}
    required = {"city_name", "city_code", "weight_kg", "price_cny", "goods_rub", "service_fee_rub", "usd_rate", "total_rub", "delivery_method"}
    if not required.issubset(last_calc):
        await state.clear()
        await message.answer("Данные расчёта устарели. Оформите заказ заново.", reply_markup=main_menu(config.is_admin(message.from_user.id)))
        return
    details = data.get("order_details", "Не указано")
    item_desc = details
    if not data.get("is_photo") and data.get("item_link"):
        item_desc = f"{data['item_link'][:180]} ({details})"
    recipient_name = data.get("recipient_name", "")
    recipient_address = data.get("recipient_address", "")
    order_id = db.create_order(
        user_id=message.from_user.id,
        weight_kg=last_calc["weight_kg"],
        city_name=last_calc["city_name"],
        city_code=last_calc["city_code"],
        price_cny=last_calc["price_cny"],
        goods_rub=last_calc["goods_rub"],
        service_fee_rub=last_calc["service_fee_rub"],
        usd_rate=last_calc["usd_rate"],
        total_rub=last_calc["total_rub"],
        item_desc=item_desc,
        recipient_name=recipient_name,
        recipient_address=recipient_address,
        recipient_phone=phone,
        delivery_method=last_calc["delivery_method"],
    )
    if data.get("is_photo") and data.get("photo_id") and data.get("photo_unique_id"):
        try:
            db.add_media(order_id, data["photo_id"], data["photo_unique_id"], "client_item", message.from_user.id)
        except ValueError as exc:
            logger.warning("Не удалось привязать фото клиента к тикету #%s: %s", order_id, exc)

    admin_text = texts.admin_new_order(
        order_id,
        message.from_user.id,
        message.from_user.username,
        details,
        last_calc["city_name"],
        last_calc["weight_kg"],
        last_calc["total_rub"],
        recipient_name,
        recipient_address,
        phone,
        last_calc["delivery_method"],
    )
    markup = manager_ticket_keyboard(order_id)
    for admin_id in config.admin_ids:
        try:
            sent = await message.bot.send_message(admin_id, admin_text, reply_markup=markup)
            db.save_admin_order_notification(order_id, admin_id, sent.chat.id, sent.message_id)
        except Exception as exc:
            logger.warning("Не удалось отправить заказ #%s админу %s: %s", order_id, admin_id, exc)
    await state.clear()
    await message.answer(
        texts.customer_order_created(order_id, last_calc["total_rub"], last_calc["city_name"], last_calc["weight_kg"], last_calc["delivery_method"]),
        reply_markup=main_menu(config.is_admin(message.from_user.id)),
    )


@router.message(F.text.contains("Мои заказы"))
async def show_user_orders(message: Message):
    orders = db.get_user_orders(message.from_user.id)
    if not orders:
        await message.answer("📋 У вас пока нет оформленных заказов в истории.", reply_markup=main_menu(config.is_admin(message.from_user.id)))
        return
    await message.answer(texts.user_orders(orders), reply_markup=user_history_keyboard(orders))


def _user_ticket_text(order: dict) -> str:
    status_map = texts.ORDER_STATUS_LABELS
    shipment = order.get("shipment")
    shipment_text = ""
    if shipment:
        shipment_text = (
            f"\n• Отправление #{shipment['id']}: <b>{escape(shipment['name'])}</b>"
            f"\n• Карго: <code>{escape(shipment['track_number'])}</code>"
            f"\n• Статус отправления: <b>{escape(texts.shipment_status_label(shipment['status']))}</b>"
        )
    update = f"\n• 📣 Обновление: <b>{escape(order['status_message'])}</b>" if order.get("status_message") else ""
    arrival = ""
    if shipment and shipment.get("arrived_at"):
        arrival = f"\n• 📍 Прибыло в {escape(order['city_name'])}: <b>{escape(shipment['arrived_at'])}</b>"
    sent = f"\n• 📤 Отправлен вам: <b>{escape(order['sent_to_client_at'])}</b>" if order.get("sent_to_client_at") else ""
    delivered = f"\n• 📬 Доставлен: <b>{escape(order['delivered_at'])}</b>" if order.get("delivered_at") else ""
    media_count = len(order.get("media", []))
    return (
        f"🎫 <b>Тикет #{order['order_id']}</b>\n\n"
        f"• Статус: <b>{status_map.get(order['status'], 'Неизвестный статус')}</b>\n"
        f"• Город: <b>{escape(order['city_name'])}</b>\n"
        f"• Вес: <b>{order['weight_kg']} кг</b>\n"
        f"• Сумма: <b>{order['total_rub']:.2f} ₽</b>\n"
        f"• Доставка дальше: <b>{escape(order.get('delivery_method') or 'не указана')}</b>\n"
        f"• Фото в тикете: <b>{media_count}</b>"
        f"{shipment_text}{arrival}{sent}{delivered}{update}"
    )


@router.callback_query(F.data.startswith("user_order_view:"))
async def user_order_view(callback: CallbackQuery):
    try:
        order_id = int((callback.data or "").split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Некорректный тикет.", show_alert=True)
        return
    order = db.get_user_order(callback.from_user.id, order_id)
    if not order:
        await callback.answer("Тикет не найден в вашей истории.", show_alert=True)
        return
    if callback.message:
        await callback.message.answer(_user_ticket_text(order), reply_markup=user_ticket_keyboard(order_id))
        for media in order.get("media", []):
            label = "Фото товара от клиента" if media.get("source") == "client_item" else "Фото от менеджера"
            note = (media.get("caption") or "").strip()
            caption = f"📷 <b>{label}</b> · тикет #{order_id}"
            if note:
                caption += f"\n\n💬 {escape(note)}"
            try:
                await callback.message.answer_photo(media["file_id"], caption=caption)
            except Exception as exc:
                logger.warning("Не удалось показать медиа %s тикета #%s: %s", media.get("id"), order_id, exc)
    await callback.answer()


@router.callback_query(F.data == "user_orders_back")
async def user_orders_back(callback: CallbackQuery):
    orders = db.get_user_orders(callback.from_user.id)
    if callback.message:
        await callback.message.answer(
            texts.user_orders(orders) if orders else "📋 У вас пока нет оформленных заказов в истории.",
            reply_markup=user_history_keyboard(orders) if orders else None,
        )
    await callback.answer()
