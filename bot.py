import asyncio
import logging
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties

# Загружаем переменные окружения
load_dotenv()

# Получаем токен
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("❌ Ошибка: переменная BOT_TOKEN не найдена! Добавьте её в настройках Railway или в файле .env")

router = Router()

# --- МОКОВЫЕ ДАННЫЕ (в будущем заменим на БД) ---
USER_DATA = {
    "balance": "1 250 000 ₽",
    "invested": "1 000 000 ₽",
    "income": "250 000 ₽",
    "reward": "70 000 ₽",
}

DEALS = {
    "1": {"name": "Toyota RAV4", "vin": "*******1234", "invested": "1 000 000 ₽", "income": "250 000 ₽", "status": "В продаже", "days": "12"},
    "2": {"name": "BMW X5", "vin": "*******5678", "invested": "1 500 000 ₽", "income": "0 ₽", "status": "Подготовка", "days": "4"},
    "3": {"name": "Hyundai Solaris", "vin": "*******9012", "invested": "800 000 ₽", "income": "0 ₽", "status": "Задержка", "days": "37"},
}

# --- FSM ДЛЯ ДОБАВЛЕНИЯ РАСХОДА ---
class AddExpense(StatesGroup):
    choosing_type = State()
    entering_amount = State()
    entering_comment = State()
    attaching_photo = State()

# --- КЛАВИАТУРЫ ---

