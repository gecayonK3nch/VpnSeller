from aiogram import Router, F, types
from aiogram.filters import Command
from src.database import get_all_active_subs, update_subscription, get_user
from src.keyboards import admin_kb
from config import settings

router = Router()

# Filter for admin
def is_admin(telegram_id: int) -> bool:
    return telegram_id in settings.ADMIN_IDS

@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("Админ-панель:", reply_markup=admin_kb())

@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    
    active_subs = await get_all_active_subs()
    count = len(active_subs)
    
    await callback.message.edit_text(f"📊 Статистика:\nАктивных подписок: {count}", reply_markup=admin_kb())

# Simple add sub command: /add_sub <user_id> <days>
@router.message(Command("add_sub"))
async def cmd_add_sub(message: types.Message, command: types.CommandObject):
    if not is_admin(message.from_user.id): return
    
    args = command.args.split() if command.args else []
    if len(args) != 2:
        await message.answer("Использование: /add_sub <telegram_id> <days>")
        return
        
    try:
        target_id = int(args[0])
        days = int(args[1])
        
        user = await get_user(target_id)
        if not user:
            await message.answer("Пользователь не найден")
            return
            
        new_date = await update_subscription(target_id, days)
        await message.answer(f"Подписка продлена до {new_date}")
        
    except ValueError:
        await message.answer("Ошибка в аргументах")
