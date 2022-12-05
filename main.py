import os
import time
import typing
import telegram
import logging
import dotenv
import nest_asyncio
from modules.browser import Browser
from utils.auth import auth
from telegram import Update
from telegram.ext import (
    Application,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)

# setup
nest_asyncio.apply()
dotenv.load_dotenv()

# logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


# set up app
application = Application.builder().token(os.environ.get("TELEGRAM_API_KEY")).build()



# dict of browser instances for each user.
browsers: typing.Dict[str, Browser] = {}


@auth()
async def send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send message to OpenAI."""

    # get the user's browser instance, or create one if it doesn't exist
    if update.effective_user.username not in browsers:
        await update.message.reply_text("Hang on, setting up your assistant...")

        browser = Browser(update.effective_user.id)
        browsers[update.effective_user.id] = browser

        await browser.connect()
        await browser.login()

    # get the response from the API
    await browser.send_message(update.message.text)

    # wait for the response to load
    await check_loading(update, browser)
    response = await browser.get_last_message()

    # send the response to the user
    await update.message.reply_text(
        response, parse_mode=telegram.constants.ParseMode.MARKDOWN_V2
    )


@auth()
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""

    if update.effective_user.username in browsers:
        await update.message.reply_text("You already have an assistant. Use /reset to reset your assistant.")
        return

    await update.message.reply_text("Getting ready...")

    browser = Browser(update.effective_user.id)
    browsers[update.effective_user.id] = browser

    await browser.connect()
    await browser.login()
    await update.message.reply_text("You are ready to start using Lydia. Say hello!")

@auth()
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset the browser instance for the user."""

    if update.effective_user.username in browsers:
        update.message.reply_text("Resetting your assistant...")
        await browsers[update.effective_user.username].login()
        await update.message.reply_text("You are ready to start using Lydia. Say hello!")
    else:
        await update.message.reply_text("You don't have an assistant yet. Use /start to get started.")


async def check_loading(update, browser):
    # with a timeout of 90 seconds, created a while loop that checks if loading is done
    loading = await browser.page.query_selector_all(
        "button[class^='PromptTextarea__PositionSubmit']>.text-2xl"
    )
    # keep checking len(loading) until it's empty or 45 seconds have passed
    await application.bot.send_chat_action(update.effective_chat.id, "typing")
    start_time = time.time()
    while len(loading) > 0:
        if time.time() - start_time > 90:
            break
        time.sleep(0.5)
        loading = await browser.page.query_selector_all(
            "button[class^='PromptTextarea__PositionSubmit']>.text-2xl"
        )
        await application.bot.send_chat_action(update.effective_chat.id, "typing")

async def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update cause error "%s"', context.error)

def main():
    # Handle messages    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, send))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reload", reset))
    application.add_error_handler(error)

    # Run the bot until the user presses Ctrl-C
    application.run_polling()


if __name__ == "__main__":
    main()