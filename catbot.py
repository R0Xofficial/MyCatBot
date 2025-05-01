import logging
import random
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- HERE ADD YOUR CAT TEXT ---
# Your text, you can add it easly
CAT_TEXTS = [
    "Meow!",
    "Purrrr...",
    "Feed me, human!",
    "Where's my nap spot?",
    "Miaow?",
    "I require pets.",
    "Is that... tuna?",
    "Stare intently...",
    "*knocks something off the table*",
    "Mrow?",
    "Let me outside... no, wait, inside!",
    "I knead this blanket... and maybe your leg.",
    "The red dot! Where did it go?!",
    "Ignoring you is my cardio.",
    "Sleeping in a sunbeam.",
    "Bring me shiny things!",
    "My bowl is... tragically empty.",
    "Hiss! (Just kidding... maybe.)",
    "Presenting my belly... it's a trap!",
    "Zoomies commencing in 3... 2... 1...",
]
# --- TEXT SECTION END ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Wysyła wiadomość powitalną, gdy użytkownik wyda komendę /start."""
    user = update.effective_user
    await update.message.reply_html(
        f"Hi {user.mention_html()}! I'm the Meow Bot. Use /meow to get a random cat sound or phrase!",
    )

async def meow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Wysyła losowy koci tekst, gdy użytkownik wyda komendę /meow."""
    if not CAT_TEXTS:
        await update.message.reply_text("Oops! The cat text list is empty.")
        return

    chosen_text = random.choice(CAT_TEXTS)
    await update.message.reply_text(chosen_text)

def main() -> None:
    """Uruchamia bota."""
    # Pobierz token bota ze zmiennej środowiskowej
    # To bezpieczniejszy sposób niż wpisywanie tokenu bezpośrednio w kodzie
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("Error: TELEGRAM_BOT_TOKEN environment variable not set!")
        print("\n--- ERROR ---")
        print("You not set TELEGRAM_BOT_TOKEN.")
        print("Set it before start catbot :]")
        return

    # Stwórz obiekt Application
    application = Application.builder().token(token).build()

    # Dodaj obsługę komend
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("meow", meow))

    # Uruchom bota w trybie polling (nasłuchiwanie aktualizacji)
    logger.info("Starting bot...")
    application.run_polling()
    logger.info("Bot stopped.")

if __name__ == "__main__":
    main()
