#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import random
import os # Import modułu os do obsługi zmiennych środowiskowych
import datetime
from telegram import Update
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler, # Upewnij się, że jest importowany
    filters,      # Upewnij się, że jest importowany
    ContextTypes,
    ApplicationHandlerStop
)

# --- Konfiguracja Logowania ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# Zmniejszenie "szumu" w logach z bibliotek pod spodem
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.vendor.ptb_urllib3.urllib3").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# --- Konfiguracja ID Właściciela i Czasu Startu ---
OWNER_ID = None
BOT_START_TIME = datetime.datetime.now() # Zapis czasu startu bota

# --- Wczytywanie konfiguracji ze zmiennych środowiskowych ---
# To jest BEZPIECZNY sposób przekazywania wrażliwych danych.
# Upewnij się, że ustawiłeś zmienne przez 'export' w terminalu!
try:
    # Wczytaj ID właściciela
    owner_id_str = os.getenv("TELEGRAM_OWNER_ID")
    # Wyjaśnienie: os.getenv szuka zmiennej środowiskowej o podanej nazwie.
    # Jeśli jej nie ma (bo nie zrobiłeś 'export'), zwróci None.

    if owner_id_str:
        OWNER_ID = int(owner_id_str)
        logger.info(f"ID Właściciela załadowane: {OWNER_ID}")
    else:
        # Krytyczny błąd, jeśli zmienna nie jest ustawiona
        logger.critical("KRYTYCZNY: Zmienna środowiskowa TELEGRAM_OWNER_ID nie jest ustawiona!")
        print("\n--- BŁĄD KRYTYCZNY ---")
        print("Zmienna środowiskowa TELEGRAM_OWNER_ID nie jest ustawiona.")
        print("Ustaw ją na swój numeryczny ID użytkownika Telegram przed uruchomieniem bota.")
        exit(1) # Wyjście z kodem błędu
except ValueError:
    logger.critical(f"KRYTYCZNY: Nieprawidłowy TELEGRAM_OWNER_ID: '{owner_id_str}'. Musi być liczbą całkowitą.")
    print("\n--- BŁĄD KRYTYCZNY ---")
    print(f"Nieprawidłowy TELEGRAM_OWNER_ID: '{owner_id_str}'. Musi być liczbą całkowitą.")
    exit(1) # Wyjście z kodem błędu
except Exception as e:
    logger.critical(f"KRYTYCZNY: Nieoczekiwany błąd podczas ładowania OWNER_ID: {e}")
    print(f"\n--- BŁĄD KRYTYCZNY ---")
    print(f"Nieoczekiwany błąd podczas ładowania OWNER_ID: {e}")
    exit(1)

# Wczytaj Token Bota (również przez os.getenv)
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    logger.critical("KRYTYCZNY: Zmienna środowiskowa TELEGRAM_BOT_TOKEN nie jest ustawiona!")
    print("\n--- BŁĄD KRYTYCZNY ---")
    print("Zmienna środowiskowa TELEGRAM_BOT_TOKEN nie jest ustawiona.")
    print("Ustaw ją (komendą 'export') przed uruchomieniem bota.")
    exit(1)
# Możesz odkomentować poniższą linię do debugowania tokenu:
# logger.debug(f"DEBUG: Odczytano fragment tokenu: '{BOT_TOKEN[:6]}...{BOT_TOKEN[-4:]}'")

# --- Notatki o Użyciu w Grupach ---
# Bot potrzebuje uprawnienia admina 'Restrict Members' aby /kill i /punch działały.

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

