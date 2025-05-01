#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import random
import os
import datetime # Dodano do uptime/ping
from telegram import Update
# Usunięto ParseMode, bo reply_html go nie potrzebuje
from telegram.ext import Application, CommandHandler, ContextTypes # Usunięto MessageHandler, filters, ApplicationHandlerStop, bo nie używamy grup/filtra
# Jeśli chcesz debugować, dodaj z powrotem: from telegram.ext import MessageHandler, filters, ApplicationHandlerStop

# --- Konfiguracja Logowania ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.vendor.ptb_urllib3.urllib3").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- Konfiguracja ID Właściciela i Czasu Startu ---
OWNER_ID = None
BOT_START_TIME = datetime.datetime.now() # Zapis czasu startu bota

# --- Wczytywanie konfiguracji (POPRAWIONE!) ---
try:
    # POPRAWKA: Użycie os.getenv()
    owner_id_str = os.getenv("TELEGRAM_OWNER_ID")
    if owner_id_str:
        OWNER_ID = int(owner_id_str)
        logger.info(f"Owner ID loaded: {OWNER_ID}")
    else:
        logger.critical("CRITICAL: TELEGRAM_OWNER_ID environment variable not set!")
        print("\n--- FATAL ERROR ---")
        print("Environment variable TELEGRAM_OWNER_ID is not set.")
        exit(1)
except ValueError:
    logger.critical(f"CRITICAL: Invalid TELEGRAM_OWNER_ID: '{owner_id_str}'. Must be an integer.")
    print("\n--- FATAL ERROR ---")
    print(f"Invalid TELEGRAM_OWNER_ID: '{owner_id_str}'. Must be an integer.")
    exit(1)
except Exception as e:
    logger.critical(f"CRITICAL: Unexpected error loading OWNER_ID: {e}")
    print(f"\n--- FATAL ERROR --- \n{e}")
    exit(1)

# POPRAWKA: Użycie os.getenv() dla tokenu
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    logger.critical("CRITICAL: TELEGRAM_BOT_TOKEN environment variable not set!")
    print("\n--- FATAL ERROR ---")
    print("Environment variable TELEGRAM_BOT_TOKEN is not set.")
    exit(1)
# logger.debug(f"DEBUG: Read token fragment: '{BOT_TOKEN[:6]}...{BOT_TOKEN[-4:]}'") # Odkomentuj do debugowania

# --- SEKCJA TEKSTÓW KOTA ---

# /meow texts
MEOW_TEXTS = [
    "Meow!", "Purrrr...", "Feed me, human!", "Where's my nap spot?", "Miaow?",
    "I require pets.", "Is that... tuna?", "Staring intently...",
    "*knocks something off the table*", "Mrow?", "Let me outside... no, wait, inside!",
    "I knead this blanket... and maybe your leg.", "The red dot! Where did it go?!",
    "Ignoring you is my cardio.", "Sleeping in a sunbeam.", "Bring me shiny things!",
    "My bowl is... tragically empty.", "Hiss! (Just kidding... maybe.)",
    "Presenting my belly... it's a trap!", "Zoomies commencing in 3... 2... 1...",
    "Prrrrt?", "Meow meow!", "Mrrrrraw!", "Did I hear the fridge open?",
    "I require attention. Immediately.", "Eeeeeek! (a mouse!)",
    "Just woke up from an 18-hour nap.", "Head boop!", "Did someone say... *treats*?",
]

# /nap texts
NAP_TEXTS = [
    "Zzzzz...", "Dreaming of chasing mice.", "Do not disturb the royal nap.",
    "Found the perfect sunbeam.", "Curled up in a tight ball.", "Too comfy to move.",
    "Just five more minutes... or hours.", "Sleeping level: Expert.",
    "Charging my batteries for zoomies.", "Is it nap time yet? Oh, it always is.",
    "Comfort is my middle name.", "Where's the warmest spot? That's where I am.",
    "Sleeping with one eye open.", "Purring on standby.", "Don't wake the sleeping beast!",
]

