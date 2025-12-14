import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import settings
from src.database import init_db
from src.handlers import user, admin, payment
from src.scheduler import setup_scheduler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # Initialize Bot and Dispatcher
    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()

    # Initialize Database
    await init_db()

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
