#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import random
import os
import datetime
from telegram import Update
# Usunięto importy niepotrzebne przy symulacji
# from telegram.constants import ParseMode, ChatMemberStatus
# from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ApplicationHandlerStop # Wciąż potrzebne dla /status
)

# --- Konfiguracja Logowania ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.vendor.ptb_urllib3.urllib3").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- Konfiguracja ID Właściciela i Czasu Startu ---
OWNER_ID = None
BOT_START_TIME = datetime.datetime.now()

try:
    owner_id_str = os.getenv("TELEGRAM_OWNER_ID")
    if owner_id_str:
        OWNER_ID = int(owner_id_str)
        logger.info(f"ID Właściciela załadowane: {OWNER_ID}")
    else:
        logger.critical("KRYTYCZNY: Zmienna środowiskowa TELEGRAM_OWNER_ID nie jest ustawiona!")
        print("\n--- BŁĄD KRYTYCZNY ---")
        print("Zmienna środowiskowa TELEGRAM_OWNER_ID nie jest ustawiona.")
        exit(1)
except ValueError:
    logger.critical(f"KRYTYCZNY: Nieprawidłowy TELEGRAM_OWNER_ID: '{owner_id_str}'.")
    print("\n--- BŁĄD KRYTYCZNY ---")
    print(f"Nieprawidłowy TELEGRAM_OWNER_ID: '{owner_id_str}'. Musi być liczbą.")
    exit(1)
except Exception as e:
    logger.critical(f"KRYTYCZNY: Nieoczekiwany błąd podczas ładowania OWNER_ID: {e}")
    print(f"\n--- BŁĄD KRYTYCZNY --- \n{e}")
    exit(1)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    logger.critical("KRYTYCZNY: Zmienna środowiskowa TELEGRAM_BOT_TOKEN nie jest ustawiona!")
    print("\n--- BŁĄD KRYTYCZNY ---")
    print("Zmienna środowiskowa TELEGRAM_BOT_TOKEN nie jest ustawiona.")
    exit(1)

# --- SEKCJA TEKSTÓW KOTA ---

# (Wszystkie listy tekstów publicznych i symulacji jak w poprzedniej wersji)
MEOW_TEXTS = ["Meow!", "Purrrr...", "..."]
NAP_TEXTS = ["Zzzzz...", "..."]
PLAY_TEXTS = ["*Batting*", "..."]
TREAT_TEXTS = ["Treats, please!", "..."]
ZOOMIES_TEXTS = ["Hyperdrive!", "..."]
JUDGE_TEXTS = ["Judging...", "..."]
ATTACK_TEXTS = ["Launched attack on {target}", "..."] # Symulacja
KILL_TEXTS = ["{target} metaphorically eliminated.", "..."] # Symulacja
PUNCH_TEXTS = ["{target} text-punched!", "..."] # Symulacja

# Teksty odmowy (ważne dla ochrony właściciela)
CANT_TARGET_OWNER_TEXTS = [ # Zmieniono nazwę dla jasności
    "Meow! I can't target my Owner. They are protected by purr-power!",
    "Hiss! Targeting the Owner is strictly forbidden by cat law!",
    "Nope. Not gonna do it. That's my human!",
    "Access Denied: Cannot target the supreme leader (Owner).",
]
CANT_TARGET_SELF_TEXTS = [ # Zmieniono nazwę dla jasności
    "Target... myself? Why would I do that? Silly human.",
    "Error: Cannot target self. My paws have better things to do.",
    "I refuse to engage in self-pawm. Command ignored.",
]
OWNER_ONLY_REFUSAL = [ # Wciąż potrzebne dla /status
    "Meeeow! Sorry, only my designated Human can use that command.",
    "Access denied! This command requires special privileges (and treats).",
    "Hiss! You are not the Boss of Meow!",
]

# --- KONIEC SEKCJI TEKSTÓW ---

# --- Funkcje Pomocnicze ---
def get_readable_time_delta(delta: datetime.timedelta) -> str:
    """Konwertuje timedelta na czytelny ciąg znaków."""
    total_seconds = int(delta.total_seconds()); days, rem = divmod(total_seconds, 86400); hours, rem = divmod(rem, 3600); minutes, seconds = divmod(rem, 60)
    parts = [];
    if days > 0: parts.append(f"{days}d")
    if hours > 0: parts.append(f"{hours}h")
    if minutes > 0: parts.append(f"{minutes}m")
    if seconds >= 0 and not parts: parts.append(f"{seconds}s")
    elif seconds > 0: parts.append(f"{seconds}s")
    return ", ".join(parts) if parts else "0s"