# /play texts
PLAY_TEXTS = [
    "*Batting at an invisible speck*", "Attack the dangly thing!", "Where's the string?",
    "Pounce!", "Wrestling the toy mouse... I WON!", "Hide and seek? I'm under the couch.",
    "My hunting instincts are tingling.", "Chasing my own tail!",
    "Got the zoomies - must play!", "Do I hear a crinkle ball?",
    "Ambush from around the corner!", "Hunting your feet under the covers.",
    "This toy insulted my ancestors. It must perish.", "Curtain climbing commencing!",
    "Bring the wand toy!",
]

# /treat texts
TREAT_TEXTS = [
    "Treats, please!", "My bowl echoes with emptiness.", "Did you say... *tuna*?",
    "I performed a cute trick, where's my reward?",
    "I can hear the treat bag rustling from three rooms away.", "Feed me, peasant!",
    "A snack would be purrfect.", "I solemnly swear I am up to no good... unless there are treats.",
    "The fastest way to my heart is through my stomach.", "Just a little nibble? Pleeeease?",
    "Staring at you with big, cute eyes... until you give me a treat.",
    "Does that cupboard contain treats? Must investigate.",
    "My internal clock says it's snack time.",
    "In exchange for a treat, I shall allow you to pet me. Maybe.", "Food is life.",
]

# /zoomies texts
ZOOMIES_TEXTS = [
    "Hyperdrive activated!", "*Streaks past at Mach 1*", "Wall climbing initiated!",
    "Can't stop, won't stop!", "Running laps around the house!",
    "The floor is lava... and a racetrack!", "Did a ghost just tickle me? MUST RUN!",
    "Sudden burst of energy!", "My ancestors were cheetahs, probably.",
    "Leaving a trail of chaos in my wake.", "Skidded around the corner!",
    "Ludicrous speed achieved!", "Parkour! (over the furniture).",
    "I don't know why I'm running, but I can't stop!", "This is better than catnip!",
]

# /judge texts
JUDGE_TEXTS = [
    "Judging your life choices.", "That outfit is... questionable.",
    "I saw what you did. I'm not impressed.",
    "My disappointment is immeasurable, and my day is ruined.",
    "*Slow blink of disapproval*", "Are you *sure* about that?",
    "Silence. Just pure, condescending silence.", "I am watching. Always watching.",
    "You call *that* a pet?", "Hmmph.", "Did you really think *this* is what I wanted?",
    "Your existence amuses... and annoys me.", "You need better ideas.",
    "Shaking my head in pity (internally).",
    "I could do that better... if I had thumbs and motivation.",
]

# /attack texts - uses {target} as a placeholder (simulation only)
ATTACK_TEXTS = [
    "Launched a sneak attack on {target}'s ankles! Got 'em!",
    "Performed the forbidden pounce onto {target}'s keyboard. Mwahaha!",
    "Used {target}'s leg as a scratching post. Meowch!",
    "I jumped on {target}'s head and demanded immediate attention!",
    "Ambushed {target} from under the bed! Rawr!",
    "Calculated trajectory... Pounced on {target}'s unsuspecting back!",
    "Unleashed fury upon {target}'s favorite sweater. It looked at me funny.",
    "Bunny-kicked {target}'s arm into submission.",
    "Surprise attack! {target} never saw it coming.",
    "Stalked {target} across the room... then attacked a dust bunny instead. Close call, {target}!",
    "Bit {target}'s toes. They were asking for it.",
    "Clawed my way up {target}'s leg. I needed a better view.",
    "A swift bap bap bap to {target}'s face!",
    "Tangled {target} in a web of... well, mostly just my own enthusiasm.",
    "Practiced my hunting skills on {target}. You're welcome.",
]

# Refusal texts
CANT_TARGET_OWNER_TEXTS = [
    "Meow! I can't target my Owner. They are protected by purr-power!",
    "Hiss! Targeting the Owner is strictly forbidden by cat law!",
    "Nope. Not gonna do it. That's my human!",
    "Access Denied: Cannot target the supreme leader (Owner).",
]
CANT_TARGET_SELF_TEXTS = [
    "Target... myself? Why would I do that? Silly human.",
    "Error: Cannot target self. My paws have better things to do.",
    "I refuse to engage in self-pawm. Command ignored.",
]
OWNER_ONLY_REFUSAL = [ # Needed for /status
    "Meeeow! Sorry, only my designated Human can use that command.",
    "Access denied! This command requires special privileges (and treats).",
    "Hiss! You are not the Boss of Meow!",
]

