from aiogram import Router, F, types
from aiogram.filters import CommandStart, CommandObject
from src.database import create_user, get_user, get_user_key
from src.keyboards import main_menu_kb, profile_kb, back_kb, key_format_kb
from config import settings
import datetime
import os
import qrcode
import io

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message, command: CommandObject):
    telegram_id = message.from_user.id
    username = message.from_user.username
    
    referrer_id = None
    args = command.args
    if args and args.isdigit():
        referrer_id = int(args)
        if referrer_id == telegram_id:
            referrer_id = None

    user = await get_user(telegram_id)
    if not user:
        await create_user(telegram_id, username, referrer_id)
        await message.answer(f"Добро пожаловать! Вы были приглашены пользователем {referrer_id}" if referrer_id else "Добро пожаловать!")
    
    await message.answer("Выберите действие:", reply_markup=main_menu_kb())

@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: types.CallbackQuery):
    await callback.message.edit_text("Выберите действие:", reply_markup=main_menu_kb())

@router.callback_query(F.data == "profile")
async def cb_profile(callback: types.CallbackQuery):
    user = await get_user(callback.from_user.id)
    sub_end = user['subscription_end_date']
    
    has_sub = False
    status = "❌ Не активна"
    
    if sub_end:
        end_date = datetime.datetime.fromisoformat(sub_end)
        if end_date > datetime.datetime.now():
            has_sub = True
            status = f"✅ Активна до {end_date.strftime('%d.%m.%Y')}"
    
    text = (
        f"👤 <b>Профиль</b>\n"
        f"ID: {user['telegram_id']}\n"
        f"Подписка: {status}\n"
    )
    
    await callback.message.edit_text(text, reply_markup=profile_kb(has_sub), parse_mode="HTML")

@router.callback_query(F.data == "referrals")
async def cb_referrals(callback: types.CallbackQuery):
    user = await get_user(callback.from_user.id)
    count = user['referral_count']
    needed = settings.REF_REWARD_THRESHOLD
    
    bot_username = (await callback.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={user['telegram_id']}"
    
    text = (
        f"👥 <b>Реферальная программа</b>\n\n"
        f"Приглашайте друзей и получайте бесплатную подписку!\n"
        f"Условия: {needed} друга, купивших подписку = {settings.REF_REWARD_DAYS} дней бесплатно.\n\n"
        f"Ваша ссылка:\n<code>{ref_link}</code>\n\n"
        f"Приглашено активных: {count}/{needed}"
    )
    await callback.message.edit_text(text, reply_markup=back_kb(), parse_mode="HTML")

@router.callback_query(F.data == "get_key")
async def cb_get_key(callback: types.CallbackQuery):
    await callback.message.edit_text("Выберите формат ключа:", reply_markup=key_format_kb())

async def get_valid_key_data(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = await get_user(user_id)
    
    # Double check sub
    if not user['subscription_end_date'] or datetime.datetime.fromisoformat(user['subscription_end_date']) < datetime.datetime.now():
        await callback.answer("Подписка истекла!", show_alert=True)
        return None

    key_data = await get_user_key(user['id'])
    
    if not key_data:
        await callback.answer("Ключ не найден. Обратитесь в поддержку.", show_alert=True)
        return None
        
    return key_data

@router.callback_query(F.data == "key_file")
async def cb_key_file(callback: types.CallbackQuery):
    key_data = await get_valid_key_data(callback)
    if not key_data: return

    config_content = key_data['config']
    file_path = f"vpn_{callback.from_user.id}.conf"
    
    with open(file_path, "w") as f:
        f.write(config_content)
        
    await callback.message.answer_document(
        types.FSInputFile(file_path),
        caption="Ваш файл конфигурации. Откройте его в приложении Amnezia VPN."
    )
    os.remove(file_path)
    await callback.answer()

@router.callback_query(F.data == "key_text")
async def cb_key_text(callback: types.CallbackQuery):
    key_data = await get_valid_key_data(callback)
    if not key_data: return

    config_content = key_data['config']
    await callback.message.answer(f"```\n{config_content}\n```", parse_mode="MarkdownV2")
    await callback.answer()

@router.callback_query(F.data == "key_qr")
async def cb_key_qr(callback: types.CallbackQuery):
    key_data = await get_valid_key_data(callback)
    if not key_data: return

    config_content = key_data['config']
    
    # Generate QR
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(config_content)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save to buffer
    bio = io.BytesIO()
    img.save(bio)
    bio.seek(0)
    
    await callback.message.answer_photo(
        types.BufferedInputFile(bio.getvalue(), filename="qrcode.png"),
        caption="Отсканируйте этот QR-код в приложении Amnezia VPN"
    )
    await callback.answer()

@router.callback_query(F.data == "support")
async def cb_support(callback: types.CallbackQuery):
    await callback.message.edit_text("По всем вопросам пишите: @YOUR_SUPPORT_USERNAME", reply_markup=back_kb())
