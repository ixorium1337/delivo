from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import texts
from calculator import PRICE_LIMIT_JOKE, WEIGHT_LIMIT_JOKE, calculate_order
from config import DELIVERY_METHODS, allowed_delivery_methods, config
from states import CalculatorStates
from ui import city_keyboard, delivery_keyboard, main_menu, order_from_calc_keyboard, step_menu

router = Router()


@router.message(F.text == "🧮 Калькулятор стоимости")
async def start_calculator(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(CalculatorStates.waiting_for_price)
    await message.answer(texts.CALC_START, reply_markup=step_menu(False))


@router.message(CalculatorStates.waiting_for_weight, F.text == "⬅️ Назад")
async def back_to_price(message: Message, state: FSMContext):
    await state.set_state(CalculatorStates.waiting_for_price)
    await message.answer("Шаг 1: Введите стоимость товара в <b>юанях (¥)</b>:", reply_markup=step_menu(False))


@router.message(CalculatorStates.waiting_for_city, F.text == "⬅️ Назад")
async def back_to_weight(message: Message, state: FSMContext):
    await state.set_state(CalculatorStates.waiting_for_weight)
    await message.answer("Шаг 2: Укажите примерный <b>вес товара в килограммах (кг)</b>:", reply_markup=step_menu())


@router.message(CalculatorStates.waiting_for_delivery, F.text == "⬅️ Назад")
async def back_to_city(message: Message, state: FSMContext):
    data = await state.get_data()
    weight = float(data.get("weight_kg", 5.0))
    await state.set_state(CalculatorStates.waiting_for_city)
    await message.answer(texts.calc_city_prompt(weight), reply_markup=city_keyboard(weight))


@router.message(CalculatorStates.waiting_for_price)
async def process_price(message: Message, state: FSMContext):
    try:
        price = float((message.text or "").replace(",", ".").strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректное число (стоимость в ¥):")
        return
    if price > config.max_price_cny:
        await message.answer(PRICE_LIMIT_JOKE)
        return
    await state.update_data(price_cny=price)
    await state.set_state(CalculatorStates.waiting_for_weight)
    await message.answer(texts.CALC_WEIGHT, reply_markup=step_menu())


@router.message(CalculatorStates.waiting_for_weight)
async def process_weight(message: Message, state: FSMContext):
    try:
        weight = float((message.text or "").replace(",", ".").strip())
        if weight <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректный вес в кг (например: <code>1.3</code>):")
        return
    if weight > config.max_weight_kg:
        await message.answer(WEIGHT_LIMIT_JOKE)
        return
    await state.update_data(weight_kg=weight)
    await state.set_state(CalculatorStates.waiting_for_city)
    await message.answer(texts.calc_city_prompt(weight), reply_markup=city_keyboard(weight))


@router.callback_query(CalculatorStates.waiting_for_city, F.data.startswith("city_"))
async def process_city(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    weight_kg = data.get("weight_kg")
    if data.get("price_cny") is None or weight_kg is None:
        await state.clear()
        await callback.answer("Данные расчёта устарели. Начните заново.", show_alert=True)
        return
    city_code = "msk" if callback.data == "city_msk" else "vlg"
    if city_code == "msk" and float(weight_kg) < 5.0:
        await callback.answer("⚠️ В Москву отправка только от 5 кг!", show_alert=True)
        return
    await state.update_data(selected_city_code=city_code)
    await state.set_state(CalculatorStates.waiting_for_delivery)
    if callback.message:
        await callback.message.edit_text(
            "Выберите способ доставки <b>из города прибытия до вас</b>.\n\n"
            "⚠️ Стоимость этой доставки оплачивается отдельно и сейчас не входит в расчёт.",
            reply_markup=delivery_keyboard(city_code),
        )
    await callback.answer()


@router.callback_query(CalculatorStates.waiting_for_delivery, F.data.startswith("delivery:"))
async def process_delivery(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    city_code = data.get("selected_city_code")
    method_code = (callback.data or "").split(":", 1)[-1]
    if city_code not in {"msk", "vlg"} or method_code not in allowed_delivery_methods(city_code):
        await callback.answer("Этот способ доставки недоступен для выбранного города.", show_alert=True)
        return
    result = calculate_order(float(data["price_cny"]), float(data["weight_kg"]), city_code, DELIVERY_METHODS[method_code])
    await state.update_data(last_calc=result.to_dict())
    if callback.message:
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            pass
        await callback.message.answer(texts.calc_result(result), reply_markup=order_from_calc_keyboard())
        await callback.message.answer("Главное меню:", reply_markup=main_menu(config.is_admin(callback.from_user.id)))
    await callback.answer()
