from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

import texts
from config import config
from database import db
from ui import (
    back_to_menu_keyboard,
    main_menu,
    manager_contact_keyboard,
    pool_notifications_keyboard,
    rate_notifications_keyboard,
)

router = Router()

RYZEN_TRIGGERS = [
    "что мне лучше купить",
    "что лучше купить",
    "что купить",
    "что взять",
    "что посоветуешь",
    "посоветуй что купить",
    "какой процессор купить",
]


def _is_admin(user_id: int | None) -> bool:
    return config.is_admin(user_id)


async def _edit(callback: CallbackQuery, text: str, reply_markup=None) -> None:
    if not callback.message:
        return
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return
        await callback.message.answer(text, reply_markup=reply_markup)


def _rates_view(user_id: int) -> tuple[str, bool]:
    enabled = db.rate_notifications_enabled(user_id)
    status = "включены" if enabled else "отключены"
    text = (
        texts.current_rates(db.pool_info(), db.get_rates())
        + f"\n\n🔔 <b>Уведомления об изменении курса:</b> {status}"
    )
    return text, enabled


@router.message(Command("cancel"))
@router.message(F.text == "❌ Отмена")
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=ReplyKeyboardRemove())
    await message.answer(texts.MAIN_MENU, reply_markup=main_menu(_is_admin(message.from_user.id)))


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    db.ensure_user(message.from_user.id)
    await message.answer(texts.START, reply_markup=ReplyKeyboardRemove())
    await message.answer(texts.MAIN_MENU, reply_markup=main_menu(_is_admin(message.from_user.id)))


@router.message(Command("menu"))
async def menu_command(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(texts.MAIN_MENU, reply_markup=main_menu(_is_admin(message.from_user.id)))


@router.message(StateFilter(None), F.text == "⬅️ Назад")
async def stray_back(message: Message, state: FSMContext):
    """Кнопка «Назад» вне сценария: сбрасываем залипшую reply-клавиатуру."""
    await message.answer("Меню обновлено 👇", reply_markup=ReplyKeyboardRemove())
    await message.answer(texts.MAIN_MENU, reply_markup=main_menu(_is_admin(message.from_user.id)))


@router.callback_query(F.data == "menu:home")
async def menu_home(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _edit(callback, texts.MAIN_MENU, main_menu(_is_admin(callback.from_user.id)))
    await callback.answer()


@router.callback_query(F.data == "menu:rates")
async def rates_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text, enabled = _rates_view(callback.from_user.id)
    await _edit(callback, text, rate_notifications_keyboard(enabled, include_home=True))
    await callback.answer()


@router.message(F.text.contains("Текущий курс"))
@router.message(F.text.contains("Курс ¥"))
async def rates_message(message: Message, state: FSMContext):
    await state.clear()
    text, enabled = _rates_view(message.from_user.id)
    await message.answer(text, reply_markup=rate_notifications_keyboard(enabled, include_home=True))


@router.callback_query(F.data == "menu:help")
async def help_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _edit(callback, texts.HELP, back_to_menu_keyboard())
    await callback.answer()


@router.message(F.text.contains("О сервисе"))
@router.message(F.text.contains("Гайд клиента"))
@router.message(F.text.contains("Справка"))
async def help_message(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(texts.HELP, reply_markup=back_to_menu_keyboard())


@router.callback_query(F.data == "menu:faq")
async def faq_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _edit(callback, texts.FAQ, back_to_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "menu:manager")
async def manager_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _edit(callback, texts.MANAGER, manager_contact_keyboard())
    await callback.answer()


@router.callback_query(F.data == "menu:selection")
async def selection_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _edit(callback, texts.SELECTION, manager_contact_keyboard())
    await callback.answer()


@router.callback_query(F.data == "menu:reviews")
async def reviews_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _edit(callback, texts.REVIEWS_FALLBACK, manager_contact_keyboard())
    await callback.answer()


@router.callback_query(F.data == "menu:channel")
async def channel_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _edit(callback, texts.CHANNEL_FALLBACK, manager_contact_keyboard())
    await callback.answer()


@router.message(F.text.func(lambda value: value and any(phrase in value.lower() for phrase in RYZEN_TRIGGERS)))
async def ryzen(message: Message):
    await message.answer(texts.RYZEN)


def _pool_view(user_id: int) -> tuple[str, bool]:
    enabled = db.pool_notifications_enabled(user_id)
    pool = db.pool_info()
    status = "включены" if enabled else "отключены"
    text = (
        "🔔 <b>Уведомления о пуле Волгограда</b>\n\n"
        f"Сейчас: <b>{status}</b>.\n"
        f"Пул: <b>{pool['current']:.2f} / {pool['target']:.2f} кг</b>.\n\n"
        "Бот сообщает о пополнении и уменьшении общего пула без данных других клиентов."
    )
    return text, enabled


@router.callback_query(F.data == "menu:pool")
async def pool_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text, enabled = _pool_view(callback.from_user.id)
    await _edit(callback, text, pool_notifications_keyboard(enabled))
    await callback.answer()


@router.message(F.text.contains("Пул ВЛГ"))
async def pool_message(message: Message, state: FSMContext):
    await state.clear()
    text, enabled = _pool_view(message.from_user.id)
    await message.answer(text, reply_markup=pool_notifications_keyboard(enabled))


@router.callback_query(F.data.startswith("pool_notify:"))
async def toggle_pool_notifications(callback: CallbackQuery):
    if callback.data not in {"pool_notify:on", "pool_notify:off"}:
        await callback.answer("Некорректная настройка.", show_alert=True)
        return
    enabled = callback.data == "pool_notify:on"
    db.set_pool_notifications(callback.from_user.id, enabled)
    if callback.message:
        try:
            await callback.message.edit_reply_markup(reply_markup=pool_notifications_keyboard(enabled))
        except TelegramBadRequest:
            pass
    await callback.answer("Уведомления пула включены." if enabled else "Уведомления пула отключены.", show_alert=True)


@router.callback_query(F.data.startswith("rate_notify:"))
async def toggle_rate_notifications(callback: CallbackQuery):
    if callback.data not in {"rate_notify:on", "rate_notify:off"}:
        await callback.answer("Некорректная настройка.", show_alert=True)
        return
    enabled = callback.data == "rate_notify:on"
    db.set_rate_notifications(callback.from_user.id, enabled)
    text, enabled = _rates_view(callback.from_user.id)
    await _edit(callback, text, rate_notifications_keyboard(enabled, include_home=True))
    await callback.answer(
        "Уведомления об изменении курса включены." if enabled else "Уведомления об изменении курса отключены.",
        show_alert=True,
    )


@router.callback_query(F.data.startswith("rate_notify_msg:"))
async def toggle_rate_notifications_from_message(callback: CallbackQuery):
    if callback.data not in {"rate_notify_msg:on", "rate_notify_msg:off"}:
        await callback.answer("Некорректная настройка.", show_alert=True)
        return
    enabled = callback.data == "rate_notify_msg:on"
    db.set_rate_notifications(callback.from_user.id, enabled)
    if callback.message:
        try:
            await callback.message.edit_reply_markup(
                reply_markup=rate_notifications_keyboard(enabled, include_home=False)
            )
        except TelegramBadRequest:
            pass
    await callback.answer(
        "Уведомления об изменении курса включены." if enabled else "Уведомления об изменении курса отключены.",
        show_alert=True,
    )