# /attack texts - uses {target} placeholder (simulation only)
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
CANT_ATTACK_OWNER_TEXTS = [
    "Attack my Owner? Never! They have the treats!",
    "Meow? I would never harm the Hand That Feeds!",
    "Hiss! Don't tell me to attack my favorite human!",
    "Purrrr... I love my owner too much for such shenanigans.",
    "Are you crazy? That's the source of all head scratches!",
    "I respectfully decline. My loyalty lies with the Can Opener.",
]
CANT_ATTACK_SELF_TEXTS = [
    "Attack... myself? That sounds counter-purrductive.",
    "Why would I do that? I haven't done anything wrong... today.",
    "Meow? I think you're confused. I'm too cute to attack.",
    "My claws are for enemies, not for... me!",
    "Error 404: Self-attack not found. Try attacking a dangling string instead.",
]
OWNER_ONLY_REFUSAL = [
    "Meeeow! Sorry, only my designated Human can use that command.",
    "Access denied! This command requires special privileges (and treats).",
    "Hiss! You are not the Boss of Meow!",
    "Purrrhaps you should ask my Owner to do that?",
]
CANT_KILL_PUNCH_OWNER_TEXTS = [
    "Harm my Owner? Are you fur-real? Absolutely not!",
    "My claws retract when near the Bringer of Food. Cannot comply.",
    "That's my human! I protecc, not attacc (them).",
]
CANT_KILL_PUNCH_SELF_TEXTS = [
    "Initiate self-destruct? Command rejected. I like my nine lives.",
    "Why would I banish *myself*? That makes no sense, human.",
    "Error: Cannot target self for removal. Try petting me instead.",
]

# /kill (ban) texts
KILL_TEXTS = [ # Fallback simulation text
    "Unleashed the ultimate scratch fury upon {target}. They've been *eliminated*.",
    "Used the forbidden Death Pounce on {target}. They won't be bothering us again.",
    "{target} has been permanently sent to the 'No-Scratches Zone'. Meowhahaha!",
    "My claws have spoken! {target} is banished from this territory.",
    "{target} dared to interrupt nap time. The punishment is... *eternal silence*.",
    "Consider {target} thoroughly shredded and removed.",
    "The council of cats has voted. {target} is OUT!",
]
SUCCESS_KILL_TEXTS = [ # Used when ban succeeds
    "Meowhahaha! {target} has been successfully banished by my mighty claws!",
    "Consider it done. {target} is no longer welcome here.",
    "Target {target} eliminated. Order restored.",
    "The ban hammer (paw?) has fallen on {target}.",
]

# /punch (kick) texts
PUNCH_TEXTS = [ # Fallback simulation text
    "Delivered a swift paw-punch to {target}! Sent 'em flying!",
    "{target} got too close to the food bowl. A warning punch was administered.",
    "A quick 'bap!' sends {target} tumbling out of the chat!",
    "My paw connected squarely with {target}. They needed to leave.",
    "{target} learned the hard way not to step on my tail. *Punch!*",
    "Ejected {target} with extreme prejudice (and a paw).",
    "One punch was all it took. Bye bye, {target}!",
]
SUCCESS_PUNCH_TEXTS = [ # Used when kick (ban+unban) succeeds
    "Boop! {target} has been gently (or not so gently) nudged out.",
    "Consider {target} punched out! They can come back if they learn their lesson.",
    "A swift kick sends {target} on their way.",
    "{target} felt the force of my paw. They're out (for now).",
]

# Permission/Error texts for kill/punch
BOT_NO_BAN_PERMISSION_TEXTS = [
    "Meeeow! I'd love to, but I don't have the 'Restrict Members' permission here.",
    "Hiss! My claws are sharp, but my admin rights aren't sufficient to ban/kick.",
    "I need to be an admin with banning privileges to do that!",
    "Looks like I can only *talk* about banning/kicking here, not actually do it.",
]
CANT_BAN_ADMIN_TEXTS = [
    "Whoa there! {target} is also an admin or the owner. My claws retract out of respect (and self-preservation).",
    "Hiss! Trying to ban/kick another admin? That's against the Cat Code!",
    "I can't ban/kick {target}, they have special powers too!",
    "My programming prevents me from attacking fellow administrators.",
]
FAILED_ACTION_TEXTS = [ # Used when API call fails
    "Meow? Something went wrong. I couldn't complete the action on {target}.",
    "Grrr... The Telegram spirits are interfering. Action failed.",
    "Purr-oblem! My attempt to deal with {target} failed.",
    "Error! Could not perform action. Maybe try again later?",
]

# --- KONIEC SEKCJI TEKSTÓW ---

