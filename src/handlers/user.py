from aiogram import Router, F, types
from aiogram.filters import CommandStart, CommandObject
from src.database import create_user, get_user, get_user_key, get_user_keys, count_user_keys, save_key, deactivate_key, get_all_used_ips, delete_key_by_id
from src.keyboards import main_menu_kb, profile_kb, back_kb, devices_kb, device_actions_kb
from src.vpn_service import vpn_service
from config import settings
import datetime
import os
import qrcode
import io
import logging
import re

logger = logging.getLogger(__name__)

def sanitize_filename(name: str) -> str:
    return re.sub(r'[^\w\-]', '_', name)

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

@router.callback_query(F.data == "my_devices")
async def cb_my_devices(callback: types.CallbackQuery):
    user = await get_user(callback.from_user.id)
    keys = await get_user_keys(user['id'])
    
    can_add = len(keys) < user['max_devices']
    
    text = (
        f"📱 <b>Мои устройства</b>\n\n"
        f"Всего устройств: {len(keys)} / {user['max_devices']}\n"
        f"Выберите устройство для управления или добавьте новое."
    )
    
    await callback.message.edit_text(text, reply_markup=devices_kb(keys, can_add), parse_mode="HTML")

@router.callback_query(F.data == "add_device")
async def cb_add_device(callback: types.CallbackQuery):
    user = await get_user(callback.from_user.id)
    current_count = await count_user_keys(user['id'])
    
    if current_count >= user['max_devices']:
        await callback.answer("Достигнут лимит устройств!", show_alert=True)
        return

    try:
        priv, pub = vpn_service.generate_keys()
        
        # Proper IPAM
        used_ips = await get_all_used_ips()
        client_ip = vpn_service.get_next_ip(used_ips)
        
        server_pub = vpn_service.get_server_pubkey()
        
        vpn_service.add_peer(pub, client_ip)
        
        config_text = vpn_service.generate_client_config(priv, client_ip, server_pub)
        
        device_name = f"Device {current_count + 1}"
        await save_key(user['id'], pub, priv, client_ip, config_text, device_name)
        
        await callback.answer("Устройство добавлено!", show_alert=True)
        await cb_my_devices(callback)
        
    except Exception as e:
        logger.error(f"Failed to add device: {e}")
        await callback.answer("Ошибка при добавлении устройства.", show_alert=True)

@router.callback_query(F.data.startswith("device_"))
async def cb_device_actions(callback: types.CallbackQuery):
    device_id = int(callback.data.split("_")[1])
    # Verify ownership? Ideally yes, but ID is unique enough for MVP
    await callback.message.edit_text("Выберите действие с устройством:", reply_markup=device_actions_kb(device_id))

@router.callback_query(F.data.startswith("delete_device_"))
async def cb_delete_device(callback: types.CallbackQuery):
    device_id = int(callback.data.split("_")[2])
    user = await get_user(callback.from_user.id)
    
    try:
        public_key = await delete_key_by_id(device_id, user['id'])
        if public_key:
            vpn_service.remove_peer(public_key)
            await callback.answer("Устройство удалено!", show_alert=True)
            await cb_my_devices(callback)
        else:
            await callback.answer("Ошибка: устройство не найдено или не принадлежит вам.", show_alert=True)
    except Exception as e:
        logger.error(f"Failed to delete device: {e}")
        await callback.answer("Ошибка при удалении устройства.", show_alert=True)

async def get_valid_key_data_by_id(callback: types.CallbackQuery, key_id: int):
    user_id = callback.from_user.id
    user = await get_user(user_id)
    
    if not user['subscription_end_date'] or datetime.datetime.fromisoformat(user['subscription_end_date']) < datetime.datetime.now():
        await callback.answer("Подписка истекла!", show_alert=True)
        return None

    # Get specific key
    keys = await get_user_keys(user['id'])
    target_key = next((k for k in keys if k['id'] == key_id), None)
    
    if not target_key:
        await callback.answer("Ключ не найден.", show_alert=True)
        return None
        
    return target_key

@router.callback_query(F.data.startswith("key_file_"))
async def cb_key_file(callback: types.CallbackQuery):
    key_id = int(callback.data.split("_")[2])
    key_data = await get_valid_key_data_by_id(callback, key_id)
    if not key_data: return

    config_content = key_data['config']
    
    device_name = sanitize_filename(key_data['device_name'])
    file_path = f"NarodnyyVPN_{device_name}.conf"
    
    with open(file_path, "w") as f:
        f.write(config_content)
        
    await callback.message.answer_document(
        types.FSInputFile(file_path),
        caption="Ваш файл конфигурации. Откройте его в приложении AmneziaWG (не Amnezia VPN!)."
    )
    os.remove(file_path)
    await callback.answer()

@router.callback_query(F.data.startswith("key_text_"))
async def cb_key_text(callback: types.CallbackQuery):
    key_id = int(callback.data.split("_")[2])
    key_data = await get_valid_key_data_by_id(callback, key_id)
    if not key_data: return

    config_content = key_data['config']

    await callback.message.answer(f"<code>{config_content}</code>\n\nСкопируйте этот текст в приложение AmneziaWG.", parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("key_qr_"))
async def cb_key_qr(callback: types.CallbackQuery):
    key_id = int(callback.data.split("_")[2])
    key_data = await get_valid_key_data_by_id(callback, key_id)
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
        caption="Отсканируйте этот QR-код в приложении AmneziaWG (не Amnezia VPN!)."
    )
    await callback.answer()