# --- Handler Debugujący ---
async def debug_receive_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Loguje każdą przychodzącą aktualizację BARDZO wcześnie."""
    update_type = "Unknown"; chat_id = "N/A"; user_id = "N/A"; update_id = update.update_id
    if update.message: update_type = "Message"; chat_id = update.message.chat.id; user_id = update.message.from_user.id if update.message.from_user else "N/A"
    elif update.callback_query: update_type = "CallbackQuery"; chat_id = update.callback_query.message.chat.id if update.callback_query.message else "N/A"; user_id = update.callback_query.from_user.id
    logger.critical(f"--- !!! DEBUG: UPDATE RECEIVED !!! ID: {update_id}, Type: {update_type}, ChatID: {chat_id}, UserID: {user_id} ---")

# --- Handlery Komend (Publiczne) ---
# Zaktualizowano tekst pomocy
HELP_TEXT = """
Meeeow! Here are the commands you can use:

/start - Shows the welcome message.
/help - Shows this help message.
/meow - Get a random cat sound or phrase.
/nap - What's on a cat's mind during naptime?
/play - Random playful cat actions.
/treat - Demand treats!
/zoomies - Witness sudden bursts of cat energy!
/judge - Get judged by a superior feline.
/attack [reply/@user] - Launch a playful attack! (Sim)
/kill [reply/@user] - Metaphorically eliminate someone! (Sim)
/punch [reply/@user] - Deliver a textual punch! (Sim)

(Note: Owner cannot be targeted by attack/kill/punch)
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user; await update.message.reply_html(f"Meow {user.mention_html()}! I'm the Meow Bot.\nUse /help to see available commands!")
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await update.message.reply_html(HELP_TEXT)
async def send_random_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text_list: list[str], list_name: str) -> None:
    if not text_list: logger.warning(f"Lista '{list_name}' pusta!"); await update.message.reply_text("Ups! Lista pusta."); return
    await update.message.reply_html(random.choice(text_list))

# --- Definicje Prostych Komend Tekstowych ---
async def meow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, MEOW_TEXTS, "MEOW_TEXTS")
async def nap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, NAP_TEXTS, "NAP_TEXTS")
async def play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, PLAY_TEXTS, "PLAY_TEXTS")
async def treat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, TREAT_TEXTS, "TREAT_TEXTS")
async def zoomies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, ZOOMIES_TEXTS, "ZOOMIES_TEXTS")
async def judge(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, JUDGE_TEXTS, "JUDGE_TEXTS")

# --- Publiczne Komendy Symulacji z Ochroną Właściciela ---

async def attack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Wysyła wiadomość o ataku (symulacja), chroni właściciela."""
    if not ATTACK_TEXTS: logger.warning("Lista 'ATTACK_TEXTS' pusta!"); await update.message.reply_text("Brak pomysłów na atak."); return

    target_user = None; target_mention = None; target_user_id = None

    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        target_user_id = target_user.id
        target_mention = target_user.mention_html()

        # Sprawdzenie ochrony właściciela/bota PRZED wysłaniem
        if target_user_id == OWNER_ID:
            await update.message.reply_html(random.choice(CANT_TARGET_OWNER_TEXTS))
            return
        if target_user_id == context.bot.id:
            await update.message.reply_html(random.choice(CANT_TARGET_SELF_TEXTS))
            return
        # Jeśli doszło tutaj, cel jest OK

    elif context.args and context.args[0].startswith('@'):
        target_mention = context.args[0].strip()
        # Nie można sprawdzić ID właściciela dla @username, więc ochrona tu nie zadziała
        logger.info(f"Attack on {target_mention} by @username. Owner protection not available for this method.")
    else:
        await update.message.reply_text("Kogo mam zaatakować? Odpowiedz na wiadomość lub użyj /attack @username.")
        return

    # Wyślij symulację
    await update.message.reply_html(random.choice(ATTACK_TEXTS).format(target=target_mention))


async def kill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Wysyła wiadomość symulującą bana, chroni właściciela."""
    if not KILL_TEXTS: logger.warning("Lista 'KILL_TEXTS' pusta!"); await update.message.reply_text("Brak tekstów 'kill'."); return

    target_user = None; target_mention = None; target_user_id = None

    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        target_user_id = target_user.id
        target_mention = target_user.mention_html()

        # Sprawdzenie ochrony właściciela/bota PRZED wysłaniem
        if target_user_id == OWNER_ID:
            await update.message.reply_html(random.choice(CANT_TARGET_OWNER_TEXTS))
            return
        if target_user_id == context.bot.id:
            await update.message.reply_html(random.choice(CANT_TARGET_SELF_TEXTS))
            return

    elif context.args and context.args[0].startswith('@'):
        target_mention = context.args[0].strip()
        logger.info(f"Simulated kill on {target_mention} by @username. Owner protection not available.")
    else:
        await update.message.reply_text("Kogo mam 'zabić'? Odpowiedz na wiadomość lub użyj /kill @username.")
        return

    # Wyślij symulację
    await update.message.reply_html(random.choice(KILL_TEXTS).format(target=target_mention))


