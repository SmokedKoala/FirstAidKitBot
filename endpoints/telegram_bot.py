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

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from properties_loader import load_private_properties
from services import first_aid_kits as first_aid_kits_service
from services import users as users_service
from services.scan_service import scan_image_bytes

logger = logging.getLogger(__name__)

_START_HELP = (
    "FirstAidKitBot\n\n"
    "Send a photo of a barcode — the bot will identify the medicine.\n\n"
    "Commands:\n"
    "/create_first_aid_kit <title> — create a first aid kit linked to you\n"
    "/my_first_aid_kits — list your first aid kits\n"
    "/rename_first_aid_kit <id> <new title> — rename a first aid kit\n"
    "/delete_first_aid_kit <id> — delete a first aid kit"
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


async def rename_first_aid_kit_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if update.message is None:
        return
    tg_user = update.effective_user
    if tg_user is None:
        return

    args = context.args or []
    if len(args) < 2 or not args[0].isdigit():
        await update.message.reply_text(
            "Usage: /rename_first_aid_kit <id> <new title>\n"
            "Example: /rename_first_aid_kit 3 Travel kit"
        )
        return

    kit_id = int(args[0])
    new_title = " ".join(args[1:]).strip()
    if not new_title:
        await update.message.reply_text("New title must not be empty.")
        return

    try:
        app_user = await asyncio.to_thread(
            users_service.get_or_create_by_telegram_id,
            tg_user.id,
            tg_user.username,
        )
        kit = await asyncio.to_thread(
            first_aid_kits_service.rename_first_aid_kit,
            kit_id,
            app_user["id"],
            new_title,
        )
    except Exception:
        logger.exception("Failed to rename first aid kit %s for telegram_id=%s", kit_id, tg_user.id)
        await update.message.reply_text("Could not rename first aid kit. Check database connection.")
        return

    if kit is None:
        await update.message.reply_text(
            f"First aid kit #{kit_id} not found or does not belong to you."
        )
        return

    await update.message.reply_text(
        f"First aid kit #{kit['id']} renamed to: {kit['title']}"
    )


async def delete_first_aid_kit_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if update.message is None:
        return
    tg_user = update.effective_user
    if tg_user is None:
        return

    args = context.args or []
    if not args or not args[0].isdigit():
        await update.message.reply_text(
            "Usage: /delete_first_aid_kit <id>\n"
            "Example: /delete_first_aid_kit 3"
        )
        return

    kit_id = int(args[0])

    try:
        app_user = await asyncio.to_thread(
            users_service.get_or_create_by_telegram_id,
            tg_user.id,
            tg_user.username,
        )
        kit = await asyncio.to_thread(
            first_aid_kits_service.get_first_aid_kit_by_id,
            kit_id,
        )
    except Exception:
        logger.exception("Failed to fetch first aid kit %s for telegram_id=%s", kit_id, tg_user.id)
        await update.message.reply_text("Could not load first aid kit. Check database connection.")
        return

    if kit is None:
        await update.message.reply_text(f"First aid kit #{kit_id} not found.")
        return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Yes, delete", callback_data=f"del_kit_yes:{kit_id}:{app_user['id']}"),
            InlineKeyboardButton("Cancel", callback_data=f"del_kit_no:{kit_id}"),
        ]
    ])
    await update.message.reply_text(
        f"Delete first aid kit #{kit_id} \"{kit['title']}\"?\n"
        "All medicines in it will also be deleted.",
        reply_markup=keyboard,
    )


async def delete_first_aid_kit_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if query is None:
        return
    await query.answer()

    data = query.data or ""
    if data.startswith("del_kit_no:"):
        await query.edit_message_text("Deletion cancelled.")
        return

    if data.startswith("del_kit_yes:"):
        parts = data.split(":")
        if len(parts) != 3:
            await query.edit_message_text("Invalid request.")
            return
        kit_id = int(parts[1])
        user_id = int(parts[2])
        try:
            deleted = await asyncio.to_thread(
                first_aid_kits_service.delete_first_aid_kit,
                kit_id,
                user_id,
            )
        except Exception:
            logger.exception("Failed to delete first aid kit %s", kit_id)
            await query.edit_message_text("Could not delete first aid kit. Check database connection.")
            return

        if deleted:
            await query.edit_message_text(f"First aid kit #{kit_id} deleted.")
        else:
            await query.edit_message_text(
                f"First aid kit #{kit_id} not found or does not belong to you."
            )


def _format_scan_result(result: dict) -> str:
    barcodes = result.get("barcodes", [])
    if not barcodes:
        return "No barcode found. Try a clearer photo with good lighting."

    lines = []
    for item in barcodes:
        lines.append(f"Barcode: {item['data']} ({item['symbology']})")

        medicine = item.get("medicine")
        if medicine:
            lines.append(f"Found in local DB: {medicine['medicine_name']}")
            continue

        medum = item.get("medum")
        if medum:
            products = medum.get("products", [])
            certs = medum.get("registration_certificates", [])
            if products:
                lines.append("Products:")
                for p in products[:5]:
                    lines.append(f"  • {p['name']}")
            if certs:
                lines.append("Registrations:")
                for c in certs[:3]:
                    lines.append(f"  • {c['registration']} {c['date_note']}".strip())
            lines.append(f"Source: {medum['page_url']}")
        else:
            note = item.get("medum_note", "")
            if note == "skipped_not_ean13":
                lines.append("Only EAN-13 barcodes are looked up in Medum.ru.")
            else:
                lines.append(f"Not found in Medum.ru: {item.get('medum_url', '')}")

        lines.append("")

    return "\n".join(lines).strip()


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or not update.message.photo:
        return

    await update.message.reply_text("Scanning barcode...")

    # Telegram sends several sizes; the last one is the highest resolution.
    photo = update.message.photo[-1]
    try:
        tg_file = await context.bot.get_file(photo.file_id)
        data = bytes(await tg_file.download_as_bytearray())
        result = await asyncio.to_thread(scan_image_bytes, data)
    except Exception:
        logger.exception("Failed to scan photo from telegram_id=%s", getattr(update.effective_user, "id", "?"))
        await update.message.reply_text("Could not scan the photo. Please try again.")
        return

    await update.message.reply_text(_format_scan_result(result))


def _register_handlers(application: Application) -> None:
    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        CommandHandler("create_first_aid_kit", create_first_aid_kit_command)
    )
    application.add_handler(
        CommandHandler("my_first_aid_kits", my_first_aid_kits_command)
    )
    application.add_handler(
        CommandHandler("rename_first_aid_kit", rename_first_aid_kit_command)
    )
    application.add_handler(
        CommandHandler("delete_first_aid_kit", delete_first_aid_kit_command)
    )
    application.add_handler(
        CallbackQueryHandler(delete_first_aid_kit_callback, pattern=r"^del_kit_")
    )
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))


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
