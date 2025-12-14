from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import settings

def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="💳 Купить подписку", callback_data="buy_sub")],
        [InlineKeyboardButton(text="👥 Рефералы", callback_data="referrals")],
        [InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")]
    ])

def buy_sub_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"1 Месяц - {settings.PRICE_1_MONTH}₽", callback_data="buy_1")],
        [InlineKeyboardButton(text=f"3 Месяца - {settings.PRICE_3_MONTHS}₽", callback_data="buy_3")],
        [InlineKeyboardButton(text=f"1 Год - {settings.PRICE_12_MONTHS}₽", callback_data="buy_12")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])

def profile_kb(has_active_sub: bool):
    buttons = []
    if has_active_sub:
        buttons.append([InlineKeyboardButton(text="🔑 Получить ключ", callback_data="get_key")])
        buttons.append([InlineKeyboardButton(text="📖 Инструкция", callback_data="instruction")])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def key_format_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Файлом", callback_data="key_file")],
        [InlineKeyboardButton(text="📝 Текстом", callback_data="key_text")],
        [InlineKeyboardButton(text="📱 QR-кодом", callback_data="key_qr")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="profile")]
    ])

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="➕ Выдать подписку", callback_data="admin_add_sub")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")]
    ])