async def punch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Wysyła wiadomość symulującą kicka, chroni właściciela."""
    if not PUNCH_TEXTS: logger.warning("Lista 'PUNCH_TEXTS' pusta!"); await update.message.reply_text("Brak tekstów 'punch'."); return

    target_user = None; target_mention = None; target_user_id = None

    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        target_user_id = target_user.id
        target_mention = target_user.mention_html()

        # Sprawdzenie ochrony właściciela/bota PRZED wysłaniem
        if target_user_id == OWNER_ID:
            await update.message.reply_html(random.choice(CANT_TARGET_OWNER_TEXTS))
            return
        if target_user_id == context.bot.id:
            await update.message.reply_html(random.choice(CANT_TARGET_SELF_TEXTS))
            return

    elif context.args and context.args[0].startswith('@'):
        target_mention = context.args[0].strip()
        logger.info(f"Simulated punch on {target_mention} by @username. Owner protection not available.")
    else:
        await update.message.reply_text("Kogo mam 'uderzyć'? Odpowiedz na wiadomość lub użyj /punch @username.")
        return

    # Wyślij symulację
    await update.message.reply_html(random.choice(PUNCH_TEXTS).format(target=target_mention))


# --- Funkcjonalność Tylko dla Właściciela ---
async def owner_only_filter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Filtr sprawdzający, czy użytkownik jest właścicielem (tylko dla komend w jego grupie)."""
    if not update.effective_user: logger.warning("Update bez effective_user."); raise ApplicationHandlerStop
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        command_text = "[nieznana komenda]"
        if update.message and update.message.text:
             try: command_text = update.message.text.split()[0]
             except IndexError: command_text = update.message.text
        logger.warning(f"Nieautoryzowana próba komendy przez {user_id} dla: {command_text}")
        try: await update.message.reply_text(random.choice(OWNER_ONLY_REFUSAL))
        except Exception as e: logger.error(f"Błąd wysyłania odmowy: {e}")
        raise ApplicationHandlerStop

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Wysyła wiadomość statusu (tylko właściciel)."""
    # Filtr właściciela działa dla tej komendy (patrz rejestracja handlerów)
    ping_ms = "N/A"
    if update.message and update.message.date:
        try: now_utc = datetime.datetime.now(datetime.timezone.utc); msg_utc = update.message.date.astimezone(datetime.timezone.utc); ping_ms = int((now_utc - msg_utc).total_seconds() * 1000)
        except Exception as e: logger.error(f"Błąd pingu: {e}"); ping_ms = "Error"
    uptime_delta = datetime.datetime.now() - BOT_START_TIME; readable_uptime = get_readable_time_delta(uptime_delta)
    status_msg = (f"<b>Purrrr! Status:</b>\n— Uptime: {readable_uptime}\n— Ping: {ping_ms} ms\n— Owner: {OWNER_ID}\n— Gotowy!")
    logger.info(f"Właściciel ({update.effective_user.id}) zażądał statusu.")
    await update.message.reply_html(status_msg)


# --- Główna Funkcja ---
def main() -> None:
    """Konfiguruje i uruchamia bota Telegram."""
    # Token i Owner ID są już wczytane globalnie.

    # Budowanie aplikacji
    application = Application.builder().token(BOT_TOKEN).build()

    # --- Rejestracja Handlerów ---

    # Grupa -2: Handler Debugujący (uruchamia się jako pierwszy dla WSZYSTKIEGO)
    application.add_handler(MessageHandler(filters.ALL, debug_receive_handler), group=-2)

    # Grupa 0: Handlery Tylko dla Właściciela (tylko /status)
    owner_handler_group = 0
    # Filtr właściciela uruchamia się pierwszy DLA KOMEND W TEJ GRUPIE
    application.add_handler(MessageHandler(filters.COMMAND, owner_only_filter), group=owner_handler_group)
    # Tylko /status jest teraz w tej grupie chronionej filtrem
    application.add_handler(CommandHandler("status", status), group=owner_handler_group)

    # Grupa -1 (domyślna): Handlery Publiczne (w tym /attack, /kill, /punch)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("meow", meow))
    application.add_handler(CommandHandler("nap", nap))
    application.add_handler(CommandHandler("play", play))
    application.add_handler(CommandHandler("treat", treat))
    application.add_handler(CommandHandler("zoomies", zoomies))
    application.add_handler(CommandHandler("judge", judge))
    application.add_handler(CommandHandler("attack", attack)) # Teraz publiczny
    application.add_handler(CommandHandler("kill", kill))     # Teraz publiczny (symulacja)
    application.add_handler(CommandHandler("punch", punch))   # Teraz publiczny (symulacja)

    # --- Uruchomienie Bota ---
    logger.info(f"Bot rozpoczyna polling... Owner ID: {OWNER_ID}")
    try:
        application.run_polling()
    except KeyboardInterrupt:
         logger.info("Bot zatrzymany przez użytkownika (Ctrl+C).")
    except Exception as e:
        logger.critical(f"KRYTYCZNY: Bot uległ awarii podczas działania: {e}", exc_info=True)
        print(f"\n--- BŁĄD KRYTYCZNY ---")
        print(f"Bot uległ awarii: {e}")
        exit(1)
    finally:
        logger.info("Proces zamykania bota zainicjowany.")

    logger.info("Bot zatrzymany.")

# --- Wykonanie Skryptu ---
if __name__ == "__main__":
    main()