# /kill (simulation only) texts - uses {target} placeholder
KILL_TEXTS = [
    "Unleashed the ultimate scratch fury upon {target}. They've been *metaphorically eliminated*.",
    "Used the forbidden Death Pounce simulation on {target}. They won't be bothering us again (in theory).",
    "{target} has been permanently sent to the 'No-Scratches Zone' (in my mind). Meowhahaha!",
    "My claws have spoken! {target} is banished from this territory (symbolically).",
    "{target} dared to interrupt nap time. The punishment is... *imaginary eternal silence*.",
    "Consider {target} thoroughly shredded (in a simulation) and removed.",
    "The council of cats has voted. {target} is OUT (of my good graces)!",
]

# /punch (simulation only) texts - uses {target} placeholder
PUNCH_TEXTS = [
    "Delivered a swift paw-punch simulation to {target}! Sent 'em flying (in my imagination)!",
    "{target} got too close to the food bowl. A warning text-punch was administered.",
    "A quick 'bap!' (as text) sends {target} tumbling out of the chat (mentally)!",
    "My textual paw connected squarely with {target}. They needed to leave (this conversation thread).",
    "{target} learned the hard way not to step on my tail (via text). *Punch!*",
    "Ejected {target} with extreme prejudice (and a message).",
    "One text-punch was all it took. Bye bye, {target}!",
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

# --- Handler Debugujący (Opcjonalny - odkomentuj jeśli potrzebny) ---
# async def debug_receive_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#     """Loguje każdą przychodzącą aktualizację BARDZO wcześnie."""
#     update_type = "Unknown"; chat_id = "N/A"; user_id = "N/A"; update_id = update.update_id
#     if update.message: update_type = "Message"; chat_id = update.message.chat.id; user_id = update.message.from_user.id if update.message.from_user else "N/A"
#     elif update.callback_query: update_type = "CallbackQuery"; chat_id = update.callback_query.message.chat.id if update.callback_query.message else "N/A"; user_id = update.callback_query.from_user.id
#     logger.critical(f"--- !!! DEBUG: UPDATE RECEIVED !!! ID: {update_id}, Type: {update_type}, ChatID: {chat_id}, UserID: {user_id} ---")

# --- Handlery Komend ---
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
Owner Only Commands (Hidden): /status
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user; await update.message.reply_html(f"Meow {user.mention_html()}! I'm the Meow Bot.\nUse /help to see available commands!")
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await update.message.reply_html(HELP_TEXT)
async def send_random_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text_list: list[str], list_name: str) -> None:
    if not text_list: logger.warning(f"List '{list_name}' empty!"); await update.message.reply_text("Oops! List empty."); return
    await update.message.reply_html(random.choice(text_list))

# Definicje prostych komend tekstowych
async def meow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, MEOW_TEXTS, "MEOW_TEXTS")
async def nap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, NAP_TEXTS, "NAP_TEXTS")
async def play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, PLAY_TEXTS, "PLAY_TEXTS")
async def treat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, TREAT_TEXTS, "TREAT_TEXTS")
async def zoomies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, ZOOMIES_TEXTS, "ZOOMIES_TEXTS")
async def judge(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, JUDGE_TEXTS, "JUDGE_TEXTS")

# Publiczne komendy symulacji z ochroną właściciela
async def attack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ATTACK_TEXTS: logger.warning("List 'ATTACK_TEXTS' empty!"); await update.message.reply_text("No attack ideas."); return
    target_user = None; target_mention = None; target_user_id = None
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        target_user_id = target_user.id; target_mention = target_user.mention_html()
        if target_user_id == OWNER_ID: await update.message.reply_html(random.choice(CANT_TARGET_OWNER_TEXTS)); return
        if target_user_id == context.bot.id: await update.message.reply_html(random.choice(CANT_TARGET_SELF_TEXTS)); return
    elif context.args and context.args[0].startswith('@'): target_mention = context.args[0].strip()
    else: await update.message.reply_text("Who to attack? Reply or use /attack @username."); return
    await update.message.reply_html(random.choice(ATTACK_TEXTS).format(target=target_mention))