@router.callback_query(F.data.startswith("key_amnezia_app_"))
async def cb_key_amnezia_app(callback: types.CallbackQuery):
    # Format: key_amnezia_app_{id} -> split gives ['key', 'amnezia', 'app', 'id']
    key_id = int(callback.data.split("_")[3])
    key_data = await get_valid_key_data_by_id(callback, key_id)
    if not key_data: return

    config_content = key_data['config']
    
    # Parse config to extract params
    import json
    import base64
    import zlib
    import struct
    
    try:
        # Construct JSON for Amnezia VPN
        # We need to embed the full config text into 'last_config'
        
        logger.info(f"Generating Amnezia VPN config for device: {key_data['device_name']}")
        
        awg_params = {
            "Jc": str(settings.AMNEZIA_JC),
            "Jmin": str(settings.AMNEZIA_JMIN),
            "Jmax": str(settings.AMNEZIA_JMAX),
            "S1": str(settings.AMNEZIA_S1),
            "S2": str(settings.AMNEZIA_S2),
            "H1": str(settings.AMNEZIA_H1),
            "H2": str(settings.AMNEZIA_H2),
            "H3": str(settings.AMNEZIA_H3),
            "H4": str(settings.AMNEZIA_H4)
        }
        
        # Extract DNS
        dns_match = re.search(r"DNS\s*=\s*(.+?)(?:\n|$)", config_content)
        dns_servers = []
        if dns_match:
            dns_str = dns_match.group(1).strip()
            # Handle comma-separated DNS servers
            dns_servers = [d.strip() for d in dns_str.split(',') if d.strip()]
        
        logger.debug(f"Extracted DNS servers: {dns_servers}")

        last_config_obj = {
            "config": config_content,
            "hostName": settings.VPN_HOST,
            "port": str(settings.VPN_PORT),
            "mtu": 1420,
            **awg_params
        }

        if len(dns_servers) > 0:
            last_config_obj["dns1"] = dns_servers[0]
        if len(dns_servers) > 1:
            last_config_obj["dns2"] = dns_servers[1]
        
        # Use device name for description if available
        device_name = key_data['device_name']
        description = f"Narodnyy VPN - {device_name}"
        
        awg_block = {
            "hostName": settings.VPN_HOST,
            "port": str(settings.VPN_PORT),
            "transport_proto": "udp",
            **awg_params,
            "last_config": json.dumps(last_config_obj, separators=(',', ':'))
        }

        amnezia_json = {
            "description": description,
            "hostName": settings.VPN_HOST,
            "defaultContainer": "amnezia-awg",
            "containers": [
                {
                    "container": "amnezia-awg",
                    "awg": awg_block
                }
            ]
        }
        
        json_str = json.dumps(amnezia_json, separators=(',', ':'))
        json_bytes = json_str.encode('utf-8')
        
        logger.debug(f"Amnezia JSON size before compression: {len(json_bytes)} bytes")
        
        # Compress using zlib with Qt qCompress header (4 bytes big-endian length)
        compressed_data = struct.pack('>I', len(json_bytes)) + zlib.compress(json_bytes)
        
        logger.debug(f"Compressed size: {len(compressed_data)} bytes")
        
        # Base64 URL-safe encode (no padding)
        vpn_link = "vpn://" + base64.urlsafe_b64encode(compressed_data).decode('utf-8').rstrip('=')
        
        logger.info(f"Generated VPN link: {vpn_link[:50]}...")
        
        # Generate QR for the link
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(vpn_link)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        bio = io.BytesIO()
        img.save(bio)
        bio.seek(0)
        
        await callback.message.answer_photo(
            types.BufferedInputFile(bio.getvalue(), filename="amnezia_qr.png"),
            caption="Отсканируйте этот QR-код в основном приложении **Amnezia VPN**.\n\n"
                "Если QR-код не сканируется, попробуйте импортировать **текстовый ключ** (кнопка '📝 Текст').\n"
                "Если подключение есть, но нет значка VPN: проверьте Настройки -> VPN на iPhone.",
            parse_mode="Markdown"
        )
        await callback.message.answer(f"<code>{vpn_link}</code>", parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Failed to generate Amnezia VPN config: {e}", exc_info=True)
        await callback.message.answer(f"❌ Ошибка генерации конфига для Amnezia VPN: {e}")
        
    await callback.answer()

@router.callback_query(F.data == "instruction")
async def cb_instruction(callback: types.CallbackQuery):
    text = (
        "📖 <b>Инструкция по подключению</b>\n\n"
        "1. Скачайте приложение <b>AmneziaWG</b> (не Amnezia VPN!):\n"
        "   • <a href='https://apps.apple.com/us/app/amneziawg/id6478942365'>iOS (App Store)</a>\n"
        "   • <a href='https://play.google.com/store/apps/details?id=org.amnezia.awg'>Android (Google Play)</a>\n"
        "   • <a href='https://github.com/amnezia-vpn/amneziawg-windows-client/releases'>Windows</a>\n"
        "   • <a href='https://github.com/amnezia-vpn/amneziawg-macos-client/releases'>macOS</a>\n\n"
        "2. В боте перейдите в <b>Профиль -> Мои устройства</b>.\n"
        "3. Выберите устройство и нажмите <b>'🚀 Amnezia VPN'</b> (для основного приложения) или <b>'📱 QR'</b> / <b>'📄 Файл'</b> (для AmneziaWG).\n"
        "4. Импортируйте настройки в приложение.\n"
        "5. Включите VPN."
    )
    await callback.message.edit_text(text, reply_markup=back_kb(), parse_mode="HTML", disable_web_page_preview=True)

@router.callback_query(F.data == "support")
async def cb_support(callback: types.CallbackQuery):
    await callback.message.edit_text("По всем вопросам пишите: @gec_dev", reply_markup=back_kb())
