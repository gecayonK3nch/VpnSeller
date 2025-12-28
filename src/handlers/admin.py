from aiogram import Router, F, types
from aiogram.filters import Command, CommandObject
from src.database import get_all_active_subs, update_subscription, get_user, get_user_key, save_key, disable_subscription, get_all_used_ips, get_all_active_keys
from src.vpn_service import vpn_service
from src.keyboards import admin_kb
from config import settings
import logging

logger = logging.getLogger(__name__)

router = Router()

# Filter for admin
def is_admin(telegram_id: int) -> bool:
    return telegram_id in settings.admin_ids_list

@router.message(Command("sync"))
async def cmd_sync(message: types.Message):
    if not is_admin(message.from_user.id): return
    
    await message.answer("🔄 Начинаю синхронизацию VPN-интерфейса...")
    try:
        active_keys = await get_all_active_keys()
        vpn_service.restore_peers(active_keys)
        await message.answer(f"✅ Синхронизация завершена. Обработано {len(active_keys)} ключей.")
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        await message.answer(f"❌ Ошибка синхронизации: {e}")

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
async def cmd_add_sub(message: types.Message, command: CommandObject):
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
        
        # Check if user has a key, if not generate one
        user_key = await get_user_key(user['id'])
        if not user_key:
            try:
                priv, pub = vpn_service.generate_keys()
                
                # Proper IPAM
                used_ips = await get_all_used_ips()
                client_ip = vpn_service.get_next_ip(used_ips)
                
                server_pub = vpn_service.get_server_pubkey()
                
                vpn_service.add_peer(pub, client_ip)
                
                config_text = vpn_service.generate_client_config(priv, client_ip, server_pub)
                
                await save_key(user['id'], pub, priv, client_ip, config_text)
                await message.answer("✅ Ключ VPN успешно сгенерирован для пользователя.")
            except Exception as e:
                logger.error(f"Failed to create VPN key in admin handler: {e}")
                await message.answer("⚠️ Подписка продлена, но произошла ошибка при создании ключа.")

        await message.answer(f"Подписка продлена до {new_date}")
        
    except ValueError:
        await message.answer("Ошибка в аргументах")

@router.callback_query(F.data == "admin_add_sub")
async def cb_admin_add_sub(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    await callback.message.answer("Для выдачи подписки используйте команду:\n/add_sub <telegram_id> <days>")
    await callback.answer()

@router.callback_query(F.data == "admin_disable_sub")
async def cb_admin_disable_sub(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    await callback.message.answer("Для отключения подписки используйте команду:\n/disable_sub <telegram_id>")
    await callback.answer()

@router.message(Command("disable_sub"))
async def cmd_disable_sub(message: types.Message, command: CommandObject):
    if not is_admin(message.from_user.id): return
    
    args = command.args.split() if command.args else []
    if len(args) != 1:
        await message.answer("Использование: /disable_sub <telegram_id>")
        return
        
    try:
        target_id = int(args[0])
        
        user = await get_user(target_id)
        if not user:
            await message.answer("Пользователь не найден")
            return
            
        await disable_subscription(target_id)
        await message.answer(f"Подписка пользователя {target_id} отключена.")
        
    except ValueError:
        await message.answer("Ошибка в аргументах")