async def kill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not KILL_TEXTS: logger.warning("List 'KILL_TEXTS' empty!"); await update.message.reply_text("No 'kill' texts."); return
    target_user = None; target_mention = None; target_user_id = None
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        target_user_id = target_user.id; target_mention = target_user.mention_html()
        if target_user_id == OWNER_ID: await update.message.reply_html(random.choice(CANT_TARGET_OWNER_TEXTS)); return
        if target_user_id == context.bot.id: await update.message.reply_html(random.choice(CANT_TARGET_SELF_TEXTS)); return
    elif context.args and context.args[0].startswith('@'): target_mention = context.args[0].strip()
    else: await update.message.reply_text("Who to 'kill'? Reply or use /kill @username."); return
    await update.message.reply_html(random.choice(KILL_TEXTS).format(target=target_mention))

async def punch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not PUNCH_TEXTS: logger.warning("List 'PUNCH_TEXTS' empty!"); await update.message.reply_text("No 'punch' texts."); return
    target_user = None; target_mention = None; target_user_id = None
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        target_user_id = target_user.id; target_mention = target_user.mention_html()
        if target_user_id == OWNER_ID: await update.message.reply_html(random.choice(CANT_TARGET_OWNER_TEXTS)); return
        if target_user_id == context.bot.id: await update.message.reply_html(random.choice(CANT_TARGET_SELF_TEXTS)); return
    elif context.args and context.args[0].startswith('@'): target_mention = context.args[0].strip()
    else: await update.message.reply_text("Who to 'punch'? Reply or use /punch @username."); return
    await update.message.reply_html(random.choice(PUNCH_TEXTS).format(target=target_mention))


# Komenda /status (tylko właściciel)
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Wysyła wiadomość statusu (tylko właściciel)."""
    user_id = update.effective_user.id
    if user_id == OWNER_ID:
        ping_ms = "N/A"
        if update.message and update.message.date:
            try: now_utc = datetime.datetime.now(datetime.timezone.utc); msg_utc = update.message.date.astimezone(datetime.timezone.utc); ping_ms = int((now_utc - msg_utc).total_seconds() * 1000)
            except Exception as e: logger.error(f"Błąd pingu: {e}"); ping_ms = "Error"
        uptime_delta = datetime.datetime.now() - BOT_START_TIME; readable_uptime = get_readable_time_delta(uptime_delta)
        status_msg = (f"<b>Purrrr! Bot Status:</b>\n— Uptime: {readable_uptime}\n— Ping: {ping_ms} ms\n— Owner: {OWNER_ID}\n— Status: Ready!")
        logger.info(f"Właściciel ({user_id}) zażądał statusu.")
        await update.message.reply_html(status_msg)
    else:
        # Odmowa, jeśli nie właściciel
        logger.warning(f"Nieautoryzowana próba /status przez {user_id}.")
        await update.message.reply_text(random.choice(OWNER_ONLY_REFUSAL))

# --- Główna Funkcja ---
def main() -> None:
    """Konfiguruje i uruchamia bota Telegram."""
    # Token i Owner ID są już wczytane globalnie.

    # Budowanie aplikacji
    application = Application.builder().token(BOT_TOKEN).build()

    # --- Rejestracja Handlerów ---
    # (Prosta rejestracja bez grup, bo filtrowanie /status jest w funkcji)

    # Opcjonalny Debug Handler (jeśli potrzebujesz, odkomentuj importy i tę linię)
    # application.add_handler(MessageHandler(filters.ALL, debug_receive_handler), group=-2) # group=-2 nada mu priorytet

    # Rejestracja wszystkich komend
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("meow", meow))
    application.add_handler(CommandHandler("nap", nap))
    application.add_handler(CommandHandler("play", play))
    application.add_handler(CommandHandler("treat", treat))
    application.add_handler(CommandHandler("zoomies", zoomies))
    application.add_handler(CommandHandler("judge", judge))
    application.add_handler(CommandHandler("attack", attack)) # Publiczna symulacja
    application.add_handler(CommandHandler("status", status)) # Publiczny, ale sprawdza ID w środku
    application.add_handler(CommandHandler("kill", kill))     # Publiczna symulacja
    application.add_handler(CommandHandler("punch", punch))   # Publiczna symulacja

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
