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
        buttons.append([InlineKeyboardButton(text="📱 Мои устройства", callback_data="my_devices")])
        buttons.append([InlineKeyboardButton(text="📖 Инструкция", callback_data="instruction")])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def devices_kb(devices: list, can_add: bool):
    buttons = []
    for i, device in enumerate(devices):
        # device is a Row object or dict, assuming it has 'id' and 'device_name'
        name = device['device_name']
        buttons.append([InlineKeyboardButton(text=f"📱 {name}", callback_data=f"device_{device['id']}")])
    
    if can_add:
        buttons.append([InlineKeyboardButton(text="➕ Добавить устройство", callback_data="add_device")])
    else:
        buttons.append([InlineKeyboardButton(text="🔒 Купить слот (+1)", callback_data="buy_slot")])
        
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="profile")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def device_actions_kb(device_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Файл", callback_data=f"key_file_{device_id}")],
        [InlineKeyboardButton(text="📝 Текст", callback_data=f"key_text_{device_id}")],
        [InlineKeyboardButton(text="📱 QR", callback_data=f"key_qr_{device_id}")],
        [InlineKeyboardButton(text="🚀 Amnezia VPN", callback_data=f"key_amnezia_app_{device_id}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_device_{device_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="my_devices")]
    ])

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="➕ Выдать подписку", callback_data="admin_add_sub")],
        [InlineKeyboardButton(text="❌ Отключить подписку", callback_data="admin_disable_sub")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")]
    ])
