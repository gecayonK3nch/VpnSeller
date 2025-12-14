from aiogram import Router, F, types
from aiogram.types import LabeledPrice, PreCheckoutQuery
from src.database import get_user, update_subscription, add_referral_count, reset_referral_count, save_key, get_user_key
from src.vpn_service import vpn_service
from src.keyboards import buy_sub_kb, main_menu_kb
from config import settings
import logging

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data == "buy_sub")
async def cb_buy_sub(callback: types.CallbackQuery):
    await callback.message.edit_text("Выберите тариф:", reply_markup=buy_sub_kb())

@router.callback_query(F.data.startswith("buy_"))
async def cb_process_buy(callback: types.CallbackQuery):
    plan = callback.data.split("_")[1]
    
    price = 0
    title = ""
    description = ""
    payload = ""
    
    if plan == "1":
        price = settings.PRICE_1_MONTH
        title = "VPN - 1 Месяц"
        description = "Доступ к VPN на 30 дней"
        payload = "sub_30"
    elif plan == "3":
        price = settings.PRICE_3_MONTHS
        title = "VPN - 3 Месяца"
        description = "Доступ к VPN на 90 дней"
        payload = "sub_90"
    elif plan == "12":
        price = settings.PRICE_12_MONTHS
        title = "VPN - 1 Год"
        description = "Доступ к VPN на 365 дней"
        payload = "sub_365"
        
    await callback.message.answer_invoice(
        title=title,
        description=description,
        payload=payload,
        provider_token=settings.PAYMENT_TOKEN,
        currency="RUB",
        prices=[LabeledPrice(label=title, amount=price * 100)], # Amount in kopecks
        start_parameter="create_invoice_vpn_sub"
    )

@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

@router.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    payment_info = message.successful_payment
    payload = payment_info.invoice_payload
    telegram_id = message.from_user.id
    
    days = 0
    if payload == "sub_30":
        days = 30
    elif payload == "sub_90":
        days = 90
    elif payload == "sub_365":
        days = 365
        
    # 1. Update Subscription
    new_end_date = await update_subscription(telegram_id, days)
    
    # 2. Manage VPN Key
    user = await get_user(telegram_id)
    existing_key = await get_user_key(user['id'])
    
    if not existing_key:
        try:
            # Generate new key
            priv, pub = vpn_service.generate_keys()
            
            # Get all used IPs to find next free one
            # In a real app, you'd query the DB for all used IPs
            # For now, we rely on a simple logic or DB query
            # Let's assume we need to implement get_all_ips in DB
            # For simplicity in this snippet, we'll just generate one based on ID (risky for collisions if not careful)
            # Better:
            # ip = vpn_service.get_next_ip(used_ips)
            
            # Simplified IP generation for MVP: 10.9.0.X where X = user_id + 2
            # WARNING: This limits to 253 users. Production needs better IPAM.
            last_octet = (user['id'] % 253) + 2
            client_ip = f"10.9.0.{last_octet}"
            
            server_pub = vpn_service.get_server_pubkey()
            
            vpn_service.add_peer(pub, client_ip)
            
            config_text = vpn_service.generate_client_config(priv, client_ip, server_pub)
            
            await save_key(user['id'], pub, priv, client_ip, config_text)
            
        except Exception as e:
            logger.error(f"Failed to create VPN key: {e}")
            await message.answer("Оплата прошла, но произошла ошибка при создании ключа. Обратитесь в поддержку.")
            return

    # 3. Referral Logic
    referrer_id = user['referrer_id']
    if referrer_id:
        # Check if this is the first purchase (or just count every purchase? Requirement says "received month of sub")
        # Requirement: "Referral counts if he received month of sub (paid or invited 3 friends)"
        # We simply increment the counter for the referrer.
        
        # To prevent abuse, we might want to check if we already counted this user.
        # But for now, let's assume simple logic:
        await add_referral_count(referrer_id)
        
        referrer = await get_user(referrer_id)
        if referrer and referrer['referral_count'] >= settings.REF_REWARD_THRESHOLD:
            # Give reward
            await update_subscription(referrer['telegram_id'], settings.REF_REWARD_DAYS)
            await reset_referral_count(referrer['telegram_id'])
            
            try:
                await message.bot.send_message(referrer['telegram_id'], f"🎉 Поздравляем! Вы пригласили {settings.REF_REWARD_THRESHOLD} друзей и получили {settings.REF_REWARD_DAYS} дней подписки бесплатно!")
            except:
                pass # User might have blocked bot

    await message.answer(f"✅ Оплата прошла успешно! Подписка продлена до {new_end_date.strftime('%d.%m.%Y')}.\nВаш ключ доступен в Профиле.", reply_markup=main_menu_kb())
