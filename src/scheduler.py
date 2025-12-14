from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.database import get_expired_subs, deactivate_key
from src.vpn_service import vpn_service
import logging

logger = logging.getLogger(__name__)

async def check_expired_subscriptions(bot):
    logger.info("Checking for expired subscriptions...")
    expired_users = await get_expired_subs()
    
    for user in expired_users:
        try:
            public_key = user['public_key']
            telegram_id = user['telegram_id']
            
            # Remove from VPN interface
            vpn_service.remove_peer(public_key)
            
            # Mark as inactive in DB
            await deactivate_key(public_key)
            
            # Notify user
            try:
                await bot.send_message(telegram_id, "Ваша подписка истекла. Доступ к VPN приостановлен. Продлите подписку, чтобы продолжить пользоваться сервисом.")
            except:
                pass
                
            logger.info(f"Deactivated user {telegram_id}")
            
        except Exception as e:
            logger.error(f"Error deactivating user {user['telegram_id']}: {e}")

def setup_scheduler(bot):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_expired_subscriptions, "interval", hours=1, args=[bot])
    scheduler.start()