def main_menu_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💰 Мой баланс", callback_data="menu_balance"))
    builder.row(InlineKeyboardButton(text="🚗 Мои сделки", callback_data="menu_deals"))
    builder.row(InlineKeyboardButton(text="📈 История операций", callback_data="menu_history"))
    builder.row(InlineKeyboardButton(text="📊 Отчеты", callback_data="menu_reports"))
    builder.row(InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu_settings"))
    return builder.as_markup()

def back_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu"))
    return builder.as_markup()

def deals_list_kb():
    builder = InlineKeyboardBuilder()
    for deal_id, deal in DEALS.items():
        builder.row(InlineKeyboardButton(text=f"{deal['name']} — {deal['status']}", callback_data=f"deal_{deal_id}"))
    builder.row(InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu"))
    return builder.as_markup()

def deal_detail_kb(deal_id: str):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить расход", callback_data=f"add_expense_{deal_id}"))
    builder.row(InlineKeyboardButton(text="📄 Скачать отчет (PDF)", callback_data="download_pdf"))
    builder.row(InlineKeyboardButton(text="🔙 Назад к сделкам", callback_data="menu_deals"))
    return builder.as_markup()

def expense_types_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔧 Ремонт", callback_data="exp_Ремонт"))
    builder.row(InlineKeyboardButton(text="🧼 Мойка/Детейлинг", callback_data="exp_Мойка"))
    builder.row(InlineKeyboardButton(text="📄 Страховка", callback_data="exp_Страховка"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="main_menu"))
    return builder.as_markup()

# --- ХЭНДЛЕРЫ ---

@router.message(CommandStart())
async def cmd_start(message: Message):
    text = (
        f"Привет, <b>{message.from_user.first_name}</b>! 👋\n"
        "Добро пожаловать в <b>АвтоИнвест</b>!\n\n"
        "Здесь вы можете управлять своими инвестициями, следить за сделками и получать отчеты."
    )
    await message.answer(text, reply_markup=main_menu_kb())

@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery):
    await callback.message.edit_text("Главное меню. Выберите действие:", reply_markup=main_menu_kb())

@router.callback_query(F.data == "menu_balance")
async def show_balance(callback: CallbackQuery):
    text = (
        "💰 <b>Ваш баланс</b>\n\n"
        f"<b>{USER_DATA['balance']}</b>\n\n"
        f"Вложено: {USER_DATA['invested']}\n"
        f"Доход: {USER_DATA['income']}\n\n"
        f"🎁 <b>Ваше вознаграждение</b>\n"
        f"{USER_DATA['reward']} (7% от суммы вложения)"
    )
    await callback.message.edit_text(text, reply_markup=back_kb())

@router.callback_query(F.data == "menu_deals")
async def show_deals(callback: CallbackQuery):
    await callback.message.edit_text(
        "🚗 <b>Мои сделки</b>\n\nВыберите автомобиль для просмотра деталей:",
        reply_markup=deals_list_kb()
    )

@router.callback_query(F.data.startswith("deal_"))
async def show_deal_detail(callback: CallbackQuery):
    deal_id = callback.data.split("_")[1]
    deal = DEALS[deal_id]
    
    text = (
        f"🚘 <b>{deal['name']}</b>\n"
        f"VIN: {deal['vin']}\n\n"
        f"<b>Финансовые показатели:</b>\n"
        f"Цена покупки: {deal['invested']}\n"
        f"Расходы: 120 000 ₽\n"
        f"Цена продажи: 1 450 000 ₽\n"
        f"Прибыль: {deal['income']}\n\n"
        f"<b>Вознаграждение инвестора:</b>\n"
        f"7% (первый месяц): 70 000 ₽\n"
        f"Общее за цикл: 100 000 ₽"
    )
    await callback.message.edit_text(text, reply_markup=deal_detail_kb(deal_id))

# --- ЛОГИКА ДОБАВЛЕНИЯ РАСХОДА (FSM) ---

@router.callback_query(F.data.startswith("add_expense_"))
async def start_add_expense(callback: CallbackQuery, state: FSMContext):
    deal_id = callback.data.split("_")[2]
    await state.update_data(deal_id=deal_id)
    await callback.message.edit_text(
        f"Добавление расхода для <b>{DEALS[deal_id]['name']}</b>.\n\nВыберите тип расхода:",
        reply_markup=expense_types_kb()
    )
    await state.set_state(AddExpense.choosing_type)

@router.callback_query(AddExpense.choosing_type, F.data.startswith("exp_"))
async def process_expense_type(callback: CallbackQuery, state: FSMContext):
    expense_type = callback.data.replace("exp_", "")
    await state.update_data(exp_type=expense_type)
    await callback.message.edit_text("Введите сумму расхода (в рублях, только цифры):")
    await state.set_state(AddExpense.entering_amount)

@router.message(AddExpense.entering_amount)
async def process_amount(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введите сумму цифрами (например: 25000).")
        return
    await state.update_data(amount=message.text)
    await message.answer("Введите комментарий (например: Замена масла и фильтров):")
    await state.set_state(AddExpense.entering_comment)

@router.message(AddExpense.entering_comment)
async def process_comment(message: Message, state: FSMContext):
    await state.update_data(comment=message.text)
    await message.answer("Прикрепите фото чека (или отправьте любой текст, чтобы пропустить):")
    await state.set_state(AddExpense.attaching_photo)

@router.message(AddExpense.attaching_photo)
async def process_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    
    text = (
        "✅ <b>Расход успешно добавлен!</b>\n\n"
        f"Автомобиль: {DEALS[data['deal_id']]['name']}\n"
        f"Тип: {data['exp_type']}\n"
        f"Сумма: {data['amount']} ₽\n"
        f"Комментарий: {data['comment']}\n"
    )
    if message.photo:
        text += "Фото: <i>Прикреплено</i>"
    else:
        text += "Фото: <i>Нет</i>"
        
    await message.answer(text, reply_markup=back_kb())
    await state.clear()

# --- ЗАПУСК БОТА ---

async def main():
    logging.basicConfig(level=logging.INFO)
    
    # Инициализация бота с новым синтаксисом aiogram 3.7+
    bot = Bot(
        token=BOT_TOKEN, 
        default=DefaultBotProperties(parse_mode="HTML")
    )
    
    dp = Dispatcher()
    dp.include_router(router)
    
    # Удаляем вебхуки (важно для Railway, чтобы не было конфликтов)
    await bot.delete_webhook(drop_pending_updates=True)
    
    print("🚀 Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен")