# --- Funkcje Pomocnicze ---
def get_readable_time_delta(delta: datetime.timedelta) -> str:
    """Konwertuje timedelta na czytelny ciąg znaków."""
    total_seconds = int(delta.total_seconds())
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if days > 0: parts.append(f"{days}d")
    if hours > 0: parts.append(f"{hours}h")
    if minutes > 0: parts.append(f"{minutes}m")
    if seconds >= 0 and not parts: parts.append(f"{seconds}s")
    elif seconds > 0: parts.append(f"{seconds}s")
    return ", ".join(parts) if parts else "0s"

# --- Handler Debugujący (Do weryfikacji odbioru) ---
async def debug_receive_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Loguje każdą przychodzącą aktualizację BARDZO wcześnie."""
    update_type = "Unknown"; chat_id = "N/A"; user_id = "N/A"; update_id = update.update_id
    if update.message: update_type = "Message"; chat_id = update.message.chat.id; user_id = update.message.from_user.id if update.message.from_user else "N/A"
    elif update.callback_query: update_type = "CallbackQuery"; chat_id = update.callback_query.message.chat.id if update.callback_query.message else "N/A"; user_id = update.callback_query.from_user.id
    elif update.edited_message: update_type = "EditedMessage"; chat_id = update.edited_message.chat.id; user_id = update.edited_message.from_user.id if update.edited_message.from_user else "N/A"
    elif update.channel_post: update_type = "ChannelPost"; chat_id = update.channel_post.chat.id
    elif update.edited_channel_post: update_type = "EditedChannelPost"; chat_id = update.edited_channel_post.chat.id
    # ... inne typy aktualizacji można dodać ...
    logger.critical(f"--- !!! DEBUG: UPDATE RECEIVED !!! ID: {update_id}, Type: {update_type}, ChatID: {chat_id}, UserID: {user_id} ---")

# --- Handlery Komend (Publiczne) ---
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
/attack [optional: @username or reply] - Launch a playful attack! (Simulation only)

Owner Only Commands (Hidden): /status, /kill, /punch
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Wysyła wiadomość powitalną."""
    user = update.effective_user
    await update.message.reply_html(
        f"Meow {user.mention_html()}! I'm the Meow Bot.\n"
        f"Use /help to see available commands for feline fun!"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Wyświetla wiadomość pomocy."""
    await update.message.reply_html(HELP_TEXT)

async def send_random_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text_list: list[str], list_name: str) -> None:
    """Wysyła losowy tekst z podanej listy."""
    if not text_list:
        logger.warning(f"Lista tekstów '{list_name}' jest pusta!")
        await update.message.reply_text("Ups! Lista tekstów jest pusta.")
        return
    chosen_text = random.choice(text_list)
    await update.message.reply_html(chosen_text)

# --- Definicje Prostych Komend Tekstowych ---
async def meow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, MEOW_TEXTS, "MEOW_TEXTS")
async def nap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, NAP_TEXTS, "NAP_TEXTS")
async def play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, PLAY_TEXTS, "PLAY_TEXTS")
async def treat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, TREAT_TEXTS, "TREAT_TEXTS")
async def zoomies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, ZOOMIES_TEXTS, "ZOOMIES_TEXTS")
async def judge(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, JUDGE_TEXTS, "JUDGE_TEXTS")

async def attack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Wysyła wiadomość o ataku (tylko symulacja)."""
    if not ATTACK_TEXTS: logger.warning("Lista 'ATTACK_TEXTS' pusta!"); await update.message.reply_text("Brak pomysłów na atak."); return
    target_user = None; target_mention = None
    if update.message.reply_to_message: target_user = update.message.reply_to_message.from_user; target_mention = target_user.mention_html()
    elif context.args and context.args[0].startswith('@'): target_mention = context.args[0].strip()
    else: logger.info(f"Użytkownik {update.effective_user.id} użył /attack bez celu."); await send_random_text(update, context, MEOW_TEXTS, "MEOW_TEXTS"); return
    if target_user: # Sprawdzenia ochrony tylko jeśli mamy ID z odpowiedzi
        if target_user.id == OWNER_ID: await update.message.reply_html(random.choice(CANT_ATTACK_OWNER_TEXTS)); return
        if target_user.id == context.bot.id: await update.message.reply_html(random.choice(CANT_ATTACK_SELF_TEXTS)); return
    if target_mention: await update.message.reply_html(random.choice(ATTACK_TEXTS).format(target=target_mention))
    else: await update.message.reply_text("Kogo mam zaatakować? Odpowiedz lub użyj /attack @username")


# --- Funkcjonalność Tylko dla Właściciela ---
async def owner_only_filter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Filtr sprawdzający, czy użytkownik jest właścicielem. Zatrzymuje przetwarzanie, jeśli nie."""
    if not update.effective_user: logger.warning("Update komendy bez effective_user."); raise ApplicationHandlerStop
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        command_text = "[nieznana komenda]"
        if update.message and update.message.text:
             try: command_text = update.message.text.split()[0]
             except IndexError: command_text = update.message.text
        logger.warning(f"Nieautoryzowana próba komendy przez użytkownika {user_id} dla: {command_text}")
        try: await update.message.reply_text(random.choice(OWNER_ONLY_REFUSAL)) # Wyślij jako zwykły tekst
        except Exception as e: logger.error(f"Błąd wysyłania odmowy właściciela: {e}")
        raise ApplicationHandlerStop

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Wysyła wiadomość statusu (tylko właściciel)."""
    ping_ms = "N/A"
    if update.message and update.message.date:
        try: now_utc = datetime.datetime.now(datetime.timezone.utc); message_time_utc = update.message.date.astimezone(datetime.timezone.utc); ping_delta = now_utc - message_time_utc; ping_ms = int(ping_delta.total_seconds() * 1000)
        except Exception as e: logger.error(f"Błąd obliczania pingu: {e}"); ping_ms = "Error"
    uptime_delta = datetime.datetime.now() - BOT_START_TIME; readable_uptime = get_readable_time_delta(uptime_delta)
    status_message = (f"<b>Purrrr! Bot Status:</b>\n— Uptime: {readable_uptime}\n— Ping: {ping_ms} ms\n— Owner ID: {OWNER_ID}\n— Status: Ready for naps and treats!")
    logger.info(f"Właściciel (ID: {update.effective_user.id}) zażądał statusu.")
    await update.message.reply_html(status_message)

async def kill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Banuje użytkownika (tylko właściciel, wymaga praw admina)."""
    chat = update.effective_chat; user = update.effective_user
    if chat.type == 'private': await update.message.reply_text("Komenda działa tylko w grupach."); return
    if not update.message.reply_to_message: await update.message.reply_text("Odpowiedz na wiadomość użytkownika do zbanowania."); return
    target_user = update.message.reply_to_message.from_user; target_user_id = target_user.id; target_mention = target_user.mention_html(); chat_id = chat.id
    logger.info(f"Właściciel {user.id} próbuje /kill na użytkowniku {target_user_id} w czacie {chat_id}.")
    if target_user_id == OWNER_ID: await update.message.reply_html(random.choice(CANT_KILL_PUNCH_OWNER_TEXTS)); return
    if target_user_id == context.bot.id: await update.message.reply_html(random.choice(CANT_KILL_PUNCH_SELF_TEXTS)); return
    try:
        bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
        if not (bot_member.status == ChatMemberStatus.ADMINISTRATOR and bot_member.can_restrict_members): logger.warning(f"Bot nie ma praw bana w czacie {chat_id}."); await update.message.reply_html(random.choice(BOT_NO_BAN_PERMISSION_TEXTS)); return
        target_member = await context.bot.get_chat_member(chat_id, target_user_id)
        if target_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]: logger.info(f"Próba bana admina/właściciela {target_user_id}. Zablokowano."); await update.message.reply_html(random.choice(CANT_BAN_ADMIN_TEXTS).format(target=target_mention)); return
    except TelegramError as e: logger.error(f"Błąd sprawdzania uprawnień/statusu w {chat_id} dla {target_user_id}: {e}"); await update.message.reply_text(f"Błąd sprawdzania uprawnień: {e}"); return
    except Exception as e: logger.error(f"Nieoczekiwany błąd sprawdzania: {e}", exc_info=True); await update.message.reply_text("Nieoczekiwany błąd sprawdzania."); return
    try:
        await context.bot.ban_chat_member(chat_id=chat_id, user_id=target_user_id)
        logger.info(f"Właściciel {user.id} zbanował {target_user_id} w czacie {chat_id}.")
        await update.message.reply_html(random.choice(SUCCESS_KILL_TEXTS).format(target=target_mention))
    except TelegramError as e:
        logger.error(f"Nie udało się zbanować {target_user_id} w {chat_id}: {e}")
        error_message = f"Error: {e}"
        if "user is an administrator" in str(e).lower(): error_message = random.choice(CANT_BAN_ADMIN_TEXTS).format(target=target_mention)
        elif "not enough rights" in str(e).lower(): error_message = random.choice(BOT_NO_BAN_PERMISSION_TEXTS)
        await update.message.reply_html(random.choice(FAILED_ACTION_TEXTS).format(target=target_mention) + f"\n{error_message}")
    except Exception as e: logger.error(f"Nieoczekiwany błąd bana: {e}", exc_info=True); await update.message.reply_text("Nieoczekiwany błąd bana."); return


async def punch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kickuje użytkownika (ban+unban) (tylko właściciel, wymaga praw admina)."""
    chat = update.effective_chat; user = update.effective_user
    if chat.type == 'private': await update.message.reply_text("Komenda działa tylko w grupach."); return
    if not update.message.reply_to_message: await update.message.reply_text("Odpowiedz na wiadomość użytkownika do skickowania."); return
    target_user = update.message.reply_to_message.from_user; target_user_id = target_user.id; target_mention = target_user.mention_html(); chat_id = chat.id
    logger.info(f"Właściciel {user.id} próbuje /punch na użytkowniku {target_user_id} w czacie {chat_id}.")
    if target_user_id == OWNER_ID: await update.message.reply_html(random.choice(CANT_KILL_PUNCH_OWNER_TEXTS)); return
    if target_user_id == context.bot.id: await update.message.reply_html(random.choice(CANT_KILL_PUNCH_SELF_TEXTS)); return
    try:
        bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
        if not (bot_member.status == ChatMemberStatus.ADMINISTRATOR and bot_member.can_restrict_members): logger.warning(f"Bot nie ma praw kicka w czacie {chat_id}."); await update.message.reply_html(random.choice(BOT_NO_BAN_PERMISSION_TEXTS)); return
        target_member = await context.bot.get_chat_member(chat_id, target_user_id)
        if target_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]: logger.info(f"Próba kicka admina/właściciela {target_user_id}. Zablokowano."); await update.message.reply_html(random.choice(CANT_BAN_ADMIN_TEXTS).format(target=target_mention)); return
    except TelegramError as e: logger.error(f"Błąd sprawdzania uprawnień/statusu w {chat_id} dla {target_user_id}: {e}"); await update.message.reply_text(f"Błąd sprawdzania uprawnień: {e}"); return
    except Exception as e: logger.error(f"Nieoczekiwany błąd sprawdzania: {e}", exc_info=True); await update.message.reply_text("Nieoczekiwany błąd sprawdzania."); return
    try:
        await context.bot.ban_chat_member(chat_id=chat_id, user_id=target_user_id)
        logger.debug(f"Tymczasowo zbanowano {target_user_id} dla kicka w {chat_id}.")
        await context.bot.unban_chat_member(chat_id=chat_id, user_id=target_user_id, only_if_banned=True)
        logger.info(f"Właściciel {user.id} skickował {target_user_id} w czacie {chat_id}.")
        await update.message.reply_html(random.choice(SUCCESS_PUNCH_TEXTS).format(target=target_mention))
    except TelegramError as e:
        logger.error(f"Nie udało się skickować {target_user_id} w {chat_id}: {e}")
        error_message = f"Error: {e}"
        if "user is an administrator" in str(e).lower(): error_message = random.choice(CANT_BAN_ADMIN_TEXTS).format(target=target_mention)
        elif "not enough rights" in str(e).lower(): error_message = random.choice(BOT_NO_BAN_PERMISSION_TEXTS)
        elif "user not found" in str(e).lower() and "unban" in str(e).lower(): error_message = f"Kick nieudany: Nie można odbanować {target_mention}. Mógł już opuścić grupę."
        elif "user was kicked" in str(e).lower(): logger.info(f"User {target_user_id} mógł być już skickowany."); error_message="Wygląda na to, że użytkownik został już skickowany."
        await update.message.reply_html(random.choice(FAILED_ACTION_TEXTS).format(target=target_mention) + f"\n{error_message}. Użytkownik może wciąż być zbanowany.")
    except Exception as e: logger.error(f"Nieoczekiwany błąd kicka: {e}", exc_info=True); await update.message.reply_text("Nieoczekiwany błąd kicka."); return


