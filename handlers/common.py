from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import texts
from config import config
from database import db
from ui import main_menu, pool_notifications_keyboard

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


@router.message(Command("cancel"))
@router.message(F.text == "❌ Отмена")
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=main_menu(config.is_admin(message.from_user.id)))


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    db.ensure_user(message.from_user.id)
    await message.answer(texts.START, reply_markup=main_menu(config.is_admin(message.from_user.id)))


@router.message(F.text.contains("Текущий курс"))
async def show_rates(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(texts.current_rates(db.pool_info(), db.get_rates()))


@router.message(F.text.contains("О сервисе"))
async def about(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(texts.ABOUT)


@router.message(F.text == "📖 Гайд клиента")
async def client_guide(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(texts.CLIENT_GUIDE, reply_markup=main_menu(config.is_admin(message.from_user.id)))


@router.message(F.text.func(lambda value: value and any(phrase in value.lower() for phrase in RYZEN_TRIGGERS)))
async def ryzen(message: Message):
    await message.answer(texts.RYZEN)


@router.message(F.text == "🔔 Пул ВЛГ")
async def pool_notifications(message: Message, state: FSMContext):
    await state.clear()
    enabled = db.pool_notifications_enabled(message.from_user.id)
    pool = db.pool_info()
    status = "включены" if enabled else "отключены"
    text = (
        "🔔 <b>Уведомления о пуле Волгограда</b>\n\n"
        f"Сейчас: <b>{status}</b>.\n"
        f"Пул: <b>{pool['current']:.2f} / {pool['target']:.2f} кг</b>.\n\n"
        "Бот сообщает о пополнении и уменьшении общего пула без данных других клиентов."
    )
    await message.answer(text, reply_markup=pool_notifications_keyboard(enabled))


@router.callback_query(F.data.startswith("pool_notify:"))
async def toggle_pool_notifications(callback: CallbackQuery):
    if callback.data not in {"pool_notify:on", "pool_notify:off"}:
        await callback.answer("Некорректная настройка.", show_alert=True)
        return
    enabled = callback.data == "pool_notify:on"
    db.set_pool_notifications(callback.from_user.id, enabled)
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=pool_notifications_keyboard(enabled))
    await callback.answer("Уведомления пула включены." if enabled else "Уведомления пула отключены.", show_alert=True)
