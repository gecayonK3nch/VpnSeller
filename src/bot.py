import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import settings
from src.database import init_db, get_all_active_keys
from src.handlers import user, admin, payment
from src.scheduler import setup_scheduler
from src.vpn_service import vpn_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # Initialize Bot and Dispatcher
    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()

    # Initialize Database
    await init_db()

    # Restore VPN peers
    try:
        logger.info("Restoring VPN peers...")
        active_keys = await get_all_active_keys()
        vpn_service.restore_peers(active_keys)
    except Exception as e:
        logger.error(f"Failed to restore peers: {e}")

    # Register Routers
    dp.include_router(user.router)
    dp.include_router(admin.router)
    dp.include_router(payment.router)

    # Setup Scheduler
    setup_scheduler(bot)

    # Start Polling
    logger.info("Starting bot...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped!")