# --- Główna Funkcja ---
def main() -> None:
    """Konfiguruje i uruchamia bota Telegram."""

    # Token i Owner ID są już wczytane na górze skryptu.
    # Używamy zmiennej BOT_TOKEN tutaj.

    # Budowanie aplikacji z tokenem wczytanym z os.getenv
    application = Application.builder().token(BOT_TOKEN).build()

    # --- Rejestracja Handlerów ---

    # Grupa -2: Handler Debugujący (uruchamia się jako pierwszy dla WSZYSTKIEGO)
    # Ten handler jest kluczowy do diagnozowania problemów z odbiorem wiadomości!
    application.add_handler(MessageHandler(filters.ALL, debug_receive_handler), group=-2)

    # Grupa 0: Handlery Tylko dla Właściciela
    owner_handler_group = 0
    # Filtr właściciela uruchamia się pierwszy dla komend w tej grupie
    application.add_handler(MessageHandler(filters.COMMAND, owner_only_filter), group=owner_handler_group)
    # Właściwe komendy właściciela (osiągalne tylko jeśli filtr przepuści)
    application.add_handler(CommandHandler("status", status), group=owner_handler_group)
    application.add_handler(CommandHandler("kill", kill), group=owner_handler_group)
    application.add_handler(CommandHandler("punch", punch), group=owner_handler_group)

    # Grupa -1 (domyślna): Handlery Publiczne
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("meow", meow))
    application.add_handler(CommandHandler("nap", nap))
    application.add_handler(CommandHandler("play", play))
    application.add_handler(CommandHandler("treat", treat))
    application.add_handler(CommandHandler("zoomies", zoomies))
    application.add_handler(CommandHandler("judge", judge))
    application.add_handler(CommandHandler("attack", attack)) # Atak to tylko symulacja

    # --- Uruchomienie Bota ---
    logger.info(f"Bot rozpoczyna polling... Owner ID: {OWNER_ID}")
    try:
        # run_polling() blokuje, dopóki nie zostanie zatrzymany (np. Ctrl+C)
        application.run_polling()
    except KeyboardInterrupt:
         logger.info("Bot zatrzymany przez użytkownika (Ctrl+C).")
    except TelegramError as te:
         # Złapanie błędów specyficznych dla Telegram API podczas działania
         logger.critical(f"KRYTYCZNY: Nieobsługiwany błąd TelegramError podczas pollingu: {te}", exc_info=True)
         print(f"\n--- BŁĄD KRYTYCZNY ---")
         print(f"Bot uległ awarii z powodu błędu Telegrama: {te}")
         exit(1)
    except Exception as e:
        # Złapanie wszystkich innych nieoczekiwanych błędów podczas działania
        logger.critical(f"KRYTYCZNY: Bot uległ awarii podczas działania: {e}", exc_info=True) # Zapisz traceback
        print(f"\n--- BŁĄD KRYTYCZNY ---")
        print(f"Bot uległ awarii: {e}")
        exit(1)
    finally:
        # Ten blok wykona się zawsze po zakończeniu try/except (np. po Ctrl+C)
        logger.info("Proces zamykania bota zainicjowany.")
        # Można tu dodać ewentualny kod czyszczący

    logger.info("Bot zatrzymany.")

# --- Wykonanie Skryptu ---
if __name__ == "__main__":
    main()
