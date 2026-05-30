import asyncio
import logging
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

# Allow `python endpoints/telegram_bot.py` (sys.path[0] is endpoints/, not project root).
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from telegram import Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes

from properties_loader import load_private_properties
from services import first_aid_kits as first_aid_kits_service
from services import users as users_service

logger = logging.getLogger(__name__)

_START_HELP = (
    "FirstAidKitBot\n\n"
    "Commands:\n"
    "/create_first_aid_kit <title> — create a first aid kit linked to you\n"
    "/my_first_aid_kits — list your first aid kits"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(_START_HELP)


async def create_first_aid_kit_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if update.message is None:
        return
    tg_user = update.effective_user
    if tg_user is None:
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: /create_first_aid_kit <title>\n"
            "Example: /create_first_aid_kit Home kit"
        )
        return

    title = " ".join(context.args).strip()
    if not title:
        await update.message.reply_text("Title must not be empty.")
        return

    try:
        app_user = await asyncio.to_thread(
            users_service.get_or_create_by_telegram_id,
            tg_user.id,
            tg_user.username,
        )
        kit = await asyncio.to_thread(
            first_aid_kits_service.create_first_aid_kit,
            title,
            [app_user["id"]],
        )
    except Exception:
        logger.exception("Failed to create first aid kit for telegram_id=%s", tg_user.id)
        await update.message.reply_text(
            "Could not create first aid kit. Check database connection and migrations."
        )
        return

    await update.message.reply_text(
        f"First aid kit created:\n"
        f"ID: {kit['id']}\n"
        f"Title: {kit['title']}"
    )


async def my_first_aid_kits_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if update.message is None:
        return
    tg_user = update.effective_user
    if tg_user is None:
        return

    try:
        app_user = await asyncio.to_thread(
            users_service.get_or_create_by_telegram_id,
            tg_user.id,
            tg_user.username,
        )
        kits = await asyncio.to_thread(
            first_aid_kits_service.list_first_aid_kits_for_user,
            app_user["id"],
        )
    except Exception:
        logger.exception("Failed to list first aid kits for telegram_id=%s", tg_user.id)
        await update.message.reply_text(
            "Could not load first aid kits. Check database connection and migrations."
        )
        return

    if not kits:
        await update.message.reply_text(
            "You have no first aid kits yet.\n"
            "Create one: /create_first_aid_kit <title>"
        )
        return

    lines = ["Your first aid kits:"]
    for kit in kits:
        created = kit["created_at"]
        if hasattr(created, "strftime"):
            created = created.strftime("%Y-%m-%d %H:%M UTC")
        lines.append(f"• #{kit['id']} — {kit['title']} (created {created})")
    await update.message.reply_text("\n".join(lines))


def _register_handlers(application: Application) -> None:
    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        CommandHandler("create_first_aid_kit", create_first_aid_kit_command)
    )
    application.add_handler(
        CommandHandler("my_first_aid_kits", my_first_aid_kits_command)
    )


def create_application() -> Application | None:
    """Build the bot application, or None if TELEGRAM_BOT_TOKEN is not configured."""
    load_private_properties()
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return None

    application = ApplicationBuilder().token(token).build()
    _register_handlers(application)
    return application


@asynccontextmanager
async def telegram_lifespan() -> AsyncIterator[None]:
    """Start polling while the host app runs; stop cleanly on shutdown."""
    application = create_application()
    if application is None:
        logger.warning(
            "TELEGRAM_BOT_TOKEN is not set; Telegram bot will not start."
        )
        yield
        return

    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    logger.info("Telegram bot polling started.")
    try:
        yield
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        logger.info("Telegram bot stopped.")


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    application = create_application()
    if application is None:
        logger.error(
            "TELEGRAM_BOT_TOKEN is not set. Add it to private.properties or the environment."
        )
        sys.exit(1)
    application.run_polling()


if __name__ == "__main__":
    main()
