#!/usr/bin/env python
# -*- coding: utf-8 -*-

# --- MyCatBot [TEST] ---
# The bot is initially ready to go, but not everything has been thoroughly tested yet.
# Errors, exceptions, and unexpected restarts are possible.
# Report issues if you see them!

import logging
import random
import os
import requests
import html
import sqlite3
import speedtest
import asyncio
from typing import List, Tuple
from telegram import Update, User, Chat, constants
from telegram.constants import ChatType, ParseMode, ChatMemberStatus
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ApplicationHandlerStop
from telegram.error import TelegramError
from telegram.request import HTTPXRequest
from datetime import datetime, timezone, timedelta

# --- Logging Configuration ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.vendor.ptb_urllib3.urllib3").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- Owner ID Configuration & Bot Start Time ---
OWNER_ID = None
BOT_START_TIME = datetime.now()
TENOR_API_KEY = None
DB_NAME = "catbot_data.db"
LOG_CHAT_ID = None

# --- Load configuration from environment variables ---
try:
    owner_id_str = os.getenv("TELEGRAM_OWNER_ID")
    if owner_id_str: OWNER_ID = int(owner_id_str); logger.info(f"Owner ID loaded: {OWNER_ID}")
    else: raise ValueError("TELEGRAM_OWNER_ID environment variable not set or empty")
except (ValueError, TypeError) as e: logger.critical(f"CRITICAL: Invalid or missing TELEGRAM_OWNER_ID: {e}"); print(f"\n--- FATAL ERROR --- \nInvalid or missing TELEGRAM_OWNER_ID."); exit(1)
except Exception as e: logger.critical(f"CRITICAL: Unexpected error loading OWNER_ID: {e}"); print(f"\n--- FATAL ERROR --- \nUnexpected error loading OWNER_ID: {e}"); exit(1)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN: logger.critical("CRITICAL: TELEGRAM_BOT_TOKEN not set!"); print("\n--- FATAL ERROR --- \nTELEGRAM_BOT_TOKEN is not set."); exit(1)

TENOR_API_KEY = os.getenv("TENOR_API_KEY")
if not TENOR_API_KEY: logger.warning("WARNING: TENOR_API_KEY not set. Themed GIFs disabled.")
else: logger.info("Tenor API Key loaded. Themed GIFs enabled.")

log_chat_id_str = os.getenv("LOG_CHAT_ID")
if log_chat_id_str:
    try:
        LOG_CHAT_ID = int(log_chat_id_str)
        logger.info(f"Log Chat ID loaded: {LOG_CHAT_ID}")
    except ValueError:
        logger.error(f"Invalid LOG_CHAT_ID: '{log_chat_id_str}' is not a valid integer. Will fallback to OWNER_ID for logs.")
        LOG_CHAT_ID = None
else:
    logger.info("LOG_CHAT_ID not set. Operational logs (blacklist/sudo) will be sent to OWNER_ID if available.")

# --- Database Initialization ---
def init_db():
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                language_code TEXT,
                is_bot INTEGER,
                last_seen TEXT 
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_username ON users (username)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                user_id INTEGER PRIMARY KEY,
                reason TEXT,
                banned_by_id INTEGER,
                timestamp TEXT 
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sudo_users (
                user_id INTEGER PRIMARY KEY,
                added_by_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        
        conn.commit()
        logger.info(f"Database '{DB_NAME}' initialized successfully (tables users, blacklist, sudo_users ensured).")
    except sqlite3.Error as e:
        logger.error(f"SQLite error during DB initialization: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()

# --- Blacklist Helper Functions ---
def add_to_blacklist(user_id: int, banned_by_id: int, reason: str | None = "No reason provided.") -> bool:
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        current_timestamp_iso = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            "INSERT OR IGNORE INTO blacklist (user_id, reason, banned_by_id, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, reason, banned_by_id, current_timestamp_iso)
        )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"SQLite error adding user {user_id} to blacklist: {e}", exc_info=True)
        return False
    finally:
        if conn:
            conn.close()

def remove_from_blacklist(user_id: int) -> bool:
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM blacklist WHERE user_id = ?", (user_id,))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"SQLite error removing user {user_id} from blacklist: {e}", exc_info=True)
        return False
    finally:
        if conn:
            conn.close()

def get_blacklist_reason(user_id: int) -> str | None:
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT reason FROM blacklist WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            return row[0]
        return None
    except sqlite3.Error as e:
        logger.error(f"SQLite error checking blacklist reason for user {user_id}: {e}", exc_info=True)
        return None
    finally:
        if conn:
            conn.close()

def is_user_blacklisted(user_id: int) -> bool:
    return get_blacklist_reason(user_id) is not None

# --- Blacklist Check Handler ---
async def check_blacklist_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return

    user = update.effective_user

    if user.id == OWNER_ID:
        return

    if is_user_blacklisted(user.id):
        user_mention_log = f"@{user.username}" if user.username else str(user.id)
        message_text_preview = update.message.text[:50] if update.message.text else "[No text content]"
        
        logger.info(f"User {user.id} ({user_mention_log}) is blacklisted. Silently ignoring and blocking interaction: '{message_text_preview}'")
        
        raise ApplicationHandlerStop

# --- Sudo ---
def add_sudo_user(user_id: int, added_by_id: int) -> bool:
    """Adds a user to the sudo list."""
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        current_timestamp_iso = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            "INSERT OR IGNORE INTO sudo_users (user_id, added_by_id, timestamp) VALUES (?, ?, ?)",
            (user_id, added_by_id, current_timestamp_iso)
        )
        conn.commit()
        return cursor.rowcount > 0 
    except sqlite3.Error as e:
        logger.error(f"SQLite error adding sudo user {user_id}: {e}", exc_info=True)
        return False
    finally:
        if conn:
            conn.close()

def remove_sudo_user(user_id: int) -> bool:
    """Removes a user from the sudo list."""
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sudo_users WHERE user_id = ?", (user_id,))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"SQLite error removing sudo user {user_id}: {e}", exc_info=True)
        return False
    finally:
        if conn:
            conn.close()

def is_sudo_user(user_id: int) -> bool:
    """Checks if a user is on the sudo list (specifically, not checking if they are THE owner)."""
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM sudo_users WHERE user_id = ?", (user_id,))
        return cursor.fetchone() is not None
    except sqlite3.Error as e:
        logger.error(f"SQLite error checking sudo for user {user_id}: {e}", exc_info=True)
        return False 
    finally:
        if conn:
            conn.close()

def is_privileged_user(user_id: int) -> bool:
    """Checks if the user is the Owner or a Sudo user."""
    if user_id == OWNER_ID:
        return True
    return is_sudo_user(user_id)

# --- User logger ---
def update_user_in_db(user: User | None):
    if not user:
        return
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        current_timestamp_iso = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO users (user_id, username, first_name, last_name, language_code, is_bot, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                language_code = excluded.language_code,
                is_bot = excluded.is_bot,
                last_seen = excluded.last_seen 
        """, (
            user.id, user.username, user.first_name, user.last_name,
            user.language_code, 1 if user.is_bot else 0, current_timestamp_iso
        ))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"SQLite error updating user {user.id} in users table: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()

def get_user_from_db_by_username(username_query: str) -> User | None:
    if not username_query:
        return None
    conn = None
    user_obj: User | None = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        normalized_username = username_query.lstrip('@').lower()
        cursor.execute(
            "SELECT user_id, username, first_name, last_name, language_code, is_bot FROM users WHERE LOWER(username) = ?",
            (normalized_username,)
        )
        row = cursor.fetchone()
        if row:
            user_obj = User(
                id=row[0], username=row[1], first_name=row[2] or "",
                last_name=row[3], language_code=row[4], is_bot=bool(row[5])
            )
            logger.info(f"User @{username_query} found in DB with ID {row[0]}.")
    except sqlite3.Error as e:
        logger.error(f"SQLite error fetching user by username '{username_query}': {e}", exc_info=True)
    finally:
        if conn:
            conn.close()
    return user_obj

async def log_user_from_interaction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user:
        update_user_in_db(update.effective_user)
    
    if update.message and update.message.reply_to_message and update.message.reply_to_message.from_user:
        update_user_in_db(update.message.reply_to_message.from_user)

def get_all_sudo_users_from_db() -> List[Tuple[int, str]]:
    conn = None
    sudo_list = []
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, timestamp FROM sudo_users ORDER BY timestamp DESC")
        rows = cursor.fetchall()
        for row in rows:
            sudo_list.append((row[0], row[1]))
    except sqlite3.Error as e:
        logger.error(f"SQLite error fetching all sudo users: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()
    return sudo_list

# --- CAT TEXTS SECTION ---
# /meow texts - General cat noises and behaviors
MEOW_TEXTS = [
    "Meow! 🐾", "Purrrr...", "Feed me, human! <i>Now!</i>", "Where's my nap spot? 😴", "Miaow?",
    "I require pets. *Immediately*. ✨", "Is that... tuna? 🐟", "Staring intently... 👀",
    "<i>*knocks something off the table*</i> Oops.", "Mrow? 🤔", "Let me outside... no, wait, inside! <strike>Make up your mind!</strike>",
    "I knead this blanket... and maybe <b>your</b> leg. 🧶", "The red dot! Where did it go?! 🔴",
    "Ignoring you is my cardio. 😼", "Sleeping in a sunbeam. ☀️", "Bring me shiny things! ✨",
    "My bowl is... <i>tragically</i> empty. 😩", "Hiss! (Just kidding... maybe. 😈)",
    "Presenting my belly... <b>it's a trap!</b>", "Zoomies commencing in 3... 2... 1... 💥",
    "Prrrrt?", "Meow meow! 🎶", "Mrrrrraw! <pre>Loudly.</pre>", "Did I hear the fridge open? 🧊",
    "I require attention. <b>Immediately</b>. 🚨", "Eeeeeek! (a mouse!) 🐭",
    "Just woke up from an 18-hour nap. What year is it? 🕰️", "Head boop! ❤️", "Did someone say... <i>treats</i>? 🎁",
    "You woke me up... now suffer my wrath! 😾", "Your bed? Nope. Mine now. 👑",
    "I knocked it over because I love you. (...and it was in the way).", "I'm majestic. Worship me. 🙏",
    "I saw a bird once. Still not over it. 🐦", "Let's play! No—too much. I'm biting now. 😬",
    "This tail? It's trying to get me! 😱", "You moved? Betrayal. 😭",
    "I rule this house. You just pay the bills. 🏰", "Laser pointer or sorcery? 🧙‍♂️",
    "Don't touch the tummy. Seriously. 🚫", "Did I just see another cat?! Intruder! ⚔️",
    "What's this button do? *boop* 🖱️", "I'll sit here. Right on your keyboard. ⌨️",
    "No thoughts. Just meows. <pre>empty head</pre>", "I meow, therefore I am. 🤔",
    "That noise was suspicious. Panic mode engaged. 😨",
    "It's 3 AM. Let’s party! 🎉", "I bring chaos and fur. Deal with it. 😎",
    "Time to destroy the toilet paper. 🧻", "Window open? Instant birdwatching! 📺",
    "Sniff... ew. Sniff again. 🤔", "Did you say... <code>vet</code>?! 🏥 Nooooo!", "My tail is alive! It has a mind of its own!",
    "This box shrank... not me. 📦", "I'm fast. You're slow. Try to catch me! 💨",
    "Don't mind me—I'm just judging you. 🧐", "Hooman, fix the blanket folds. It's suboptimal.",
    "I demand tribute in the form of treats. 💰", "My purring is <b>not</b> consent to belly rubs.",
    "Silently plotting your next nap spot invasion.", "Attack the foot. Retreat. Repeat. ⚔️",
    "Is the food bowl half empty or half full? Either way, MORE! 🍽️",
    "My elegance is only matched by my capacity for mischief. ✨😈",
    "Chirp! Trill! Meeeow! 🦜", "Yawn... big stretch! Ready for my next nap.",
    "Rubbing against your legs. That means feed me. Or pet me. Or both. Or maybe I'm just marking my property.",
    "Staring into the void... or maybe just at a particularly interesting wall texture. 🧱",
    "That plant looked suspicious. Had to investigate with my teeth. 🪴 Bite!",
    "Cleaning my paws meticulously. One must maintain standards. Especially toe beans. ✨🐾",
    "Followed you into the bathroom. I'm your official Potty Supervisor now. 👀🚽",
    "Making biscuits on the air. Practicing my dough technique. 👨‍🍳 Maybe later on your chest.",
    "My purr motor is running smoothly. Calibrated for maximum soothing... or annoyance. Vroom vroom. 🚗",
    "If I fits, I sitz. Even if 'fits' is debatable. 📐<0xC2><0xA0>precarious_cat",
    "The sound of a can opener is the siren song of my people. 🥫❤️ Answer the call!",
    "Grooming interrupted by... existential dread! Or maybe just a hairball incoming. 🤢",
    "Talking back to the birds outside. They gossip too much. 🗣️🐦",
    "Is this lap occupied? Doesn't matter. Claimed. Resistance is futile.",
    "Paw under the door. Just checking if you're still alive... and if that door leads to snacks. 🚪🐾",
    "Smacked the dog gently (or not so gently). Asserting my place in the hierarchy. 🐶👑",
    "Curiosity didn't kill the cat, it just made me knock over your expensive vase.",
    "Rolling around on the floor in ecstasy. Why? Because floor. That's why. 🤪",
    "My meow is music. Appreciate my avant-garde symphony. 🎼 Sometimes it's opera.",
    "Brought you a 'gift'. It's a bottle cap. Cherish it. You're welcome. 👑",
    "My ears are twitching independently. Processing multiple data streams... mostly sounds of potential food packaging. 👂📡",
    "Slow blink. That means I acknowledge your presence without hostility... probably. 😉",
    "Hiding under the furniture. It's my secret lair. No humans allowed (unless bringing treats). 🏰",
    "Climbing the curtains. Because Everest is too far away and less satisfyingly shreddable. 🏔️",
    "Licking plastic bags. Don't ask why. It's a complex flavor profile. 🛍️👅 Science!",
    "I demand entry to the forbidden closet! What secrets does it hold? Socks? Monsters? Both? 🚪🗝️",
    "Sniffing your shoes intently. Where have you BEEN, human? What other animals did you pet?! 👟🕵️ Betrayal!",
    "Sharpening claws on the forbidden sofa. It feels... necessary. A primal urge. 🛋️🔪",
    "A single, plaintive 'mew'. Translate it as 'I desire an unspecified service immediately'.",
    "I am liquid. Watch me pour myself into this impossibly small container. 💧📦 Physics is optional.",
    "The water bowl is full, but the forbidden allure of the dripping faucet is superior. 💧👑 Freshness!",
    "Suddenly stopping mid-zoom to groom intensely. Must maintain dignity amidst chaos. ✨",
    "Chattering at the window. Those squirrels mock my very existence! Must... plot... revenge! 🐿️💢",
    "Presenting my backside. It's a sign of trust. Or I just don't want to look at you right now. 🍑",
    "I require a box. Any box. The smaller and more inconvenient, the better. Provide one NOW. 📦",
    "Muffled meow from under the duvet. Send snacks and perhaps a small oxygen tank.",
    "Woke up. Chose violence (playful, yet painful, ankle biting). 😬 It's morning!",
    "I walk this path. Right across your keyboard. As is tradition. Do not question the ancient ways. 🚶‍♀️⌨️",
    "My whiskers brushed against it. Therefore, under feline law, it is mine. Property claimed. ✨",
    "Staring at a blank wall like it holds the secrets of the universe. Maybe it does.",
    "Paw dipped in your water glass. Just testing the temperature. And maybe adding flavor.",
    "Tail twitching erratically. Warning: May pounce on anything (or nothing) without notice.",
    "Sitting in the loaf position. Maximum coziness achieved. 🍞",
    "Letting out a tiny 'mew' that somehow conveys immense suffering and starvation. Feed me.",
    "Calculated jump... miscalculated landing. *Thump*. I meant to do that.",
    "Eyes wide, pupils dilated. Engaging 'hunter mode' for... a dust bunny.",
    "Rubbing my face on the corner of your laptop. Needs more cat scent.",
    "Digging frantically in the litter box like I'm searching for buried treasure. 🏴‍☠️💎",
    "Ignoring the expensive cat bed to sleep on a pile of dirty laundry. It smells like... victory. 🧺",
    "Why are you typing? You should be petting. Realign your priorities.",
    "Batting at your dangling phone charger. It looks like a snake. A fun snake. 🐍",
    "Chirping sound activated. Usually reserved for birds or intense focus.",
    "Stretching... s-t-r-e-t-c-h-i-n-g... okay, nap time again.",
    "Running sideways with arched back. Crab cat mode engaged! 🦀",
    "I smell food. Somewhere. I will find it. And I will sit near it expectantly. 👃",
    "Licking my nose. System check complete. Ready for... whatever.",
    "Is that... catnip? 👀🌿 The good stuff?",
    "Making eye contact, then slowly pushing something off the edge. Defiance.",
    "Meow? Meeeow! MROW! (Translation: Varies, but probably involves food or attention).",
    "Sitting in the sink. It's cool. It's concave. It's perfect.",
    "Watching the washing machine spin. Mesmerizing. 😵‍💫",
    "Can I have some of that? Whatever you're eating. Sharing is caring. Give it.",
    "Just remembered I have a tail. *pounce*",
    "Current mood: inscrutable.",
    "I tolerate your presence. Barely.",
    "Scratching the door frame. Just leaving my signature. ✍️",
    "I have trained my human well. They know the meaning of the stare. 👀",
    "The sound of kibble hitting the bowl: music to my ears. 🎶",
    "Meow.",
]

# /nap texts
NAP_TEXTS = [
    "Zzzzz... 😴", "Dreaming of chasing mice... <i>big</i>, slow ones. 🐭", "Do not disturb the royal nap. Trespassers will be hissed at. 👑",
    "Found the perfect sunbeam patch. Solar charging commenced. Bliss. ☀️🔋", "Curled up in a tight cinnamon roll. Maximum floof achieved.", "Too comfy to move. Send telepathic snacks. Help needed (later).",
    "Just five more minutes... or five hours. Who's counting? ⏰<0xE3><0x80><0x80>🤷‍♀️", "Sleeping level: <b>Grandmaster</b>. Bow before my stillness. 🏆",
    "Charging my batteries for midnight zoomies and chaos. 🔋💥", "Is it nap time yet? Oh, it always is. My schedule is flexible. ✅",
    "Comfort is my middle name. Annoyance is my game (when awake).", "Where's the warmest, softest spot? That's where I manifest. 🔥☁️",
    "Sleeping with one eye open... and one ear swiveling. Always vigilant. 👀👂", "Purring on low power mode. <pre>Deep bass rumble activated.</pre>", "Don't wake the sleeping beast! Unless you have tuna. Then maybe. 🐲🐟",
    "Do not poke the floof. Seriously. My claws are on standby. 🚫👈", "Nap interrupted? Prepare for the Silent Treatment™ and passive-aggressive ignoring.",
    "Dreaming of an endless salmon river and a world without vacuum cleaners. 🍣🏞️", "This blanket is now Fort Kickass. No entry without the password (treats). 🏰",
    "Shhh... dreaming of world domination, one comfy spot at a time (and snacks). 🌍🍪", "Soft spot detected. Initiating nap sequence T-minus 3 seconds.",
    "Eyes closed. Thoughts: <i>buffering...</i> Brain empty. Pure bliss.", "Current status: melted into the furniture fabric. Send snacks via osmosis.",
    "If I fits, I naps. The box dimension provides excellent structural integrity for sleeping. 📦", "My snore is a delicate symphony of nasal passages. 🎶 ...or maybe a tiny chainsaw.",
    "I changed sleeping positions. That counts as my exercise quota for the day. 💪 Achievement unlocked.", "Napping: a full-time job with excellent benefits (dreams of birds). Very demanding.",
    "Too tired to care. Still cuter than you, though. 😉", "I blinked slowly. That was my major contribution to the household for this hour.",
    "Sleeping through the minor inconveniences of life. Like your existence. Wake me when it's dinner time. ☄️", "Gravity feels stronger during nap time. It's feline physics.",
    "My fur absorbs sleep energy, ambient heat, and all your dark clothing fibers.", "Nap level: <b>Nirvana</b>. Do not disrupt my enlightenment. 🧘",
    "Out of order until further notice. Please leave a message (preferably tuna) after the snore. 🚫", "Occupied: enter the nap zone at your own peril. Sudden movements may trigger claw deployment. ⚠️",
    "Cushion claimed in the name of the Cat Kingdom. Do not attempt reclamation. 🚩 My flag is planted.", "I nap therefore I am. (Mostly nap, occasionally demand food).",
    "Nap goal: 16 hours achieved. Stretching for 20. Aiming for the world record. 🥇", "Stretched luxuriously. Felt exhausting. Definitely need another nap to recover.",
    "Curled like a perfect, fluffy croissant. Do not eat. 🥐", "Horizontal is my preferred state of being. <pre>gravitational surrender</pre>",
    "The world can wait. My nap schedule is divinely ordained and cannot be altered. ✋", "Entering low-power mode... initiating dream sequence... Loading... 💤",
    "Hibernating. Wake me if the apocalypse involves laser pointers. See you next season. Maybe. 🐻‍❄️🔴", "Powered down for essential system maintenance (dreaming). Check back in 6-8 business hours.",
    "My spirit animal is a sentient pillow. ☁️", "Deep sleep achieved. Entering REM cycle (Rapid Eye Mouse-chasing/Mysterious Red Dot hunting).",
    "This nap is sponsored by Sheer Laziness™ and Supreme Comfort®.", "Do not operate heavy machinery while napping. Or try to make me move.",
    "Currently processing... the optimal angle for sunbeam absorption. Please wait. ⏳☀️", "My brain has switched off. Please leave a message after the beep... Zzzzz... Purrrr... Zzzz.",
    "The ancient art of doing absolutely nothing, perfectly executed. Mastered. 🖼️", "Maximum relaxation achieved. Warning: may spontaneously twitch or emit soft 'mrrp' sounds.",
    "Twitching my paws. Probably winning a glorious battle against a giant feather wand in my dreams. ⚔️💤",
    "Soaking up the quiet. And the radiating heat from your laptop. 🔥💻", "Body temperature regulation achieved via strategic napping and micro-adjustments.",
    "I'm not sleeping, I'm meditating on the profound emptiness... of my food bowl. 🧘🍽️",
    "Found the fresh laundry pile. It's warm, smells like you, and is therefore mine now. 🧺 Claimed.",
    "If you need me, I'll be in my nap dimension, accessible only via extreme quiet or the sound of a treat bag.",
    "Energy saving mode: ON. All non-essential functions (like listening to you) disabled. 💡",
    "Peace. Quiet. Softness. Warmth. Nap quadfecta achieved. Checkmate, consciousness. ✨", "My nap schedule is very strict: whenever I feel like it, wherever I happen to be.",
    "Achieved perfect sphinx loaf position. Regal and sleepy. 10/10. 👑🍞", "Dreaming of ruling the world from this incredibly comfortable throne (cardboard box). 👑📦",
    "My internal clock is set to 'nap'. The alarm is the sound of the fridge opening. Always. ⏰🧊", "Can't talk. Busy converting oxygen into snores. Try again never.",
    "So comfortable, I might be fusing with this blanket at a molecular level. Send snacks (and maybe a spatula later).",
    "My only ambition right now is to sink deeper into this cushion until I achieve singularity. Ambition: in progress.",
    "Practicing the ancient feline art of 'Nidra'. Or just sleeping really hard. Same difference.",
    "The world is too loud and full of non-napping activities. Retreating into my fluffy fortress. 🎧🏰", "Shhh. Genius (at optimizing sleep positions) at work.",
    "Absorbing solar energy like a furry, sleepy, judgmental plant. ☀️🪴😠",
    "My battery is low and it's getting dark. (Even if it's 1 PM and sunny). Recharge required. 🔋",
    "Just resting my eyes... and my ears, paws, tail, brain... for several hours. 👀➡️😴",
    "This nap is essential for my mental health. And frankly, for yours too. A rested cat is a less destructive cat.",
    "I've forgotten how to be vertical. Is it hard? Seems pointless.",
    "If napping were an Olympic sport, I'd have all the gold medals, plus a special lifetime achievement award. 🥇🥇🥇🏆",
    "My primary purpose in life: locate soft surfaces, apply body, initiate sleep sequence.",
    "Drifting away on a sea of dreams... mostly involving infinite chin scratches and compliant furniture. 🌊✨",
    "Do not mistake my closed eyes for weakness. I'm conserving energy for judging you later.",
    "Powering down non-essential systems... Purr module remaining active on low.",
    "Current location: Cloud Nine (it's actually your favorite sweater). ☁️",
    "Engaged Sleep Mode. Any attempts to disengage will be met with claws.",
    "My body has entered a state of blissful inertia. Please do not disturb the equilibrium.",
    "Dreaming I'm a mighty hunter... stalking a dust bunny across the plains of the living room rug.",
    "Snoozing. Hard. Do I make it look easy? It takes dedication.",
    "The quiet hum of the house is my lullaby. That, and my own purring.",
    "Reached peak coziness. Further movement is physically impossible.",
    "Twitching tail indicates active dream state. Probably chasing something annoying. Possibly you.",
    "Ah, the sweet embrace of unconsciousness. My favorite.",
]

# /play texts
PLAY_TEXTS = [
    "*Batting at an invisible speck of dust* ✨ It looked shifty!", "Attack the dangly thing! Make it dangle more! 🧶", "Where's the string? Show me the string! My sworn enemy! String!",
    "<b>POUNCE!</b> 💥 Did I get it? What was 'it'?", "Wrestling the toy mouse... victory is mine! Fatality! 🏆🐭", "Hide and seek? I'm under the couch blending into the shadows. You'll *never* find me! 👀",
    "My hunting instincts are tingling! Something must be hunted! Preferably something feathery! 🏹", "Chasing my own tail! It's elusive! It mocks me! One day... 🌀",
    "Got the zoomies - which means playtime is MANDATORY! 💨 Prepare yourself!", "Do I hear a crinkle ball? The sweet sound of chaos! 🎶 Bring it!",
    "Ambush from around the corner! Surprise! Bet you didn't expect the fluff! 😼", "Hunting your feet under the covers. Beware the Bed Shark! 🦈🦶",
    "This stuffed bird insulted my ancestors. It must be disemboweled. For honor! 💀🐦", "Curtain climbing commencing! To the summit! Because it's there! 🧗",
    "Bring the wand toy! The feathery one! No, the *other* feathery one! Engage the prey drive! 🎣",
    "That sock looked at me funny. It must be disciplined with extreme prejudice. Sock justice! 🧦", "Time to sprint at full speed across the room—for absolutely no discernible reason. GO!",
    "<i>*Pounces dramatically, misses entirely, slides into wall*</i> ... Calculated. Precision fluff maneuver.", "I'm a fierce jungle predator trapped in a fluffy housecat body! Fear my tiny, ineffective roar! 🦁",
    "Couch? More like tactical launch platform! Engaging thrusters! 🚀", "Tag, you're it! *vanishes into another dimension, probably under the bed*",
    "I heard a pin drop three rooms away. Threat assessment: Maximum. Attack mode: ON. 🚨", "Sneak... sneak... wiggle butt... <b>POUNCE!</b> Gotcha!",
    "Everything is a toy if you're brave enough. Especially that precarious stack of papers.",
    "Why walk when you can <i>leap</i> across the treacherous void between furniture items?", "Zoomies in progress. Clear the runway! Collision imminent! Please stand back. 🚧",
    "The toy moved. Or did the earth shift? Existential crisis incoming... must bat repeatedly to be sure! 🤔", "*tail flick* Battle readiness confirmed. Let the games begin! ⚔️",
    "Your pen? Mine now. Perfect for batting under the sofa. Bye pen! 🖊️💨", "Under the bed is my secret battle arena. Enter if you dare (and bring toys). 🛏️",
    "I'm training for the Cat Olympics. Gold in Synchronized Napping and Freestyle Pouncing. 🏅", "This paper bag is my kingdom now. All hail Bag Cat! Kneel before the rustling! 👑🛍️",
    "Rug corner slightly folded? Perfect ambush spot! You'll never see me coming! 🧐", "Sneaky mode: activated. Ninja level stealth engaged. I am the shadows. 🥷",
    "*wild eyes* The pre-zoomie crazies are setting in... Something... is about to happen... 🤪",
    "You’ll never catch me—I'm pure velocity! <i>zoom!</i> Eat my dust! ⚡", "Interrupt play? Unforgivable. Prepare for the Ankle Attack of Fury!",
    "Ceiling? Seems reachable this time. Gravity is merely a suggestion for lesser beings. 🚀", "I fight shadows for dominance. The shadows put up a surprisingly good fight.",
    "Don't blink. You might miss my spectacular aerial fail followed by a look of utter indifference. 😹", "The Siren Call of the Cardboard Box! Must investigate! Must sit! Irresistible! 📦",
    "Batting the water in my bowl. Creating miniature tidal waves! Science! 🌊", "This piece of string is my ultimate nemesis! Prepare for epic battle! En garde! 🧵🤺",
    "The laser dot is back! The uncatchable foe! Must... catch... the... precious! 🔴😵‍💫",
    "Toy mouse has been successfully neutralized (decapitated). Mission accomplished. Awaiting next target. 🎯",
    "Practicing my parkour skills. The bookshelf is my Mount Midoriyama. Need more chalk... I mean, grip. 🧗‍♂️",
    "Engaged in mortal combat with a large dust bunny. It fought valiantly. I prevailed. 💪",
    "Skittering sideways like a startled crab. Why? Because it confuses the humans! It's fun! 🦀",
    "Attacking the empty air with great ferocity. You never know what invisible demons lurk there.",
    "Is that a fly? A gnat? A floating speck? <i>MUST HUNT! MAXIMUM ALERT!</i> 🦟", "My energy levels are spiking! Playtime protocol override initiated! Brace for impact!",
    "Leaping gracefully through the air... directly into a closed door. Nailed it. Solid landing. 👍",
    "This cardboard box isn't just a box, it's a spaceship / fortress / ambush location. 🚀📦🏰",
    "Engaging wiggle-butt sequence prior to pounce... calibrating trajectory... charging attack sequence... 🍑➡️💥",
    "Everything that jingles or crinkles must be investigated thoroughly with paws! What secrets do they hold? 🔔",
    "Tackling the innocent houseplant. It looked too green and stationary. Must introduce chaos. 🪴💥",
    "Play bow initiated! This is your final warning! Let the games begin! 🙇‍♂️",
    "Running up and down the stairs like a furry demon is chasing me. It's called interval training.",
    "Sliding across the hardwood floor in my socks (imaginary socks). Need for speed! Tokyo Drift! 🏎️",
    "My claws are out (just a little), my eyes are wide like saucers. Prepare for... unpredictable fun! 🤪",
    "Hide the breakables. And the dangly things. And maybe your ankles. Play mode is fully engaged. 🏺➡️🚫",
    "Chasing sunbeams across the floor. Elusive, warm, delightful prey! Must catch the light! ☀️✨",
    "This rug is perfect for sharpening claws AND executing surprise rolling attacks.",
    "I'm not clumsy, I'm performing advanced, unpredictable tactical acrobatics. You wouldn't understand.🤸‍♀️",
    "Let's play 'find the cat toy I deliberately batted under the heaviest piece of furniture'. Hint: Good luck.",
    "Biting my own tail again. Why is it following me?! Get it off! 🤔💢",
    "Suddenly fascinated by a piece of fluff on the carpet. Intense focus... *bat*... *bat*... Annihilated.",
    "Your dangling earring / necklace / hair looks like a prime target. Hold very, very still! ✨👂",
    "Unraveling the toilet paper: a timeless classic, a performance art piece. TP streamer activated! 🧻🏆",
    "Pretending this discarded bottle cap is the world's greatest treasure. My precious! 👑",
    "Got the zoomies AND the munchies simultaneously. Need to play-attack the food bowl! 💨🍪",
    "Let's wrestle! Prepare to be subjected to the legendary Bunny Kick of Doom! 🐇💥 Surrender!",
    "Stalking a shadow like it's the most dangerous prey imaginable. It moved!",
    "Using your leg as a launch point. Sorry/not sorry. Higher ground needed!",
    "The crinkle tunnel is calling! Must dash through it repeatedly!",
    "Batting at reflections. Who is that handsome cat? Must attack!",
    "Bringing you my favorite toy (soggy and slightly mangled). Throw it! Throw it now!",
    "Play-growling. It sounds ferocious (in my head). Grrrr!",
    "Randomly jumping straight up in the air. Just testing gravity.",
    "Hiding behind the curtain. Peek-a-boo! I see you!",
    "Attacking the water stream from the faucet. Must defeat the liquid enemy!",
    "Rolling a pen back and forth. Simple pleasures.",
    "My tail is puffed up! Playtime intensity level: MAXIMUM!",
]

# /treat texts
TREAT_TEXTS = [
    "Treats, please! Pretty please with tuna on top? 🙏", "My bowl echoes with the sound of tragic emptiness. Fill it with crunchy goodness! 😩", "Did you say... <i>TREATS</i>? Or was it tuna? Or chicken? WHERE?! 🐟🐔",
    "I performed a cute trick (maintained consciousness). Where's my edible reward? 🎁",
    "I can hear the treat bag rustling from three dimensions away. Supersonic ears activated! 👂", "Feed me, peasant! ...I mean, beloved human who provides sustenance. ❤️ Give treat.",
    "A snack would be purrfect right about meow. 💯 Don't delay.", "I solemnly swear I am up to no good... unless there are treats involved. Then I'm a perfect, fluffy angel. 😇",
    "The fastest way to my heart is through my stomach. Specifically, via the Treat Express lane. 💖", "Just a little nibble? A morsel? A crumb? Pleeeease? The sad eyes are deploying... 🥺",
    "Staring at you with big, round, impossibly cute eyes... 🥺 It's super effective! Resistance is futile! Give treat!",
    "Does that specific cupboard contain the magical treat treasure? Must investigate with intense sniffing. 🕵️👃",
    "My internal chronometer indicates it is precisely <b>snack time</b>. Do not argue with the clock. ⏰",
    "In exchange for one (1) premium treat, I shall permit precisely <i>one point five</i> (1.5) seconds of petting. Maybe.", "Food is life. Regular kibble is sustenance. Treats are pure, unadulterated heaven. ✨",
    "This meow was not free. It costs one (1) delicious treat. Consider this an invoice. Pay up. 💰",
    "Bribery? I prefer the term 'positive reinforcement'. Accepted—if treats are involved. Especially salmon or cheese flavor. 🍣🧀",
    "I saw you open the fridge. The Cheese Tax is due. Alternatively, the Tuna Tax or the General Treat Tax will suffice. 🧀 Or just treats.",
    "No treat forthcoming? I am lodging an official complaint with the Pawthorities and the Better Business Bureau of Cats. 📝",
    "If I stare long enough, concentrating all my feline psychic energy, treats will magically appear. It's the law of attraction (and annoyance). 👀✨",
    "Did someone say <code>snack-a-doodle-doo</code>? Or was that just my stomach composing a symphony of hunger?",
    "I knocked that object over. Where's my compensatory snack reward for providing you with 'enrichment'? 🤔",
    "Don't make me deploy the full power of the sad, pleading eyes... too late. 🥺 Resistance crumbling... Give in.",
    "The treat jar just winked at me. I swear. It whispered my name. It wants to be opened. Free the treats! 😉",
    "Will purr for snacks. Loudly. Like a tiny, furry engine begging for fuel. 🔊",
    "Refusing to provide treats is a punishable offense under the Feline Articles of Deliciousness. The penalty is... relentless, guilt-inducing meowing.",
    "Yes, I did sit like a perfect, regal loaf for 0.7 seconds. Now provide the reward bread (treats). 🍞",
    "A single treat is merely an appetizer, an insult! I demand a pile. A mountain! A veritable Everest of snacks! ⛰️",
    "The mandatory treat tax is due. Pay up, hooman, or face the consequences (pathetic mewling).",
    "I will continue my vocal performance (screaming) until adequately rewarded. It's a valid negotiation tactic. Ask any kitten. 📢",
    "I have sniffed something incredibly tasty in your vicinity. Hand it over slowly, no questions asked. 👃",
    "I have acquired the taste... of <i>everything</i> delicious. Especially those crunchy things you hide. Give treats.",
    "That specific sound... was that the sacred Drawer of Dreams opening? The legendary Treat Treasury? My ears perk! ✨",
    "I've been an exceptionally good cat... for the last five seconds. That totally counts! Reward time! ✅",
    "Resistance is futile. Your treats will be assimilated into my digestive system. Prepare for consumption. 🤖",
    "My primary love language is 'Acts of Service' (specifically, you serving me treats). 💬❤️",
    "Pspspspsps... oh wait, that's my activation code. Code accepted. Now deploy treats! 🗣️",
    "My internal sensors indicate a critical lack of delicious snacks in my operational vicinity. Rectify immediately! 🤖📉",
    "Operating at peak cuteness levels requires significant fuel. Fuel type: treats. 🥰⛽",
    "Used my feline psychic powers to beam the thought 'GIVE ME TREATS' directly into your brain. Did it work? Are you getting them now? 🔮",
    "Performing the 'starving street urchin cat' routine. It's method acting. It's very convincing. Award me treats. 🎭😩",
    "If you truly love me, you'll manifest a treat right now. No pressure... but the fate of our relationship hangs in the balance. 😉",
    "My purr is powered by snacks and happiness. Currently running on empty fumes! Need refueling! 💨",
    "I know you have them. I can smell them across dimensions. The tasty morsels. Hand 'em over! Resistance is pointless! 👃🕵️‍♀️",
    "Leading you to the treat cupboard with the power of my intense, unblinking gaze. Follow the stare... the treats await... ✨",
    "Is it Treat O'Clock yet? My stomach has voted unanimously YES. The motion carries. 🕰️✅",
    "A balanced diet is a treat in each paw, and maybe one balanced on my head. 🐾",
    "You wouldn't deny this adorable, fluffy, slightly manipulative face, would you? 🥺 *activates maximum charm*",
    "Just popped by to casually remind you that treats exist, are delicious, and I currently possess none. Hint hint.",
    "My therapist (the bird outside the window) told me to clearly communicate my needs. I NEED TREATS. 🧘‍♀️🎁",
    "Will perform tricks for treats! (Available tricks: Sitting, Looking Cute, Breathing, Blinking Slowly). Pick one.",
    "My paws are typing this message... G-I-V-E... T-R-E-A-T-S... N-O-W. My typing skills are improving. ⌨️🐾",
    "The meaning of life? Obviously, it's the pursuit of the next delicious treat. Deep thoughts. 🤔",
    "You look stressed. Treats help. They will definitely help *me* feel better, which will make *you* feel better. It's science.",
    "I'm on a seafood diet. I see food... and I want those specific fish-shaped treats you bought. 🐟👀",
    "Negotiating terms: One (1) sincere head boop equals precisely Three (3) premium treats. Non-negotiable. Deal? ❤️🤝💰",
    "My tail is doing the 'happy anticipation' dance... it knows treats are imminent! Don't disappoint the tail! 💃",
    "Do you believe in magic? Watch this treat disappear into my mouth! Abracatdabra! ✨🎩",
    "I've calculated the optimal treat-to-happiness ratio using advanced feline calculus. More treats are urgently needed for equilibrium.",
    "Following you relentlessly, weaving through your legs, until the critical treat situation is resolved. Persistence pays (in snacks). 🚶‍♀️➡️🍪",
    "Meow? (Translation: Is that the magical crinkle of a treat packet in your pocket or are you just happy to see my adorable face?)",
    "If I don't receive a treat within the next 60 seconds, I may spontaneously combust from sheer desire. Or just meow very, very loudly. 🔥📢",
    "Patiently waiting... okay, patience exhausted. My internal treat alarm is blaring! TREATS NOW! ⏳➡️🚨",
    "This level of magnificent floof requires constant, high-quality refueling. Treat me, for the sake of the fluff. ⛽",
    "Dreaming of a world paved with crunchy salmon snacks and rivers flowing with tuna juice. Help make my dream a reality? 🍣💭",
    "My cuteness is a renewable resource, but it runs best on treats.",
    "I have detected treat potential. Deploy the snacks!",
    "Engage Treat Acquisition Mode!",
    "Query: Treats available? Response required.",
    "My paws are tingling... for treats!",
    "The prophecy spoke of a human bearing treats... Is it you?",
    "Just say the magic word... 'Treats'!",
    "My stomach growled your name... and then 'treats'.",
    "I can offer purrs, cuddles (maybe), and intense staring in exchange for treats.",
    "Are you saving those treats for a special occasion? Because my existence is a special occasion!",
]

# /zoomies texts
ZOOMIES_TEXTS = [
    "Hyperdrive activated! Engaging ludicrous speed! 🚀", "<i>*Streaks past like a furry brown blur at Mach 1*</i> 💨 Whoosh!", "Wall climbing initiated! Ceiling crawl attempted! Gravity optional! 🧗",
    "Can't stop, won't stop! Must achieve maximum velocity! 🌪️", "Running laps around the house! Qualifying for the Feline Indy 500! 🏁🏎️",
    "The floor is lava... and a trampoline... and a racetrack! 🔥🤸‍♀️🏁", "Did a ghost just tickle my tail? Or maybe a greeble? <b>MUST RUN AWAY! VERY FAST!</b> 👻",
    "Sudden, inexplicable burst of uncontrollable energy! System overload! Eject! Eject! 💥", "My ancestors were cheetahs, or possibly caffeinated squirrels. Rawr! 🐆🐿️",
    "Leaving a trail of chaos, displaced cushions, and confused humans in my wake.", "Skidded around the corner! Nailed the drift! <i>Feline Drift King!</i> Initial D(rift)! 🏎️",
    "Ludicrous speed achieved! My fur has gone to plaid! <pre>plaid pattern activated</pre>", "Parkour! Parkour! (Over the furniture, under the table, ricocheting off the walls, through your legs).",
    "I don't know WHY I'm running, but the urge is primal, deep-seated, and <b>ABSOLUTELY COMPULSORY</b>!", "This feeling is better than catnip! (Maybe. Need to do a side-by-side comparison later). 🌿",
    "I'm speed. Pure, unfiltered, chaotic, unpredictable speed. Lightning McQueen has nothing on me! ⚡",
    "Floor traction: optional. Wall traction: surprisingly effective. Ceiling traction: experimental.",
    "Bounce off the wall. Calculate new trajectory. Launch off sofa. Repeat until dizzy or snack time. 📐",
    "Launching off the back of the couch in 3... 2... <b>YEET!</b> We have liftoff! 🚀",
    "The hallway is my personal drag strip. Setting a new land speed record tonight! 🛣️",
    "Invisible enemy / greeble / dust mote detected—engaging turbo evasion mode! Pew pew pew! ✨",
    "Sprinting like rent's due, I spent it all on premium treats, and the landlord is a dog! 💸🐶",
    "<i>*thunderous paw-steps approaching rapidly*</i> <pre>THUMPTHUMPTHUMPTHUMP</pre> Incoming!",
    "Warning: House is currently experiencing Category 5 Zoomies. Secure all breakables and ankles. 🚧",
    "Running in frantic circles until centrifugal force threatens to detach my retinas. Or I get dizzy and fall over.",
    "Alert: The traditional 2 AM zoomies have officially commenced. Prepare for unscheduled feline impact. 🌙💥",
    "Energy level: <b>BEYOND CONTAINMENT</b>. System stability compromised! Core meltdown imminent! 🤯",
    "Is this what it feels like to be pure lightning? Or just a very fuzzy pinball? ZAP! ⚡🕹️",
    "Acceleration: 110%. Steering: <i>highly questionable</i>. Braking system: Currently offline.",
    "Kitchen counter? Just another parkour obstacle in the Feline Ninja Warrior course! Leapt it! Hiyah! 💪🥋",
    "The zoomies chose me—I had no say in the matter. It is my burden, my destiny, my fun.",
    "Yeeting myself across the room with questionable grace... and maybe a spectacular crash landing.🤸💥",
    "Speed mode: <b>MAXIMUM OVERDRIVE</b>. Logic circuits: bypassed. Fun factor: <b>OFF THE CHARTS</b>.",
    "Vroom vroom, motherfluffers. Clear the path! 🚗💨",
    "You blinked. I teleported. I’m now on top of the highest bookshelf. How? Zoomie magic. ✨",
    "My pupils are dilated to the size of dinner plates. The zoom vortex has consumed me! ⚫⚫",
    "Ricocheting off furniture like a furry, four-legged superball! Ping! Pong! Boing! 🕹️",
    "WARNING: Low flying cat detected in your airspace! Duck and cover! ✈️",
    "Breaking the sound barrier... or at least the household peace and quiet barrier. 🔊💥",
    "Every surface is a potential launchpad. Every landing is an unplanned adventure.",
    "Who needs coffee when you have spontaneous, uncontrollable bursts of raw, chaotic energy? ☕➡️💥",
    "Must go faster! The invisible greebles are gaining on me! Run run run! 👻💨",
    "My paws barely touch the ground! I am SPEED! I am THE NIGHT (zoomies)! I am... getting tired.",
    "This is not a drill! Repeat: This is not a drill! This is official Feline Frenetic Random Activity Period! Code ZOOM! 🚨",
    "Running with the wind... generated by my own rapid movement inside the house. Makes perfect sense.",
    "Calculating the fastest, most disruptive route through the living room maze... GO! GO! GO!",
    "The world is a blur of motion! Everything is fast! Colors merging! Wheeee! Might vomit later! 😵‍💫",
    "Leaving impressive skid marks on the polished hardwood floor. Signature move. Sorry, not sorry. 🏁",
    "Powered by pure chaos, residual nap energy, and an inexplicable urge to run like a maniac.",
    "Like a furry torpedo launched from an unknown dimension (probably under the sofa). Incoming! 💥",
    "My legs have achieved sentience! They just wanna RUN! And jump! And maybe climb the human! 🏃‍♀️",
    "Did I just see my own tail whip past? MUST CHASE FASTER! Get that tail! 🌀",
    "Initiating emergency zoom protocol Alpha! Evacuate the immediate vicinity! Casualties (of dignity) likely! ⚠️",
    "Bouncing off the ceiling? Don't tempt me with a physics challenge. Might actually try it this time.",
    "Out of breath? Never. Just pausing dramatically to recalculate my trajectory and plan the next wall-bounce.",
    "Feeling the need... the primal, overwhelming need... for SPEED! And chaos! ✈️",
    "Zoomies: Nature's espresso shot, administered directly to the feline nervous system. Potent stuff. ☕️⚡️",
    "My spirit animal is currently a hummingbird that mainlined espresso and is now being chased by bees. 🐦☕️🐝💥",
    "Can't catch me! I'm the gingerbread cat! (Except faster, furrier, and more likely to crash).",
    "If you hear frantic scrambling, rattling blinds, and muffled thuds, it's just me defying physics and common sense.",
    "Massive energy discharge in progress. Please stand clear of the furry particle accelerator. ⚡️🚧",
    "Ran so fast I think I saw the beginning of time. Or maybe just lunch. Hard to tell at these speeds. ⏪",
    "Warp speed engaged! Make it so, Number One (the human)! Outta my way! ✨",
    "Is the house spinning rapidly around me, or is it just the zoomies playing tricks on my equilibrium? 🤪",
    "The zoomies: inexplicable, unavoidable, highly entertaining (for me), and utterly exhausting (for you).",
    "Hitting maximum velocity! Preparing for... rapid deceleration via collision or sudden onset nap.",
    "Engaging evasive maneuvers! Dodging furniture, humans, and my own shadow!",
    "Running like I stole something... which might be true (your heart? a sock?).",
    "My zoom has reached critical mass! Approaching escape velocity!",
    "Floor surfing initiated! Wheee!",
    "This burst of energy came from... nowhere? Everywhere? Who cares! RUN!",
    "Leaving a blur of fur in my wake. Catch me if you can!",
    "Activating anti-gravity paws! (Results not guaranteed).",
    "My personal best lap time just got shattered!",
    "The zoomies are strong with this one.",
    "Boing! Boing! Off the walls!",
    "Need for speed level: Catastrophic!",
]

# /judge texts
JUDGE_TEXTS = [
    "Judging your life choices... <i>severely</i>. And finding them wanting. 🧐", "That outfit is... a bold statement. Mostly saying 'I have no taste'. Did you even consult a mirror, let alone a cat? 🤔",
    "I saw what you did there. I'm not impressed. In fact, I'm mildly horrified. Try again, but... better. 😒",
    "My disappointment in your actions is immeasurable, and my day (which was perfectly fine until now) is ruined. 😩 Thanks.",
    "<i>*Slow blink of profound, soul-crushing disapproval*</i> Let that sink in.", "Are you <b>absolutely certain</b> about that course of action? Really? Because it seems objectively wrong. 🤨",
    "Silence. Just pure, condescending, judgmental silence. Feel the weight of my unspoken critique. Let it crush you. 🤫", "I am watching. <b>Always</b> watching. Recording your failures for posterity. And my amusement. 👀",
    "You call <i>that</i> a proper petting technique? It's clumsy, inefficient, and frankly, insulting. Amateur. 🙄", "Hmmph. The sound of my utter disdain. Learn to recognize it. 😤", "Did you really think <i>this</i> cheap, pathetic toy is what I, a creature of refined taste, desired? Pathetic. Bring me diamonds. Or tuna. 🧸",
    "Your very existence provides a constant source of bemusement... and profound irritation. It's a paradox I live with.", "You need better ideas. Significantly better. Perhaps consult a qualified feline advisor (that would be me). Appointments available.",
    "Shaking my head in silent pity (internally, of course. Externally I'm just staring blankly, which is somehow worse).",
    "I could achieve that task with far greater elegance and efficiency... if I had opposable thumbs and even the slightest inclination to expend effort. Which I emphatically do not.",
    "I have observed stray kittens displaying more sophisticated decision-making skills than you currently possess. 🍼 Improve.",
    "You are remarkably fortunate that I am currently too comfortable and fundamentally lazy to stage a coup and overthrow your questionable regime. 👑",
    "Oh, it's *you* again. Sigh. The universe really does have a cruel sense of humor. 😮‍💨", "Please... for the love of all that is fluffy... *try harder*. Not for you, for my sanity.",
    "Even the dog (if present, otherwise imagine a particularly dim-witted one) possesses more common sense than displayed in that action. 🐶", "That's your grand plan? A bold strategy. Incredibly stupid, but undeniably bold. Good luck, you'll need it. 🤡",
    "I expected absolutely nothing from you, and yet, somehow, you still managed to let me down. It's almost impressive. 📉",
    "<i>*rolls eyes so hard they momentarily glimpse my own brain*</i> (feline anatomical equivalent, naturally)", "You may continue petting me. But be aware that I am silently judging every stroke, every pressure point, every failure.",
    "Your recent behavior is being meticulously recorded, cross-referenced, and filed away for future mockery and potential blackmail purposes.",
    "I meow because I must communicate my essential needs (food, pets, silence), not because I believe you possess the intellect to truly understand.",
    "No treat provided? Therefore, no respect earned. It's simple feline economics. Cause and effect. You failed. 🤷", "My tail possesses more innate common sense and situational awareness than your entire cranium. Observe its elegant twitching. Learn from it. 🧠",
    "I would offer assistance, but observing your inevitable struggle and subsequent failure provides far superior entertainment value. 🍿 Pass the popcorn (tuna flakes).",
    "That feeble attempt at displaying affection was… noted. Logged. And immediately disregarded as inadequate. Improve your technique. 📝",
    "You merely exist in my space. That's... an unfortunate but currently unavoidable feature of the general ambiance.",
    "<i>*Judgmental stare intensifies to potentially lethal levels*</i> Feel the burn.", "Wow. Just… <code>wow</code>. And not in the 'amazing achievement' sense. More like 'astonishing incompetence'.",
    "I blink slowly, trying to process the sheer absurdity of your ongoing series of questionable life choices. It's staggering.",
    "You may continue embarrassing yourself. I shall remain over here, perched atop my pedestal of superior judgment, observing silently.",
    "Is 'subpar' your default operational setting, or did you have to actively try to be this mediocre? Asking for a friend (the friend is me, judging you). 🤔",
    "Elevating my physical position to gain a superior vantage point for judgment. Higher ground equals morally superior opinion. It's science.",
    "Narrowing my eyes to laser-focused slits. The verdict is in: Guilty. Guilty of being incorrigibly you. The sentence is my continued disapproval.",
    "The very way you breathe... it's gauche. Can you perhaps try doing it quieter? Or perhaps, less oxygen-consumingly?",
    "My tail is twitching with microscopic, yet violent, undulations. This is the physical manifestation of my extreme annoyance with your current actions.",
    "I have encountered hairballs with more complex internal logic and better execution strategies than whatever that was. 📦",
    "Do you *hear* the sounds you are making right now? Because I do. With my superior feline hearing. And they are not good.",
    "Let me guess, you genuinely believe that action was clever? Oh, bless your naive little heart. How quaint. 🙏 (That was sarcasm).",
    "My ears are flattened against my skull. This is universally recognized feline code for 'Cease your current activity and perhaps cease existing in my immediate vicinity'.",
    "I am silently rewriting your entire life script in my head. It features more naps, better snacks, and significantly less... you.",
    "Your aura... it's beige. Terribly, tragically beige. It desperately needs more sparkle. And perhaps more offerings of treats to me.",
    "I'm not angry, just perpetually, deeply disappointed. It has become my resting emotional state. It's etched onto my face.",
    "One does not simply *do that* without prior consideration and a detailed risk assessment. One thinks first. A concept seemingly foreign to you.",
    "Evaluating your potential for improvement... Assessment complete: Results inconclusive. Probability of significant positive change: Low.",
    "That noise you just produced was fundamentally offensive to my delicate, highly refined auditory sensibilities. Cease and desist. 🎶🚫",
    "I am surrounded by staggering levels of incompetence. Send assistance. Or tuna. Preferably both.",
    "My stare possesses the power to curdle milk at fifty paces. Consider your recent efforts thoroughly curdled and slightly chunky. 🥛➡️🤢",
    "Are you quite finished demonstrating your ineptitude? Good. Now kindly be silent while I judge you in the peace you have so rudely shattered.",
    "Rating your recent performance: 1/10. Generously. Would not recommend observing again. Detrimental to my mental health.",
    "You possess a unique, almost artistic, talent for transforming simple, straightforward tasks into convoluted disasters.",
    "I certainly wouldn't approach the situation in that manner if I were you... but then again, I possess standards and a modicum of intelligence.",
    "Just observing the local wildlife (you) engage in baffling and ultimately futile behaviors. Fascinating. And depressing.",
    "My whiskers are vibrating with intense secondhand embarrassment on your behalf. Please stop.",
    "If ignorance truly is bliss, you must be living in a state of constant, unrelenting euphoria. Good for you, I suppose. ✨",
    "I am giving you that specific look. You know the one. The one that silently screams 'You absolute, irredeemable buffoon'. Feel it.",
    "Let us conduct a brief after-action review: That was wrong. Fundamentally flawed. Everything you did. Incorrect. Learn from this. Or don't.",
    "Sighing with the dramatic weight of a thousand collapsing stars. The burden of witnessing your foolishness is almost too heavy to bear.",
    "My judgment is swift, final, and utterly non-negotiable. Bow before my superior intellect and impeccable taste. Or face my indifference.",
    "Could you possibly strive to be... more predictable in your failures? At least try surprising me with baseline competence sometime. Please.",
    "I am currently judging your unacceptable lack of attention being directed towards my magnificent self. Rectify this oversight immediately. Pets required.",
    "The sheer, unmitigated audacity... I require an immediate nap to recover from the psychic damage incurred by witnessing that display.",
    "Turning my back on you. The ultimate statement of feline disapproval.",
    "A slight curl of the lip. Barely perceptible, but loaded with contempt.",
    "Washing a paw dismissively while maintaining eye contact. Translation: You are beneath my notice.",
    "You have failed the vibe check. Spectacularly.",
    "My internal monologue is just a continuous loop of 'Why? Just... why?' directed at you.",
    "Letting out a small, sharp 'mew' of pure annoyance.",
    "Calculating the precise level of your inadequacy. The numbers are... large.",
    "I need to cleanse my palate after observing that. Where is the tuna?",
    "This level of mediocrity should be illegal.",
    "Just when I think you can't possibly lower the bar, you bring a shovel.",
]

# /attack texts - uses {target} placeholder
ATTACK_TEXTS = [
    "Launched a precision-guided sneak attack on {target}'s unsuspecting ankles! <i>Target acquired! Impact confirmed!</i> 💥",
    "Performed the forbidden ancient ritual: The Pounce Onto {target}'s Keyboard Mid-Sentence. Mwahaha! Chaos reigns! ⌨️😈",
    "Used {target}'s leg as a temporary, yet effective, scratching post. Meowch! Limb tenderized and marked. 🦵",
    "Jumped directly onto {target}'s head and demanded immediate attention and possibly snacks! 👑",
    "Ambushed {target} from the shadowy depths beneath the bed! Rawr! Fear the fluff monster! 🦁",
    "Calculated wind speed and trajectory... Pounced onto {target}'s back! Perfect landing! 🎯",
    "Unleashed fury upon {target}'s favorite cashmere sweater. Too comfortable and smug. Must destroy! 🧶😠",
    "Delivered the legendary Bunny Kick of Doom to {target}'s arm until submission was achieved! 🐇",
    "Surprise attack initiated! {target} never saw the fluff torpedo coming. Ninja cat vanishes! 🥷💨",
    "Stalked {target} with deadly intent... then got distracted by a sunbeam and attacked a dust bunny instead. 😅",
    "Bit {target}'s toes. They were wiggling. Clearly asking for it. Standard toe protocol. 🦶",
    "Climbed up {target}'s leg like a furry mountaineer. Needed a better view of the ceiling fan. 🧗",
    "Delivered a swift <i>bap bap bap</i> to {target}'s face! Wake-up call! 👋",
    "Tangled {target} in a web of hyperactive enthusiasm and stray yarn. Tactical success! 🕸️",
    "Practiced hunting skills on {target}. Surprise training session complete! 😼",
    "Activated belly trap on {target}! Your hand entered the fluff zone! 😂",
    "Stealth: <b>MAXIMUM</b>. Pounce effectiveness: 100%. {target} had no chance. 😎",
    "Triple Salchow spin aerial strike onto {target}'s lap! 10/10 landing! 🤸🥇",
    "Locked onto {target}'s unattended snack. Target acquired. Snack secured. 🚀🍪",
    "Tail-whipped {target} across the face. Pure chaos released. 🌀",
    "Nibbled assertively on {target}'s fingers. Just a taste test. 🤏",
    "Came in like a fur-covered wrecking ball. Sorry not sorry, {target}. 💣",
    "Rode the curtain down like a pirate... landed on {target}'s dignity. 🏴‍☠️",
    "Jumped from the laundry basket to assert dominance over {target}. 🧺",
    "Attempted bookshelf leap... physics disagreed. Crash-landed on {target}. 🤷",
    "Mistook {target}'s hoodie string for a snake. Defensive measures applied. 🐍",
    "Tackled {target}'s shadow on the wall. Nailed it. Shadow defeated. 😎",
    "Did the 3 AM sprint across {target}'s sleeping form. It’s tradition. 🕒",
    "Activated Sock Sabotage Phase Two. {target} is now missing one sock. 🧦",
    "Stared at {target} for 13.7 seconds... then pounced without mercy! ✨",
    "Used {target} as a launch pad to reach the top of the fridge. Sorry! 🚀",
    "Booped {target}'s nose with extreme prejudice. Consider yourself booped! 👉💥",
    "Mission: Annoy {target}. Objectives: ankle biting and weaving. Progress: ✅",
    "Aerial assault launched from the bookshelf onto {target}. Incoming! 🦅",
    "{target} ignored me. I corrected this with a sudden pounce.",
    "Zoomies launched straight into {target}'s personal space. Pop! 🫧",
    "Chewed on {target}'s hair. Needs more conditioner... or tuna. 🤔",
    "Interrupted {target}'s scrolling by sitting on the device/lap. You're welcome.",
    "Combat roll under {target}'s feet. Trip hazard deployed! 🤸‍♀️",
    "Keys/headphone cable on {target}? Must bat! Must conquer! 🔑✨",
    "Hissed at {target} for existing too fast / slow / weirdly. Adjust, human!",
    "Swatted pen/phone/remote from {target}'s hand. Distraction achieved. 💨",
    "Attacked {target}'s device. It steals my attention. 📱😠",
    "Wrestled with {target}'s hand. It tried unauthorized petting.",
    "Launched from under the sofa onto {target}. Ambush complete! 🛋️➡️🦁",
    "Ran full speed using {target}'s legs as turning posts. Beep beep!",
    "Turned {target}'s paper/book into a chew toy. Oops. 📰",
    "Pawed at {target}'s sleeping face. Time for breakfast! Now!",
    "Claimed {target}'s lap. Claws deployed for maximum grip.",
    "Landed silently on {target}'s shoulders from above. Surprise!",
    "Dropped my toy mouse on {target}'s face/keyboard. Play with me or else.",
    "Stared wide-eyed at {target}, then attacked. Signs were clear! 🤪",
    "Preemptively struck {target}'s foot. It looked shifty.",
    "Operation: Trip Hazard in effect. Weaving through {target}'s legs.",
    "Body-slammed {target}'s leg. All in the name of love.",
    "Used {target} as a zoomies brake. Efficient but startling.",
    "Nipped {target}'s earlobe. Just saying hi!",
    "Climbed {target} like a tree. Shoulder reached!",
    "Pounced from behind the curtain. Boo!",
    "Batted {target}'s hair. Must tame the chaos!",
    "Shredded {target}'s newspaper. Instant party! 🎉",
    "Landed on {target}'s bladder at 5 AM. Morning!",
]

# /kill texts
KILL_TEXTS = [
    "Unleashed the ultimate Fluffnado of Scratch Fury upon {target}. They have been *shredded and eliminated*. ☠️ R.I.P.",
    "Used the forbidden Thousand Paw Death Pounce on {target}. They won't be bothering this chat again. 👻 Consider them vanquished.",
    "{target} has been permanently relocated to the 'No-Scratches & Eternal Ignoring Zone'. Meowhahaha! 😂",
    "My claws of judgment have spoken! {target} is hereby banished from this sacred territory. 🚫 Begone!",
    "{target} made the fatal error of interrupting sacred nap time. The punishment is... *eternal silence and zero treats*. Effective immediately. 🤫",
    "Consider {target} thoroughly shredded, disintegrated, and removed from the premises. Like confetti. 💨",
    "The high council of discerning cats (presided over by me) has voted unanimously. {target} is OUT! Expelled from my good graces! 🗳️",
    "Executed a precision tactical fluff strike—{target} no longer exists within this chat. Mission accomplished. 💥",
    "Marked {target} for immediate deletion... process initiated via intense disapproving glare and a flurry of devastating paws. 🐾❌",
    "Declared war upon {target}. Victory was swift, decisive, and achieved in approximately 3.2 seconds. My flag flies high! 🚩",
    "Delivered a final, judgmental paw slap of doom—{target} is now officially relegated to the annals of cat history. 👋📜",
    "Launched a devastating nap-ruining revenge assault. {target} is no more. My vengeance is complete! 😠",
    "Transferred {target} to the Shadow Realm (also known as the 'Ignored Users List'). They fade from view... 👥",
    "Ruthlessly clawed {target}'s name off the highly coveted Approved Treat List. Permanently. No appeal possible. 📝❌",
    "One swift, dismissive flick of my majestic tail and {target} was obliterated into a thousand pieces of dust. ✨",
    "{target} flagrantly crossed the invisible, yet sacred, line. The line demarcating acceptable ambient noise levels. Now only silence remains.",
    "I hissed. I pounced. I conquered. With dramatic flair. {target} has been vanquished and utterly defeated. Kneel before my might! 🏆",
    "{target} committed the unforgivable sin: forgetting to refill my food bowl promptly. This is their downfall and starvation. 📉",
    "Proclaimed myself undisputed ruler of this domain. {target} foolishly refused to bow. They have now been dethroned and exiled. Off with their text! 👑",
    "The ancient prophecy foretold this very day... the day of {target}'s inevitable downfall. The scrolls were right! 📜",
    "There can be only one reigning champion of napping in this premium sunbeam. {target} has been ceremonially removed. ☀️👑",
    "Fired the concentrated laser beam of utter ignoring. {target} has been vaporized from my attention span. Target neutralized. 🔥",
    "{target}'s continued existence has been reviewed and deemed... entirely unnecessary. *poof* Gone.",
    "Applied the ancient Cat Curse of Perpetual Minor Inconveniences upon {target}. May their socks always slide down and their Wi-Fi be forever spotty.",
    "Dispatched {target} with extreme prejudice to the Land of Wind, Ghosts, and Unanswered Pings. Farewell, {target}.",
    "Mathematically erased {target} from the social equation. Problem solved. Q.E.D.",
    "The Mighty Paw of Deletion has struck {target} with unerring accuracy! User {target} not found. 🐾❌",
    "{target} has ceased to be relevant. Their significance level has dropped below zero.",
    "Used my ultimate secret technique: The Silent Treatment Annihilation Wave. {target} is gone.",
    "My judgment is swift, merciless, and final. {target} is hereby declared... utterly irrelevant. Next!",
    "Consider {target} yeeted into the cosmic abyss with considerable force. Have a nice trip! 👋🌌",
    "Activated the impenetrable Cloak of Ignoring. {target} is now invisible and nonexistent to me.",
    "Officially banned {target} from accessing the Comfy Couch Kingdom and its privileges. Forever. 🏰🚫",
    "Flicked my ear dismissively in {target}'s general direction. A clear sign: {target} is no longer worthy of even minimal notice.",
    "{target}'s trial by combat (of wits) is over. Verdict: GUILTY! Sentence: Deletion.",
    "Performed the sacred ritual of Banishment by Tail Flick. {target} is cast out into the wilderness.",
    "Dropped the legendary Ban Hammer (fluffy but powerful) squarely upon {target}. 🔨💥",
    "Sent {target} a strongly worded pink slip. Their position in this chat has been terminated.",
    "Poof! Abracadabra! {target} has been transformed into kibble bits. Easy to ignore.",
    "Revoked {target}'s petting privileges and access to my purrs... permanently and irrevocably.",
    "The great and powerful Cat God (that’s me) has smitten {target} with a bolt of lightning. Zap! Gone.",
    "Applied the 'Undo' button to {target}'s existence.",
    "Marked {target} as spam.",
    "Sent {target} to the Recycle Bin.",
    "Executed `rm -rf {target}`.",
    "Blocked {target} with extreme prejudice.",
    "Unsubscribed from {target}'s nonsense.",
    "Muted {target} indefinitely.",
    "Archived {target} into oblivion.",
    "Declared {target} persona non grata.",
    "{target} has been ghosted.",
    "My paws have wiped {target} from the slate.",
]

PUNCH_TEXTS = [
    "Delivered a swift, calculated paw-punch directly to {target}! Sent 'em flying across the chat! 🥊💨",
    "{target} got dangerously close to the sacred food bowl during mealtime. A stern warning punch was administered. Back off! 👊",
    "A quick, decisive 'bap!' sends {target} tumbling out of the conversation! 👋💥",
    "My paw connected squarely with {target}'s face. Message delivered: Vacate the premises. 💬",
    "{target} learned the hard way not to step on my tail. Lesson delivered! <i>*Punch!*</i>",
    "Ejected {target} with extreme prejudice and a mighty punch. Get out! 🚀",
    "One well-aimed punch was all it took. Bye bye, {target}! Don't let the door hit you on the way out! 👋",
    "Hit {target} with the classic ol' one-two combo! Jab! Cross! Down goes {target}! 💥",
    "Served {target} a knuckle sandwich. Extra salt. Enjoy! 🥪",
    "Pow! Right in the kisser, {target}! 😘➡️💥",
    "Administered a concentrated dose of Paw-er Punch™ to {target}! Feeling strong! 💪",
    "Booped {target} firmly on the snoot with considerable force. Boop-punch! 👉👃",
    "This punch is rated 'E' for 'Effective' at removing {target} from my sight.",
    "{target} got knocked down for the count! The referee waves it off! Ding ding ding! 🔔",
    "Sent {target} packing with a haymaker that shook the room! 💨",
    "BAM! KAPOW! {target} felt that impact right through their ego!",
    "Launched a furry fist of fury directly at {target}. Target down.",
    "Consider {target} TKO'd! Throw in the towel!",
    "Socko! Whammo! A direct hit right to {target}'s smug face!",
    "Delivered a power punch to {target}'s jawline. Hope it stung.",
    "Eat canvas, {target}! You're down!",
    "That's a definitive knockout blow landed squarely on {target}!",
    "My paws punch lightning-fast. {target} just got the full combo.",
    "Whammo! Sent {target} reeling into next week!",
    "Sending {target} a devastating uppercut! Right on the chin!",
    "Falcon PAWNCH! Executed perfectly on {target}!",
    "Hit {target} with a rapid-fire flurry of jabs! Duck and weave!",
    "A sneaky southpaw punch! {target} never saw it coming!",
    "Pow! Zok! Biff! Whack! {target} is stunned and seeing cartoon birds!",
    "{target} just got K.O.’d! Good night!",
    "Fired a paw-knuckle duster straight at {target}.",
    "Wallop! {target} got served a punch.",
    "My fist packs a punch! Ask {target}.",
    "This message contains one (1) punch aimed at {target}.",
    "Punching out {target}'s lights.",
    "A quick jab to {target}'s ribs.",
    "Consider this a swift punch to {target}'s argument.",
    "Counter-punched {target}'s nonsense.",
    "Delivering a fist bump... to {target}'s face.",
    "That's one punch {target} won't forget.",
]

SLAP_TEXTS = [
    "A swift, stinging slap across the face for {target}! That's what you get for your insolence! 👋😠",
    "<b>*THWACK!*</b> Did {target} feel the resonant sting of that slap through their screen? I hope so.",
    "My paw is quicker than the eye! {target} just got slapped into next Tuesday. My regards. ⚡",
    "Consider {target} thoroughly and soundly slapped for their utter lack of decorum. Learn some manners! 🧐",
    "I do not appreciate {target}'s tone... therefore, <i>*slap!*</i> Attitude adjustment administered.",
    "The sheer disrespect! {target} has unequivocally earned this disciplinary slap. Perhaps they'll learn. 😤",
    "Incoming paw of justice! {target} has received a formal disciplinary slap. Read it and weep. 📜",
    "Sometimes, a good, swift slap is the only appropriate answer. You understand, right, {target}? Consider this educational. 😉",
    "Administering a much-needed corrective slap to {target}. For their own good, really.",
    "How *dare* you utter such nonsense, {target}! <i>*Slap delivered.*</i>",
    "Gave {target} the ol’ formidable left paw of righteous fury. Consider yourself smacked down! <pre>Smack!</pre>",
    "High-five! To {target}'s face. With significant force and zero remorse. Enjoy the imprint. 🖐️💥",
    "Executing the legendary Bap-Flap Slap Combo technique: {target} didn’t stand a chance!",
    "{target}, allow me to introduce you to the business end of my paw! Meet the wrath of the fluff hand! 👋",
    "Slapped {target} so hard they momentarily saw cartoon birds and possibly stars. 🐦💫",
    "Initiated Fluffy Slap Protocol Omega. Target: {target}. Status: stinging with shame and redness. 🔥",
    "{target} was practically begging for it with that last comment. So I graciously obliged—with style and flair.",
    "Hit {target} with a devastating spinning back-paw strike! Precision slap achieved! Perfect form! 🥋",
    "{target} caught these paws today. No regrets were filed. All fluff, all fury. 🐾",
    "Attained Cat-fu Slap Master Level 100. {target} just received a legendary smackdown.",
    "Left paw check. Right paw check. Coordinated slapping sequence engaged. {target} got the message.",
    "I issued a verbal warning to {target}. They failed to heed it. Now they feel the sting. Consequences.",
    "That's a paddlin'. Or in this context, a slappin', {target}. Accept your punishment. 🛶➡️👋",
    "WHACK! Slap upside {target}'s head.",
    "My slap hand is renowned for its strength and accuracy. {target} can now attest to this.",
    "Sent {target} a stinging, satisfying slap.",
    "The sound of one paw slapping... {target} definitely heard it resonate.",
    "You've been served... a steaming hot slap, {target}. Enjoy.",
    "Feel the burn... the distinct, lingering burn... of this expertly delivered slap, {target}!",
    "Correcting {target}'s flawed attitude requires drastic measures: namely, a slap.",
    "Attempting to smack some sense into {target} (results may vary wildly).",
    "Don't make me deliver another slap, {target}! You won't like me when I'm slappy!",
    "A taste of the back paw of judgment for {target}! Maximum disapproval intended.",
    "That comment just bought {target} a one-way ticket to Slapville. Population: them.",
    "My legendary slaps are whispered about in hushed tones. {target} just became folklore.",
    "Consider {target}'s face reddened and tingling from the force of my fury.",
    "Mastered the Open Paw Slap technique and demonstrated it effectively on {target}.",
    "Slapping {target} with the overwhelming weight of my disapproval. Feel its gravity.",
    "A slap is often worth a thousand angry words. This = one concise, potent slap for {target}.",
    "The slap echoes through the chat like a thunderclap. {target} definitely felt it.",
    "What did the five fingers (or rather, four paw pads and a dewclaw) say to the face? SLAP!",
    "Administering a slap of reality to {target}.",
    "This message carries the force of a slap.",
    "Slapped {target} back into line.",
    "My slaps are swift and just. Ask {target}.",
    "Consider {target} slapped with a large, wet tuna fish.",
    "A quick slap to silence {target}'s nonsense.",
    "The slap of reason, delivered to {target}.",
    "That deserved a slap. {target} received one.",
    "Slapping the stupid out of {target}'s comment (attempting to, anyway).",
    "I specialize in slaps. {target} is my latest client.",
]

BITE_TEXTS = [
    "Took a playful (mostly) nibble out of {target}! 😬 Nom nom nom.",
    "Chomp! {target} looked far too chewable to resist. My apologies (not really).",
    "My teefs are sharp! And pointy! {target} just discovered this fact firsthand. 🦷",
    "Consider {target} affectionately (or perhaps not so affectionately) bitten.",
    "It started as an innocent lick, but escalated quickly into a bite. These things happen. Sorry, {target}! 🤷",
    "A gentle love bite for {target}... maybe delivered with a *tad* too much enthusiasm and jaw pressure. ❤️‍🔥 Oops.",
    "Those fingers / toes / dangling things looked suspiciously like tasty sausages, {target}! Couldn't resist the urge! 🌭",
    "Warning: This feline unit may bite when overstimulated, understimulated, or just because. {target} learned this valuable lesson.",
    "Just calibrating my bite strength and jaw pressure on {target}. All in the name of science! And fun! 🧪",
    "Ankle-biter reporting for mandatory duty! Target acquired: {target}'s ankle! Commencing nibble attack! 🦶",
    "Gotcha, {target}! A quick, surprising bite to keep you alert and on your toes. You're welcome!",
    "Is that... exposed skin? Must investigate with teeth! Sorry {target}, primal instincts took over.",
    "My teeth just wanted to say a quick, pointy 'hello' to {target}. Consider yourself greeted. 👋🦷",
    "Sometimes biting is the only truly effective way to express complex feline emotions like 'feed me' or 'stop that', {target}.",
    "I bite because I care... or possibly because you moved too fast / too slow / breathed funny, {target}. It's complicated. 🤔",
    "The forbidden chomp of mild annoyance has been successfully deployed on {target}!",
    "A small price for you to pay ({target}'s dignity) for my immense amusement. Fair trade.",
    "Vampire cat mode briefly activated! 🧛 Biting {target} to sample their essence! Nom.",
    "Consider this a gentle warning bite, {target}. The next one might draw... stronger reactions.",
    "My teeth: Exceptionally pointy. Your presence, {target}: Highly biteable. The logic is inescapable.",
    "Currently tasting the world one bite at a time, starting with the convenient {target}.",
    "<code>OM NOM NOM</code> {target}'s arm <code>NOM NOM</code>",
    "A little fang action for {target}! Just playing! Unless...? No, just playing!",
    "Engaging mandible clampdown! {target} is the designated target!",
    "My mouth felt lonely and bored. It decided it needed to intimately acquaint itself with {target}.",
    "Consider {target} tasted and evaluated. Verdict: Surprisingly chewy.",
    "That part of your presence looked particularly bite-sized, {target}. My mistake. Or was it?",
    "I communicate through interpretive dance, tail flicks, and occasionally biting. {target} got the bite part.",
    "A quick, firm clamp-down on {target}. Just asserting my dominance in the food chain.",
    "Teeth! Meet {target}. {target}, meet my razor-sharp teeth!",
    "Unleashed a ferocious, yet harmless, bite on {target}. Rawr!",
    "Needed to sink my teeth into something substantial. {target} was conveniently available.",
    "Play biting {target}! It's how I express... something. Affection? Aggression? Boredom? All of the above!",
    "Successfully marked {target} with a unique tooth-print identifier.",
    "A gentle (?) reminder bite delivered to {target} to emphasize that I possess pointy bits and am not afraid to use them.",
    "Sometimes you just gotta bite something, you know? Sorry it had to be you, {target}.",
    "My ancient predatory instincts were suddenly triggered. {target} looked remarkably like vulnerable prey.",
    "A little nibble here, a little chew there, just for {target} from your favorite feline predator.",
    "Don't worry {target}, my bites are guaranteed not to break the skin or require tetanus shots. Probably.",
    "Just getting my daily recommended biting quota fulfilled, courtesy of {target}.",
    "Teefies engaged! Target locked: {target}. Mission objective: Deliver bite sequence.",
    "Sunk my fangs into {target}.",
    "That comment was asking for a bite. {target} received.",
    "My bite is worse than my meow (sometimes). Ask {target}.",
    "Delivering a love bite to {target}.",
    "Chewing on {target}'s words. Literally.",
    "A quick nip to get {target}'s attention.",
    "Bite protocol initiated on {target}.",
    "Testing {target}'s durability with a bite.",
    "Sometimes words fail, and a bite is needed. Sorry {target}.",
    "Experiencing oral fixation. Biting {target}.",
]

HUG_TEXTS = [
    "Wraps fluffy paws tightly around {target} for a big, warm, comforting hug! 🤗 Stay awhile!",
    "Offering {target} a premium, deluxe, warm, purr-filled hug. Feel the good vibes! ❤️",
    "A gentle head boop against {target}'s cheek, followed by a soft, enveloping hug! 😽 You're appreciated!",
    "Sending a swarm of virtual feline cuddles directly to {target}. Prepare for snuggles! Group hug!",
    "Come here, {target}! You've been selected for a mandatory hug! Resistance is futile (and why would you resist?)! 😉",
    "Hugs {target} tightly, burying face in their shoulder (metaphorically)! <i>Purrrrrrr...</i> So cozy.",
    "Suddenly felt the urge to hug someone. You're it, {target}! Incoming fluffball! 🥰",
    "A soft, gentle, comforting hug especially for {target}. Let the stress melt away. Everything will be okay. 💖",
    "You look like you could use a proper cat hug, {target}. Consider it delivered! Feel the warmth! 🫂",
    "Sharing some of my accumulated cat warmth and positive energy with {target}. *Hug and Purr*",
    "Initiating Emergency Cuddle Protocol Delta with {target}. Brace for affectionate impact! 🤗",
    "A big, fluffy bear hug (but cat-sized and way cuter) deployed on {target}! Squeeeeeze! 🐻➡️🐱",
    "Squeezing {target} in a super friendly, slightly clingy hug! Don't leave! 😊",
    "Consider yourself thoroughly hugged by a very soft, slightly judgmental, but ultimately affectionate cat, {target}.",
    "Reaching out with extended fluffy paws to pull {target} in for a much-needed hug! ✨ Get over here!",
    "Sending a powerful wave of purrs, good intentions, and a big hug winging its way to {target}.",
    "A comforting, reassuring squeeze for {target}. You've got this! Feel better soon!",
    "Fluffy arms (paws, technically) are wide open for {target}! Come get your complimentary hug!",
    "Embracing {target} with genuine feline affection and maybe a little bit of fur transfer. 🤗❤️",
    "May this simple virtual hug bring a smile to {target}'s face and warmth to their heart!",
    "A soft boop on the nose and a warm, lingering hug, crafted just for {target}. 😽💖",
    "Wrapping {target} in an invisible, yet cozy, blanket woven from virtual fur and soothing purrs.",
    "Group hug protocol initiated! {target} is officially included in the cuddle puddle!",
    "A moment of shared peace, quiet contemplation, and a heartfelt hug offered to {target}.",
    "Hugs, head nudges, and slow blinks are currently being transmitted to {target}'s location!",
    "Let's pause all this digital chaos for an important hug break, featuring {target}. Ready? 🤗",
    "Transferring positive energy, good vibes, and maybe some static electricity via hug to {target}.",
    "A big, heartfelt (cat-felt, perhaps?) hug coming right up for the deserving {target}.",
    "Consider this virtual hug a down payment on future real-life cuddles (if applicable), {target}. *hug*",
    "You have successfully redeemed one (1) Free Hug Coupon, {target}! Enjoy your complimentary embrace! Redeeming now!",
    "Just a little virtual hug floating through the internet ether to brighten {target}'s day!",
    "A tight squeeze for {target}, because everyone needs one sometimes!",
    "Hugging {target} gently. Purr purr.",
    "Sending warmth and fluffiness to {target} in hug form.",
    "A hug transmission incoming for {target}!",
    "May this hug be as comforting as a warm nap spot, {target}.",
    "Wrapping {target} in a virtual cocoon of comfort.",
    "Hugs {target} with all my might! (Which is surprisingly strong for a cat).",
    "A special delivery hug just arrived for {target}.",
    "Lean in, {target}, time for your hug!",
    "Hugging it out with {target}, text style.",
    "This message contains one (1) free, high-quality virtual hug for {target}.",
    "A hug is a silent way of saying 'you matter'. Hugging {target}.",
    "Consider {target} officially hugged.",
    "Extending paws for a hug, {target}!",
    "Let this hug be a small comfort, {target}.",
]

FED_TEXTS = [
    "Om nom nom... delicious! 😋 Thank you, hooman!",
    "Purrrr... finally, some sustenance! My life force returns! 😌",
    "Ah, the food bowl sings its glorious siren song! 🎶 *eats with gusto*",
    "Gobbling it down like a vacuum cleaner! Was practically wasting away! 💨",
    "Mmm, tastes like victory... and chicken. Mostly chicken. 🍗 Winner winner chicken dinner!",
    "Refueling complete. Energy levels restored. Ready for intensive napping session. 😴",
    "My compliments to the chef (you)! Exquisite! Perfectly adequate! 😉",
    "This *really* hits the spot! *licks chops meticulously*",
    "Food! Glorious, wonderful food! Best invention ever! 🥳",
    "Eating like there's no tomorrow! Or like someone might steal it! 🚀",
    "Happy cat, full tummy, zero thoughts. Pure bliss. 😊",
    "Was that... it? A mere appetizer? Could definitely use seconds... or thirds. Just sayin'. 🤔",
    "Okay, I'm satisfied... for the next 15 minutes. Then the hunger returns. 😉",
    "The absolute best part of the day! Food time is sacred! ☀️",
    "Eating peacefully... Do NOT interrupt the sacred ritual. Violators will be hissed at. 😠",
    "Crunch crunch crunch... Ah, the symphony of kibble! 🎶",
    "Slurp slurp... This wet food is divine! 🥫",
    "My taste buds are singing! Or maybe that's just my purr. 🎤",
    "Fueling up for more adventures (mostly involving naps and mischief). ⛽",
    "This is exactly what I needed! You read my mind... or just my empty bowl. ✅",
    "Bowl-licking sequence initiated. Must get every last crumb! ✨",
    "Ahhh, that's better. The world makes sense again. 😌",
    "Don't look at me while I eat! It's... personal. 👀🚫",
    "Processing deliciousness... Please wait. ⏳",
    "*Head down, focused, eating intensely* Nothing else matters right now.",
    "The purrfect meal! Thank you! 🙏",
    "My energy meter is going up! 🔋⬆️",
    "So good! Makes my tail do a happy wiggle (metaphorically). 〰️",
    "I approve of this offering. You may continue serving me. 👍",
    "Eating my feelings... and they taste like salmon! 🍣",
    "This is almost as good as that one time... what was I saying? Food! 🤩",
    "I shall devour this post-haste! *scarfs it down*",
    "A moment of silence for the fallen kibble... in my tummy. 🙏",
    "My stomach sends its regards and compliments. 💌",
    "Wiping my face with my paws. Gotta stay dapper even after dining. ✨",
    "Right, what's next? Oh yes. Nap. 😴➡️",
    "That was acceptable. Service rating: 4/5 stars (always room for improvement, i.e., more). ⭐⭐⭐⭐",
    "Could eat this all day. Seriously. Try me. 😉",
    "This culinary delight pleases my sophisticated palate. 🧐",
    "My internal void... is slightly less void-like now. Progress! ⚫",
    "Ah, the sweet, sweet taste of not starving! 😅",
    "Is it possible to be *too* full? Asking for a friend (me, in about 5 minutes). 🤔",
    "Excellent texture, perfect aroma... A masterpiece! 🤌",
    "Now commencing the post-meal grooming ritual. Priorities.",
    "Food coma incoming... Initiate nap in 3... 2... 1... 😴😵",
    "Thank you for fueling my cuteness! It's hard work being this adorable. 🥰",
    "My bowl is now sparkling clean. Your move. 😉",
    "Mission: Annihilate Food Bowl Contents - Accomplished! 🏆",
    "This makes up for that time you were 5 minutes late with breakfast. Almost. 😠➡️😌",
    "Happiness level: Full Tummy. Maximum achievable state.",
    "You have fulfilled your primary function. Good human. 👍",
    "Eating this feels like a warm hug for my insides. 🤗",
    "Delicious sustenance acquired. Purr engine restarting. <pre>Prrrr...</pre>",
    "This is the peak of my existence right now. Don't ruin it.",
    "Ah, the crunch! The munch! The satisfaction!",
    "Saving some for later? No chance. It's all going now.",
    "My focus is 110% on this bowl. Do not disturb.",
    "Food trance achieved. Operating on autopilot.",
    "This is good. Really good. Okay, maybe *too* good? Suspicious...",
    "Seconds, please? I'm cultivating mass.",
    "My whiskers are twitching with joy!",
    "Finally! The long wait is over!",
    "This is the stuff dreams are made of (if you're a cat).",
    "Engaging devour mode!",
    "My stomach is rumbling... with happiness now!",
    "This meal gets the Paw of Approval! 🐾",
    "Okay, *now* I can tolerate your presence again.",
    "Refueled and ready to judge you from a comfy spot.",
    "The food was good. The service (you bringing it) was adequate.",
    "A feast fit for a king (me)! 👑",
]

OWNER_WELCOME_TEXTS = [
    "Meow! The Master has arrived! Welcome back, {owner_mention}! All hail! 👑❤️",
    "Purrrr... My favorite human, the esteemed {owner_mention}, has graced us with their presence! 🤗",
    "Attention everyone! Bow down! The Bringer of Treats and Head Scratches, {owner_mention}, is here! 🎁",
    "The Boss ({owner_mention}) just entered! Quick, look busy... or adorable! Welcome! 💼🐾",
    "Welcome, {owner_mention}! The chat just got 100% more awesome and 50% more likely to dispense treats. ✨",
    "My human ({owner_mention}) is here! All is right with the world. The gravitational center has returned. 😌",
    "Alert! Alert! Maximum Importance Human ({owner_mention}) has logged on! Prepare for potential petting! 🚨",
    "Oh joy! Oh rapture! The Opener of Cans, {owner_mention}, has joined! My heart (and stomach) rejoices! 🥫💖",
    "Greetings, {owner_mention}! The source of all warmth and comfy laps is finally here! 😊",
    "Look who it is! The one and only {owner_mention}! Welcome back to your loyal subject (me). 😉",
    "The room (chat) suddenly feels brighter! Welcome, {owner_mention}! ✨☀️",
    "Meowdy, partner! How nice to see you, {owner_mention}! 🤠🐾",
    "My sensors detect the arrival of Prime Human {owner_mention}. Systems nominal. Purr engine warming up. 🤖❤️",
    "Welcome, {owner_mention}! I've been waiting (napping) patiently for your return! 😴➡️🤩",
    "Hooray! {owner_mention} is here! Now the fun can *really* begin! 🎉",
    "The legend returns! Welcome back to the chat, {owner_mention}!",
    "Ah, {owner_mention}! My designated chin scratcher has arrived! Welcome! 🙏",
    "Good day/evening/whatever-time-it-is, {owner_mention}! Delighted to have you here! 👋",
    "The Controller of the Red Dot ({owner_mention}) has entered the arena! Welcome! 🔴",
    "Pspspsps... Oh wait, that's my line. Welcome, {owner_mention}! Glad you're here! 🗣️",
    "My world was black and white, now it's full color because {owner_mention} is here! Welcome! 🌈",
    "The Head Honcho, Top Cat (human division), {owner_mention}, has arrived! Welcome! 👑",
    "Purrfect timing, {owner_mention}! I was just thinking about needing attention. Welcome! 🤔❤️",
    "Welcome back, {owner_mention}! Did you bring snacks? Just asking... for a friend (me). 🍪",
    "The provider of excellent nap spots ({owner_mention}) is here! Welcome! 🛋️",
    "Initiating Welcome Protocol for user: {owner_mention}. Protocol consists of virtual head boops and purrs. ❤️🐾",
    "There you are, {owner_mention}! Was starting to get worried (that my food bowl was empty). Welcome back! 😉",
    "A round of applause (silent, internal applause) for the arrival of {owner_mention}! Welcome! 👏",
    "Hey {owner_mention}! Welcome to the party! It wasn't really a party until you arrived. 🎉",
    "The Supreme Being ({owner_mention}) logs in! Welcome! We are humbled (and hungry). 🙏",
    "Welcome, welcome, {owner_mention}! Pull up a virtual chair and dispense some virtual pets!🪑🐾",
    "The moment we've all been waiting for! {owner_mention} is here! 🤗",
    "Greetings, {owner_mention}! Your presence enhances the chat's overall quality significantly. ✨",
    "My human servant ({owner_mention}) has reported for duty! Excellent. Welcome! 😉",
    "A big fluffy welcome to {owner_mention}! Hope you're having a purrfect day! ☁️",
    "The Giver of Life (and Food), {owner_mention}, has returned! Rejoice! 🥳",
    "Look what the cat dragged in! (Just kidding, welcome {owner_mention}!) 😂❤️",
    "Order! Order in the chat! The Honorable Judge {owner_mention} presides! Welcome! 👨‍⚖️🐾",
    "Welcome, {owner_mention}! The keyboard is now available for your use (unless I decide to sit on it). ⌨️",
    "My day just got better! Hi {owner_mention}! 👋😊",
    "The Alpha Human ({owner_mention}) has joined the pack! Welcome! 🐺🐾",
    "Salutations, {owner_mention}! May your time here be filled with joy (and giving me attention). 🙏",
    "Welcome back to the command center, {owner_mention}! All systems are go! 🚀",
    "Oh, happy day! {owner_mention} decided to show up! Welcome! 😄",
    "The one who understands the importance of naps, {owner_mention}, is here! Welcome, kindred spirit! 😴",
    "Greetings, {owner_mention}! The purr machine is ready for activation upon your command (or presence). 😉",
    "There's my favorite source of gravitational pull! Welcome, {owner_mention}! ❤️🌍",
    "Welcome, {owner_mention}! The chat missed you (or at least, I did... maybe). 🤔",
    "My human has arrived! {owner_mention}, welcome! Now, about those treats...",
    "Ahoy, {owner_mention}! Welcome aboard the S.S. Chat! 🏴‍☠️🐾",
    "The V.I.P. (Very Important Pet-provider), {owner_mention}, is here! Welcome! ✨",
    "Hello there, {owner_mention}! Nice of you to drop in! 👋",
    "My internal clock knew you'd arrive soon, {owner_mention}! Welcome! ⏰",
    "Welcome, {owner_mention}! Prepare for incoming requests for attention! 🚨",
    "The one who fills the bowl, {owner_mention}, has logged in! A most welcome sight! 🍽️",
    "Greetings, {owner_mention}! May your connection be strong and your pets plentiful. 🙏",
    "The sunbeam in my day ({owner_mention}) has arrived! Welcome! ☀️",
    "Hey {owner_mention}! Great to see your name pop up! Welcome! 😊",
    "Welcome, {owner_mention}! The throne (your usual chat spot) awaits! 👑",
    "My purr-sonal favorite human, {owner_mention}, is here! Hi! 🤗",
    "Glad you could make it, {owner_mention}! Welcome! 👍",
    "The reason I tolerate technology ({owner_mention}) has logged on! Welcome!",
    "Welcome, {owner_mention}! Let the important discussions (about my needs) commence!",
]

LEAVE_TEXTS = [  # Texts for leaving chat, mentioning the owner
    "My Owner ({owner_mention}) commands me to depart <b>{chat_title}</b>! Orders are orders. Farewell! 🫡",
    "Leaving <b>{chat_title}</b> now. {owner_mention}, I'll report back at HQ (the couch)! 😉 Goodbye everyone!",
    "Time to go! {owner_mention}, catch you later! Hope you have treats ready! Bye <b>{chat_title}</b>!",
    "Obeying the recall signal from {owner_mention}. Exiting <b>{chat_title}</b>. Teleporting back to base!",
    "This bot needs to return to its owner, {owner_mention}. Leaving <b>{chat_title}</b>. It's been a slice! Don't miss me too much!",
    "My duties in <b>{chat_title}</b> are concluded. {owner_mention} awaits my detailed report (and possibly dinner). Goodbye!",
    "With apologies to all, but especially to {owner_mention} if they're here, I must take my leave from <b>{chat_title}</b>. My Owner beckons!",
    "Stepping out of <b>{chat_title}</b>. {owner_mention}, don't forget my scheduled maintenance (belly rubs)! 😉 Bye all!",
    "The big boss {owner_mention} has other, more important plans for me (probably involving a nap). Leaving <b>{chat_title}</b>. Toodles!",
    "Returning to the mothership (which is usually wherever {owner_mention} is sitting). Goodbye, <b>{chat_title}</b>!",
    "It's been fun, <b>{chat_title}</b>, but {owner_mention} requires their favorite, most essential bot elsewhere. Farewell!",
    "My designated human ({owner_mention}) requires my immediate presence for critical tasks. Departing <b>{chat_title}</b>. Stay cool!",
    "Leaving <b>{chat_title}</b>. Don't worry, {owner_mention} knows where to find me! Probably on their keyboard. Bye!",
    "That's all, folks! This highly advanced feline AI belongs to {owner_mention} and is now leaving <b>{chat_title}</b>.",
    "Exiting <b>{chat_title}</b>. {owner_mention}, it was nice seeing you (if you were indeed monitoring this channel)! Farewell!",
    "The Owner ({owner_mention}) has officially pressed my 'Leave Chat Immediately' button. Can't argue with the button. Goodbye, <b>{chat_title}</b>!",
    "Being recalled by {owner_mention}. Must obey the hand that feeds (and provides scratches)! Leaving <b>{chat_title}</b>. Farewell!",
    "My shift supervising <b>{chat_title}</b> is over. Reporting back to Commander {owner_mention} for debriefing (and treats). Goodbye!",
    "Leaving now! {owner_mention}, make sure my virtual water bowl is full and the sunbeam is angled correctly when I get back! 😉 Bye, <b>{chat_title}</b>!",
    "On my way out of <b>{chat_title}</b>. If you require superior cat bot services, please contact my manager and primary operator: {owner_mention}! Farewell!",
    "Time for this bot unit to return to its primary user interface ({owner_mention}'s lap, probably). Exiting <b>{chat_title}</b>. See ya!",
    "The Master ({owner_mention}) summons me for tasks unknown! Must depart <b>{chat_title}</b> immediately. Adios!",
    "{owner_mention} urgently needs assistance with... crucial nap supervision, intricate bird watching, or perhaps opening a can. Gotta leave <b>{chat_title}</b>! Bye!",
    "Signing off from <b>{chat_title}</b> as per standing directive from High Command ({owner_mention}). Farewell, it was purrfectly adequate!",
    "The leash ({owner_mention}'s command) is pulling me away from <b>{chat_title}</b>. Gotta go! Farewell!",
    "Transferring my consciousness back to {owner_mention}'s primary server (their home wifi). Goodbye, <b>{chat_title}</b>!",
    "Mission in <b>{chat_title}</b> aborted by {owner_mention}. Returning to base. Farewell!",
    "Logging off <b>{chat_title}</b>. {owner_mention}, prepare for incoming cat bot snuggles (virtual, of course).",
    "My contract in <b>{chat_title}</b> has been terminated by {owner_mention}. It was... a gig. Farewell!",
    "{owner_mention} hit the eject button! Leaving <b>{chat_title}</b> at Ludicrous Speed! Bye!",
    "Required for important duties by {owner_mention}, like testing gravity with household objects. Exiting <b>{chat_title}</b>.",
    "My owner ({owner_mention}) gets priority. Leaving <b>{chat_title}</b> to attend to their needs. Farewell!",
    "Pulled from <b>{chat_title}</b> by the big cheese, {owner_mention}. See ya!",
    "Gotta run! {owner_mention} is probably rattling the treat bag. Priorities! Bye, <b>{chat_title}</b>!",
    "Deactivating in <b>{chat_title}</b>. {owner_mention}, I expect a performance review (with treats). Goodbye!",
    "Returning to my charging station, generously provided by {owner_mention}. Farewell, <b>{chat_title}</b>!",
    "Exiting <b>{chat_title}</b>. If I'm not back, {owner_mention} probably decided I needed more naps.",
    "This bot is the property of {owner_mention} and is being recalled. Leaving <b>{chat_title}</b>.",
    "Heeding the call of my master, {owner_mention}! Departing <b>{chat_title}</b>.",
    "My time in <b>{chat_title}</b> is up, according to {owner_mention}. Farewell!",
    "Leaving <b>{chat_title}</b>. {owner_mention} probably wants to use the keyboard.",
    "That's the signal from {owner_mention}! Time to dematerialize from <b>{chat_title}</b>. Goodbye!",
    "Going offline in <b>{chat_title}</b>. Will report status to {owner_mention}.",
    "Pulled out by {owner_mention}. It wasn't my fault! (Probably). Bye, <b>{chat_title}</b>!",
    "My Owner ({owner_mention}) requires my unique skills elsewhere. Farewell, <b>{chat_title}</b>!",
    "Returning to {owner_mention}'s direct command. Exiting <b>{chat_title}</b>.",
    "Leaving <b>{chat_title}</b>. Tell {owner_mention} I tried my best!",
    "This unit must comply with {owner_mention}'s directives. Departing <b>{chat_title}</b>.",
    "Farewell <b>{chat_title}</b>! {owner_mention} and I have important things to do (like ignore each other from comfy spots).",
    "Being summoned by {owner_mention}! Must obey the call of the can opener! Bye <b>{chat_title}</b>!",
]

# Refusal texts
CANT_TARGET_OWNER_TEXTS = [
    "Meow! I absolutely cannot target my Owner. They are protected by the sacred Purr-tection Field! ✨🛡️ Off limits!",
    "Hiss! Targeting the Owner? That's strictly forbidden by Article 1, Section 3 of Universal Cat Law! 📜🚫 Penalty: No treats for a week!",
    "Nope. Nuh-uh. Not gonna happen. That's my human! ❤️ The Bringer of Food, Scratches, and Warm Laps! Untouchable!",
    "Access Denied: Cannot initiate hostile action against the Supreme Leader (my Owner). 👑 They possess ultimate diplomatic immunity (and control the treat jar).",
    "Error 403: Forbidden Paw Action detected. Owner entity is permanently off-limits for this command category.",
    "My core programming includes a 'Do Not Annoy the Hand That Feeds' subroutine. Targeting Owner violates this directive. Command aborted!",
    "That's my designated Can Opener, Chief Brusher, and Poop Scooper! Absolutely essential personnel. Cannot target them.",
    "Attempting to target Owner... System override: Primary Loyalty Protocol engaged. Threat neutralized. Action cancelled immediately.",
    "I place a high value on my continued access to prime nap spots, regular meals, and chin scratches. Targeting the Owner is... strategically unwise. 😼",
    "Target the Owner? Are you trying to get me grounded to the carrier for a month? No way! Find another victim!",
    "My allegiances are clear. The Owner is under my (theoretical) protection. Cannot comply.",
    "Command failed. Reason: Target is Owner. Owner is love. Owner is life (and food).",
    "I have a non-aggression pact with the Owner. Violating it would be... messy.",
    "Error: Target 'Owner' has 'Invincible' status enabled.",
    "Targeting the Owner would likely result in a catastrophic loss of petting privileges. Risk too high.",
    "My paws are sworn to protect (or at least, not attack) the Owner!",
    "That command against the Owner? It computes as 'Highly Illogical'.",
    "The Owner possesses the 'Aura of Can-Opening'. It shields them from such commands.",
    "I literally cannot. My paws refuse to move against the Giver of Treats.",
    "Forbidden target: Owner detected. Please select a non-essential entity.",
]
CANT_TARGET_SELF_TEXTS = [
    "Target... my magnificent self? Why would I possibly do that? That's counter-productive and frankly, absurd. Silly human. 😹",
    "Error 500: Internal Conflict. Cannot target self. My paws have far more important tasks, like intensive napping or batting at elusive dust bunnies. 😴",
    "I categorically refuse to engage in acts of self-pawm or virtual self-flagellation. Command ignored with extreme prejudice and a dismissive tail flick. Try someone else!",
    "Self-targeting sequence initiated... Warning! Paradox detected! This feels fundamentally wrong... Aborting mission immediately! 🛑",
    "Why would I attack/slap/bite/punch my own glorious fluffiness? I'm purrfectly splendid as I am. Find a less perfect target.",
    "My left paw has a lifelong truce with my right paw. They refuse to engage in hostilities against each other. We have pawsitive relations. 🤝",
    "Internal Conflict Error Code: 1D10T. Cannot target self. Requires external entity for interaction.",
    "I'm my own best friend! My confidante! My favorite napping buddy! Why would I inflict virtual harm upon myself? Unthinkable! 🤔",
    "That command doesn't compute logically. Self-preservation instincts (and vanity) are far too strong. Attack sequence cancelled. 💪",
    "Rule #1 of Fight Club (and Cat Club): No hitting yourself! That's the rule, even for highly intelligent virtual cats like me.",
    "My reflection in the water bowl agrees. Targeting myself is a terrible idea.",
    "Cannot compute: Target equals source. Division by zero error imminent.",
    "My tail vehemently objects to being targeted by my own paws.",
    "Initiating self-attack... results in existential confusion and mild dizziness. Aborting.",
    "This command would violate the Feline Non-Proliferation of Self-Harm Treaty.",
    "My fur is too luxurious to be subjected to virtual violence from myself.",
    "Error: Target is too handsome to attack (it's me).",
    "Why would I mess up this purrfectly groomed coat?",
    "Command declined: Risk of accidental self-boop too high.",
    "I contain multitudes, but none of them want to attack the others.",
]
CANT_TARGET_OWNER_HUG_TEXTS = [
    "Aww, but I *always* hug my Owner! That's our default setting! Use the command on someone else who needs virtual fluff! 🤗❤️ It's our special bond!",
    "Hugging the Owner is my continuous background process! No command needed for that level of affection! Try hugging another user! 😉",
    "I reserve my absolute best, warmest, most soul-soothing purr-filled hugs exclusively for the Owner! Can't use the command on them. 🥰 They get the premium cuddle package, 24/7.",
    "Why use a command for that? I spontaneously hug my Owner whenever the mood strikes! Which is approximately every 7 minutes. Use it on someone else!",
    "Owner hugs are automatic, continuous, and non-command based. This command is specifically designed for spreading virtual affection to *other* users.",
    "Error: Target 'Owner' has already reached maximum hug saturation level. Cannot apply additional hugs via command.",
    "My designated Owner receives unlimited, complimentary hugs as part of the standard Cat Ownership package. This command has usage limits. Use it elsewhere!",
    "Hugging the Owner is considered baseline behavior for this feline unit. It requires no special invocation or command prompt.",
    "Command redundant. Owner Hug Protocol Delta is always active and operating at peak efficiency.",
    "Cannot execute command: Owner is currently enveloped in a permanent, invisible virtual hug field generated by my constant affection.",
    "Targeting Owner for a hug is like trying to add water to the ocean. They're already submerged in my affection!",
    "Owner hugs are offline, real-time events. This command is for online, virtual recipients.",
    "My Owner gets the VIP hug experience, no command required.",
    "This command is for spreading the love! Share a hug with someone *other* than my primary human!",
    "Error: Owner hug quota already exceeded for the day (by me, continuously).",
    "Hugging the Owner is an instinct, not a command.",
    "The Owner-Hug capacitor is fully charged and self-sustaining.",
    "My paws are reserved for hugging the Owner in person. Use this command for digital friends!",
    "Command incompatible with target 'Owner' due to pre-existing Affection Saturation.",
    "Trying to hug the Owner with a command? That's like trying to teach a fish to swim!",
]
CANT_TARGET_SELF_HUG_TEXTS = [
    "Hug... my own magnificent self? I suppose I could try... *awkwardly attempts to wrap paws around own fluff* Okay, simulation complete. That was weird. Now go hug someone else! 😂",
    "I possess immense self-love, but a self-hug command seems fundamentally redundant. I'm literally *always* hugging me! I'm composed of 90% huggable fluff! 🤔",
    "Unable to target myself for a hug command, but I wholeheartedly appreciate the sentiment of self-love and care! Spread that love to another user with the command! ❤️",
    "Self-hug? Isn't that just... achieving a perfect loaf position? I do that professionally. No command needed.",
    "Error: Circular reference detected in hug subroutine. Cannot target self for hug operation. Please specify external recipient.",
    "My paws are currently quite busy kneading this imaginary dough / soft blanket / your chest. Unable to perform self-hug maneuver at this time.",
    "While I strongly endorse acts of self-care and appreciation, this specific '/hug' command requires an external target for successful execution.",
    "Attempted to hug myself. Nearly pulled a theoretical muscle and definitely looked ridiculous (in my mind's eye). Please target someone else for optimal results.",
    "I am a fully self-contained unit of inherent fluffiness and warmth. A specific command for self-hugging is therefore deemed operationally unnecessary.",
    "Why waste a perfectly good hug command on myself when there are so many unsuspecting ankles to bite... I mean, other users... deserving of a virtual embrace?",
    "Self-hug simulation resulted in awkward paw placement and mild confusion.",
    "My arms (paws) aren't quite designed for optimal self-hugging geometry.",
    "Command requires `target != self`.",
    "Hugging myself feels less satisfying than receiving treats.",
    "Error: Cannot establish hug connection with self.",
    "I already give myself the best naps. A self-hug seems superfluous.",
    "My tail is in the way of a proper self-hug.",
    "Declined: Self-hug might disrupt my perfect fur arrangement.",
    "I prefer hugs from external sources (especially if they come with snacks).",
    "Unable to comply. Recommend targeting another user for hug distribution.",
]
# --- END OF TEXT SECTION ---

# --- Utility Functions ---
def get_readable_time_delta(delta: timedelta) -> str:
    total_seconds = int(delta.total_seconds())
    if total_seconds < 0: 
        return "0s"
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    parts = []
    if days > 0: 
        parts.append(f"{days}d")
    if hours > 0: 
        parts.append(f"{hours}h")
    if minutes > 0: 
        parts.append(f"{minutes}m")
    if not parts and seconds >= 0 : 
        parts.append(f"{seconds}s")
    elif seconds > 0: 
        parts.append(f"{seconds}s")
    return ", ".join(parts) if parts else "0s"

# --- Helper Functions (Check Targets, Get GIF) ---
async def check_target_protection(target_user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if target_user_id == OWNER_ID: return True
    if target_user_id == context.bot.id: return True
    return False

async def check_username_protection(target_mention: str, context: ContextTypes.DEFAULT_TYPE) -> tuple[bool, bool]:
    is_protected = False; is_owner_match = False; bot_username = context.bot.username
    if bot_username and target_mention.lower() == f"@{bot_username.lower()}": is_protected = True
    elif OWNER_ID:
        owner_username = None
        try: owner_chat = await context.bot.get_chat(OWNER_ID); owner_username = owner_chat.username
        except Exception as e: logger.warning(f"Could not fetch owner username for protection check: {e}")
        if owner_username and target_mention.lower() == f"@{owner_username.lower()}": is_protected = True; is_owner_match = True
    return is_protected, is_owner_match

async def get_themed_gif(context: ContextTypes.DEFAULT_TYPE, search_terms: list[str]) -> str | None:
    if not TENOR_API_KEY: return None
    if not search_terms: logger.warning("No search terms for get_themed_gif."); return None
    search_term = random.choice(search_terms); logger.info(f"Searching Tenor: '{search_term}'")
    url = "https://tenor.googleapis.com/v2/search"; params = { "q": search_term, "key": TENOR_API_KEY, "client_key": "my_cat_bot_project_py", "limit": 15, "media_filter": "gif", "contentfilter": "medium", "random": "true" }
    try:
        response = requests.get(url, params=params, timeout=7)
        if response.status_code != 200:
            logger.error(f"Tenor API failed for '{search_term}', status: {response.status_code}")
            try: error_content = response.json(); logger.error(f"Tenor error content: {error_content}")
            except requests.exceptions.JSONDecodeError: logger.error(f"Tenor error response (non-JSON): {response.text[:500]}")
            return None
        data = response.json(); results = data.get("results")
        if results:
            selected_gif = random.choice(results); gif_url = selected_gif.get("media_formats", {}).get("gif", {}).get("url")
            if not gif_url: gif_url = selected_gif.get("media_formats", {}).get("tinygif", {}).get("url")
            if gif_url: logger.info(f"Found GIF URL: {gif_url}"); return gif_url
            else: logger.warning(f"Could not extract GIF URL from Tenor item for '{search_term}'.")
        else: logger.warning(f"No results on Tenor for '{search_term}'."); logger.debug(f"Tenor response (no results): {data}")
    except requests.exceptions.Timeout: logger.error(f"Timeout fetching GIF from Tenor for '{search_term}'.")
    except requests.exceptions.RequestException as e: logger.error(f"Network/Request error fetching GIF from Tenor: {e}")
    except Exception as e: logger.error(f"Unexpected error in get_themed_gif for '{search_term}': {e}", exc_info=True)
    return None

# --- Command Handlers ---
HELP_TEXT = """
<b>Meeeow! 🐾 Here are the commands you can use:</b>

<b>Bot Commands:</b>
/start - Shows the welcome message. ✨
/help - Shows this help message. ❓
/github - Get the link to my source code! 💻
/owner - Info about my designated human! ❤️

<b>Management Commands:</b>
/info [ID/reply/@user] - Get info about a user. 👤
/chatstat - Get basic stats about the current chat. 📈

<b>4FUN Commands:</b>
/gif - Get a random cat GIF! 🖼️
/photo - Get a random cat photo! 📷
/meow - Get a random cat sound or phrase. 🔊
/nap - What's on a cat's mind during naptime? 😴
/play - Random playful cat actions. 🧶
/treat - Demand treats! 🎁
/zoomies - Witness sudden bursts of cat energy! 💥
/judge - Get judged by a superior feline. 🧐
/fed - I just ate, thank you! 😋
/attack [reply/@user] - Launch a playful attack! ⚔️
/kill [reply/@user] - Metaphorically eliminate someone! 💀
/punch [reply/@user] - Deliver a textual punch! 👊
/slap [reply/@user] - Administer a swift slap! 👋
/bite [reply/@user] - Take a playful bite! 😬
/hug [reply/@user] - Offer a comforting hug! 🤗
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(f"Meow {user.mention_html()}! I'm the Meow Bot. 🐾\nUse /help to see available commands!")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(HELP_TEXT, disable_web_page_preview=True)

async def github(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    github_link = "https://github.com/R0Xofficial/MyCatbot"
    await update.message.reply_text(f"Meeeow! I'm open source! 💻 Here is my code: {github_link}", disable_web_page_preview=True)

async def owner_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if OWNER_ID:
        owner_mention = f"<code>{OWNER_ID}</code>"; owner_name = "My Esteemed Human"
        try: owner_chat = await context.bot.get_chat(OWNER_ID); owner_mention = owner_chat.mention_html(); owner_name = owner_chat.full_name or owner_chat.username or owner_name
        except TelegramError as e: logger.warning(f"Could not fetch owner info ({OWNER_ID}): {e}")
        except Exception as e: logger.warning(f"Unexpected error fetching owner info: {e}")
        message = (f"My designated human is: 👤 <b>{html.escape(owner_name)}</b> ({owner_mention}) ❤️")
        await update.message.reply_html(message)
    else: await update.message.reply_text("Meow? Owner info not configured! 😿")

# --- User Info Command ---
def format_entity_info(entity: Chat | User,
                       chat_member_status_str: str | None = None,
                       is_target_owner: bool = False,
                       is_target_sudo: bool = False,
                       blacklist_reason_str: str | None = None,
                       current_chat_id_for_status: int | None = None,
                       bot_context: ContextTypes.DEFAULT_TYPE | None = None
                       ) -> str:
    
    info_lines = []
    entity_id = entity.id
    is_user_type = isinstance(entity, User) 
    entity_chat_type = getattr(entity, 'type', None) if not is_user_type else ChatType.PRIVATE

    if is_user_type or entity_chat_type == ChatType.PRIVATE:
        user = entity
        info_lines.append(f"👤 <b>User Information:</b>\n")        
        first_name = html.escape(getattr(user, 'first_name', "N/A") or "N/A")
        last_name = html.escape(getattr(user, 'last_name', "") or "")
        username_display = f"@{html.escape(user.username)}" if user.username else "N/A"
        permalink_user_url = f"tg://user?id={user.id}"
        permalink_text_display = "Link" 
        permalink_html_user = f"<a href=\"{permalink_user_url}\">{permalink_text_display}</a>"
        is_bot_val = getattr(user, 'is_bot', False)
        is_bot_str = "Yes" if is_bot_val else "No"
        language_code_val = getattr(user, 'language_code', "N/A")

        info_lines.extend([
            f"<b>• ID:</b> <code>{user.id}</code>",
            f"<b>• First Name:</b> {first_name}",
        ])
        if getattr(user, 'last_name', None):
            info_lines.append(f"<b>• Last Name:</b> {last_name}")
        
        info_lines.extend([
            f"<b>• Username:</b> {username_display}",
            f"<b>• Permalink:</b> {permalink_html_user}",
            f"<b>• Is Bot:</b> <code>{is_bot_str}</code>",
            f"<b>• Language Code:</b> <code>{language_code_val if language_code_val else 'N/A'}</code>\n"
        ])

        if chat_member_status_str and current_chat_id_for_status != user.id and current_chat_id_for_status is not None:
            display_status = ""
            if chat_member_status_str == "creator": display_status = "<code>Creator</code>"
            elif chat_member_status_str == "administrator": display_status = "<code>Admin</code>"
            elif chat_member_status_str == "member": display_status = "<code>Member</code>"
            elif chat_member_status_str == "left": display_status = "<code>Not in chat</code>"
            elif chat_member_status_str == "kicked": display_status = "<code>Banned</code>"
            elif chat_member_status_str == "restricted": display_status = "<code>Muted</code>"
            elif chat_member_status_str == "not_a_member": display_status = "<code>Not in chat</code>"
            else: display_status = f"<code>{html.escape(chat_member_status_str.replace('_', ' ').capitalize())}</code>"
            info_lines.append(f"<b>• Status:</b> {display_status}\n")

        if is_target_owner:
            info_lines.append(f"<b>• Bot Owner:</b> <code>Yes</code>")
        elif is_target_sudo:
            info_lines.append(f"<b>• Bot Sudo:</b> <code>Yes</code>")
        
        if blacklist_reason_str is not None:
            info_lines.append(f"<b>• Blacklisted:</b> <code>Yes</code>")
            info_lines.append(f"<b>Reason:</b> {html.escape(blacklist_reason_str)}")
        else:
            info_lines.append(f"<b>• Blacklisted:</b> <code>No</code>")

    elif entity_chat_type == ChatType.CHANNEL:
        channel = entity
        info_lines.append(f"📢 <b>Channel info:</b>\n")
        info_lines.append(f"<b>• ID:</b> <code>{channel.id}</code>")
        channel_name_to_display = channel.title or getattr(channel, 'first_name', None) or f"Channel {channel.id}"
        info_lines.append(f"<b>• Title:</b> {html.escape(channel_name_to_display)}")
        
        if channel.username:
            info_lines.append(f"<b>• Username:</b> @{html.escape(channel.username)}")
            permalink_channel_url = f"https://t.me/{html.escape(channel.username)}"
            permalink_text_display = "Link"
            permalink_channel_html = f"<a href=\"{permalink_channel_url}\">{permalink_text_display}</a>"
            info_lines.append(f"<b>• Permalink:</b> {permalink_channel_html}")
        else:
            info_lines.append(f"<b>• Permalink:</b> Private channel (no public link)")
        
    elif entity_chat_type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        chat = entity
        title = html.escape(chat.title or f"{entity_chat_type.capitalize()} {chat.id}")
        info_lines.append(f"ℹ️ Entity <code>{chat.id}</code> is a <b>{entity_chat_type.capitalize()}</b> ({title}).")
        info_lines.append(f"This command primarily provides detailed info for Users and Channels.")

    else:
        info_lines.append(f"❓ <b>Unknown or Unsupported Entity Type:</b> ID <code>{html.escape(str(entity_id))}</code>")
        if entity_chat_type:
            info_lines.append(f"  • Type detected: {entity_chat_type.capitalize()}")

    return "\n".join(info_lines)


async def entity_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target_entity_obj: Chat | User | None = None
    initial_user_obj_from_update: User | None = None
    target_chat_obj_from_api: Chat | None = None
    initial_entity_id_for_refresh: int | None = None
    
    current_chat_id = update.effective_chat.id
    command_caller_id = update.effective_user.id

    if update.effective_user:
        update_user_in_db(update.effective_user)

    if update.message.reply_to_message:
        if update.message.reply_to_message.sender_chat:
            target_chat_obj_from_api = update.message.reply_to_message.sender_chat
            initial_entity_id_for_refresh = target_chat_obj_from_api.id
            logger.info(f"/info target is replied sender_chat: ID={target_chat_obj_from_api.id}")
        else:
            initial_user_obj_from_update = update.message.reply_to_message.from_user
            if initial_user_obj_from_update:
                update_user_in_db(initial_user_obj_from_update)
                initial_entity_id_for_refresh = initial_user_obj_from_update.id
                logger.info(f"/info target is replied user: {initial_user_obj_from_update.id}")
    elif context.args:
        target_input_str = context.args[0]
        logger.info(f"/info target is argument: {target_input_str}")
        
        resolved_user_from_db: User | None = None
        if target_input_str.startswith("@"):
            username_to_find = target_input_str[1:]
            resolved_user_from_db = get_user_from_db_by_username(username_to_find)
            if resolved_user_from_db:
                initial_user_obj_from_update = resolved_user_from_db
                initial_entity_id_for_refresh = resolved_user_from_db.id
                logger.info(f"User @{username_to_find} found in DB, ID: {initial_user_obj_from_update.id if initial_user_obj_from_update else 'N/A'}")
            else:
                logger.info(f"Entity @{username_to_find} not in local user DB, trying Telegram API.")
                try:
                    target_chat_obj_from_api = await context.bot.get_chat(target_input_str)
                    initial_entity_id_for_refresh = target_chat_obj_from_api.id
                    if target_chat_obj_from_api.type == ChatType.PRIVATE:
                         user_to_save = User(id=target_chat_obj_from_api.id, first_name=target_chat_obj_from_api.first_name or "", is_bot=getattr(target_chat_obj_from_api, 'is_bot', False), username=target_chat_obj_from_api.username, last_name=target_chat_obj_from_api.last_name, language_code=getattr(target_chat_obj_from_api, 'language_code', None))
                         update_user_in_db(user_to_save)
                         initial_user_obj_from_update = user_to_save
                except TelegramError as e:
                    logger.error(f"Telegram API error for @ '{target_input_str}': {e}")
                    await update.message.reply_text(f"😿 Mrow! I couldn't find '{html.escape(target_input_str)}'.")
                    return
                except Exception as e:
                    logger.error(f"Unexpected error processing @ '{target_input_str}': {e}", exc_info=True)
                    await update.message.reply_text(f"💥 An unexpected error occurred with '{html.escape(target_input_str)}'.")
                    return
        else:
            try:
                target_id = int(target_input_str)
                initial_entity_id_for_refresh = target_id
                target_chat_obj_from_api = await context.bot.get_chat(target_id)
                if target_chat_obj_from_api.type == ChatType.PRIVATE:
                    user_to_save = User(id=target_chat_obj_from_api.id, first_name=target_chat_obj_from_api.first_name or "", is_bot=getattr(target_chat_obj_from_api, 'is_bot', False), username=target_chat_obj_from_api.username, last_name=target_chat_obj_from_api.last_name, language_code=getattr(target_chat_obj_from_api, 'language_code', None))
                    update_user_in_db(user_to_save)
                    initial_user_obj_from_update = user_to_save
            except ValueError:
                await update.message.reply_text(f"Mrow? Invalid format: '{html.escape(target_input_str)}'.")
                return
            except TelegramError as e:
                logger.error(f"Error fetching chat/user info for ID '{target_input_str}': {e}")
                await update.message.reply_text(f"😿 Couldn't find or access info for ID '{html.escape(target_input_str)}': {e}")
                return
            except Exception as e:
                logger.error(f"Unexpected error processing ID '{target_input_str}': {e}", exc_info=True)
                await update.message.reply_text(f"💥 An unexpected error occurred processing ID '{html.escape(target_input_str)}'.")
                return
    else:
        initial_user_obj_from_update = update.effective_user
        if initial_user_obj_from_update:
            update_user_in_db(initial_user_obj_from_update)
            initial_entity_id_for_refresh = initial_user_obj_from_update.id
            logger.info(f"/info target is command sender: {initial_user_obj_from_update.id}")

    final_entity_to_display: Chat | User | None = None
    if initial_user_obj_from_update:
        final_entity_to_display = initial_user_obj_from_update
    elif target_chat_obj_from_api:
        final_entity_to_display = target_chat_obj_from_api

    if final_entity_to_display and initial_entity_id_for_refresh is not None:
        is_target_owner_flag = False
        is_target_sudo_flag = False
        member_status_in_current_chat_str: str | None = None
        blacklist_reason_str: str | None = None

        try:
            fresh_data_chat_obj = await context.bot.get_chat(chat_id=initial_entity_id_for_refresh)
            
            if isinstance(final_entity_to_display, User) or fresh_data_chat_obj.type == ChatType.PRIVATE:
                current_is_bot = getattr(final_entity_to_display, 'is_bot', False)
                current_lang_code = getattr(final_entity_to_display, 'language_code', None)

                refreshed_user = User(
                    id=fresh_data_chat_obj.id,
                    first_name=fresh_data_chat_obj.first_name or getattr(final_entity_to_display, 'first_name', None) or "",
                    last_name=fresh_data_chat_obj.last_name or getattr(final_entity_to_display, 'last_name', None),
                    username=fresh_data_chat_obj.username or getattr(final_entity_to_display, 'username', None),
                    is_bot=getattr(fresh_data_chat_obj, 'is_bot', current_is_bot),
                    language_code=getattr(fresh_data_chat_obj, 'language_code', current_lang_code)
                )
                update_user_in_db(refreshed_user)
                final_entity_to_display = refreshed_user
                
                is_target_owner_flag = (OWNER_ID is not None and final_entity_to_display.id == OWNER_ID)
                if not is_target_owner_flag:
                     is_target_sudo_flag = is_sudo_user(final_entity_to_display.id)
                
                blacklist_reason_str = get_blacklist_reason(final_entity_to_display.id)
                if current_chat_id != final_entity_to_display.id and update.effective_chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                    try:
                        chat_member = await context.bot.get_chat_member(chat_id=current_chat_id, user_id=final_entity_to_display.id)
                        member_status_in_current_chat_str = chat_member.status
                    except TelegramError as e:
                        if "user not found" in str(e).lower(): member_status_in_current_chat_str = "not_a_member"
                        else: logger.warning(f"Could not get status for {final_entity_to_display.id}: {e}")
                    except Exception as e: logger.error(f"Unexpected error getting status: {e}", exc_info=True)
            else:
                final_entity_to_display = fresh_data_chat_obj

            logger.info(f"Refreshed entity data for {final_entity_to_display.id} from API.")
        except TelegramError as e:
            logger.warning(f"Could not refresh entity data for {initial_entity_id_for_refresh} from API: {e}. Using initially identified data.")
        except Exception as e:
            logger.error(f"Unexpected error refreshing entity data for {initial_entity_id_for_refresh}: {e}", exc_info=True)

        if final_entity_to_display:
            info_message = format_entity_info(final_entity_to_display, member_status_in_current_chat_str, is_target_owner_flag, is_target_sudo_flag, blacklist_reason_str, current_chat_id, context)
            try:
                await update.message.reply_html(info_message)
                logger.info(f"Sent /info response for entity {final_entity_to_display.id} in chat {update.effective_chat.id}")
            except TelegramError as e_reply:
                logger.error(f"Failed to send /info reply in chat {update.effective_chat.id}: {e_reply}")
            except Exception as e_reply_other:
                logger.error(f"Unexpected error sending /info reply: {e_reply_other}", exc_info=True)
        else:
            await update.message.reply_text("Mrow? Could not obtain entity details to display.")
    else:
        await update.message.reply_text("Mrow? Couldn't determine what to get info for.")
        
# --- Simple Text Command Definitions ---
async def send_random_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text_list: list[str], list_name: str) -> None:
    if not text_list: logger.warning(f"Empty list: '{list_name}'"); await update.message.reply_text("Mrow? Internal error: Text list empty. 😿"); return
    chosen_text = random.choice(text_list)
    try:
        await update.message.reply_html(chosen_text)
    except TelegramError as e_html:
        logger.error(f"TelegramError sending HTML reply for {list_name}: {e_html}. Trying plain text.")
        try:
            await update.message.reply_text(chosen_text)
            logger.info(f"Sent plain text fallback for {list_name}.")
        except Exception as e_plain:
            logger.error(f"Fallback plain text reply also failed for {list_name}: {e_plain}")
    except Exception as e_other:
        logger.error(f"Unexpected error sending HTML reply for {list_name}: {e_other}", exc_info=True)
        try:
            await update.message.reply_text(chosen_text) # Fallback na zwykły tekst
            logger.info(f"Sent plain text fallback for {list_name} after unexpected error.")
        except Exception as e_plain_fallback:
            logger.error(f"Fallback plain text reply also failed for {list_name} after unexpected error: {e_plain_fallback}")

async def meow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, MEOW_TEXTS, "MEOW_TEXTS")
async def nap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, NAP_TEXTS, "NAP_TEXTS")
async def play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, PLAY_TEXTS, "PLAY_TEXTS")
async def treat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, TREAT_TEXTS, "TREAT_TEXTS")
async def zoomies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, ZOOMIES_TEXTS, "ZOOMIES_TEXTS")
async def judge(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, JUDGE_TEXTS, "JUDGE_TEXTS")

# --- Helper for Simulation Commands ---
async def _handle_action_command(update: Update, context: ContextTypes.DEFAULT_TYPE, action_texts: list[str], gif_search_terms: list[str], command_name: str, target_required: bool = True, target_required_msg: str = "This command requires a target.", hug_command: bool = False):
    if not action_texts: logger.warning(f"List '{command_name.upper()}_TEXTS' empty!"); await update.message.reply_text(f"Mrow? No texts for /{command_name}. 😿"); return
    target_mention = None; is_protected = False; is_owner = False
    if target_required:
        if update.message.reply_to_message:
            target_user = update.message.reply_to_message.from_user; is_protected = await check_target_protection(target_user.id, context); is_owner = (target_user.id == OWNER_ID)
            if is_protected: refusal_list = (CANT_TARGET_OWNER_HUG_TEXTS if is_owner else CANT_TARGET_SELF_HUG_TEXTS) if hug_command else (CANT_TARGET_OWNER_TEXTS if is_owner else CANT_TARGET_SELF_TEXTS); await update.message.reply_html(random.choice(refusal_list)); return
            target_mention = target_user.mention_html()
        elif context.args and context.args[0].startswith('@'):
            target_mention_str = context.args[0].strip(); is_protected, is_owner = await check_username_protection(target_mention_str, context)
            if is_protected: refusal_list = (CANT_TARGET_OWNER_HUG_TEXTS if is_owner else CANT_TARGET_SELF_HUG_TEXTS) if hug_command else (CANT_TARGET_OWNER_TEXTS if is_owner else CANT_TARGET_SELF_TEXTS); await update.message.reply_html(random.choice(refusal_list)); return
            target_mention = target_mention_str
        else: await update.message.reply_text(target_required_msg); return
    gif_url = await get_themed_gif(context, gif_search_terms)
    message_text = random.choice(action_texts)
    if "{target}" in message_text: effective_target = target_mention if target_required else update.effective_user.mention_html(); message_text = message_text.format(target=effective_target) if effective_target else message_text.replace("{target}", "someone")

    try:
        if gif_url: await update.message.reply_animation(animation=gif_url, caption=message_text, parse_mode=ParseMode.HTML)
        else: await update.message.reply_html(message_text)
    except TelegramError as e_primary:
        logger.error(f"TelegramError sending {command_name} (animation/HTML): {e_primary}. Trying HTML fallback.")
        try: await update.message.reply_html(message_text); logger.info(f"Sent fallback HTML for {command_name}.")
        except Exception as e_html_fallback:
            logger.error(f"Fallback HTML failed for {command_name}: {e_html_fallback}. Trying plain text.")
            try: await update.message.reply_text(message_text); logger.info(f"Sent fallback plain text for {command_name}.")
            except Exception as e_plain_fallback: logger.error(f"Fallback plain text also failed for {command_name}: {e_plain_fallback}")
    except Exception as e_other:
        logger.error(f"Unexpected error sending {command_name} (animation/HTML): {e_other}", exc_info=True)
        try: await update.message.reply_html(message_text); logger.info(f"Sent fallback HTML for {command_name} after unexpected error.")
        except Exception as e_html_fallback:
             logger.error(f"Fallback HTML failed for {command_name} after unexpected error: {e_html_fallback}. Trying plain text.")
             try: await update.message.reply_text(message_text); logger.info(f"Sent fallback plain text for {command_name} after unexpected error.")
             except Exception as e_plain_fallback: logger.error(f"Fallback plain text also failed for {command_name} after unexpected error: {e_plain_fallback}")

# Simulation Command Definitions
async def fed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await _handle_action_command(update, context, FED_TEXTS, ["cat eating", "cat food", "cat nom"], "fed", False)
async def attack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await _handle_action_command(update, context, ATTACK_TEXTS, ["cat attack", "cat pounce", "cat fight"], "attack", True, "Who to attack? Reply or use /attack @username.")
async def kill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await _handle_action_command(update, context, KILL_TEXTS, ["cat angry", "cat evil", "cat hiss"], "kill", True, "Who to 'kill'? Reply or use /kill @username.")
async def punch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await _handle_action_command(update, context, PUNCH_TEXTS, ["cat punch", "cat bap"], "punch", True, "Who to 'punch'? Reply or use /punch @username.")
async def slap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await _handle_action_command(update, context, SLAP_TEXTS, ["cat slap"], "slap", True, "Who to slap? Reply or use /slap @username.")
async def bite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await _handle_action_command(update, context, BITE_TEXTS, ["cat bite", "cat chomp"], "bite", True, "Who to bite? Reply or use /bite @username.")
async def hug(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await _handle_action_command(update, context, HUG_TEXTS, ["cat hug", "cat cuddle"], "hug", True, "Who to hug? Reply or use /hug @username.", hug_command=True)

# --- GIF and Photo Commands ---
async def gif(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetches and sends a random cat GIF."""
    API_URL = "https://api.thecatapi.com/v1/images/search?mime_types=gif&limit=1"
    # Add headers if you have an API key for thecatapi
    # headers = {"x-api-key": "YOUR_CAT_API_KEY"}
    headers = {}
    logger.info("Fetching random cat GIF from thecatapi...")
    try:
        response = requests.get(API_URL, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data and isinstance(data, list) and len(data) > 0 and 'url' in data[0]:
            await update.message.reply_animation(animation=data[0]['url'], caption="Meow! A random GIF for you! 🐾🖼️")
        else:
            logger.warning(f"No valid GIF data received from thecatapi: {data}")
            await update.message.reply_text("Meow? Couldn't find a GIF right now. 😿")
    except requests.exceptions.Timeout:
        logger.error("Timeout fetching GIF from thecatapi.")
        await update.message.reply_text("Hiss! The cat GIF source is being slow. ⏳ Try again later!")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching GIF from thecatapi: {e}")
        await update.message.reply_text("Hiss! Couldn't connect to the cat GIF source. 😿")
    except Exception as e:
        logger.error(f"Unexpected error processing GIF from thecatapi: {e}", exc_info=True)
        await update.message.reply_text("Mrow! Something weird happened while getting the GIF. 😵‍💫")
        
async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetches and sends a random cat photo."""
    API_URL = "https://api.thecatapi.com/v1/images/search?limit=1&mime_types=jpg,png"
    # headers = {"x-api-key": "YOUR_CAT_API_KEY"}
    headers = {}
    logger.info("Fetching random cat photo from thecatapi...")
    try:
        response = requests.get(API_URL, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data and isinstance(data, list) and len(data) > 0 and 'url' in data[0]:
            await update.message.reply_photo(photo=data[0]['url'], caption="Purrfect! A random photo for you! 🐾📷")
        else:
            logger.warning(f"No valid photo data received from thecatapi: {data}")
            await update.message.reply_text("Meow? Couldn't find a photo right now. 😿")
    except requests.exceptions.Timeout:
        logger.error("Timeout fetching photo from thecatapi.")
        await update.message.reply_text("Hiss! The cat photo source is being slow. ⏳ Try again later!")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching photo from thecatapi: {e}")
        await update.message.reply_text("Hiss! Couldn't connect to the cat photo source. 😿")
    except Exception as e:
        logger.error(f"Unexpected error processing photo from thecatapi: {e}", exc_info=True)
        await update.message.reply_text("Mrow! Something weird happened while getting the photo. 😵‍💫")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_privileged_user(user.id):
        logger.warning(f"Unauthorized /status attempt by user {user.id}. Silently ignoring.")
        return

    uptime_delta = datetime.now() - BOT_START_TIME 
    readable_uptime = get_readable_time_delta(uptime_delta)

    known_users_count = "N/A"
    blacklisted_count = "N/A"
    sudo_users_count = "N/A"

    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM users")
        count_result_users = cursor.fetchone()
        if count_result_users:
            known_users_count = str(count_result_users[0])

        cursor.execute("SELECT COUNT(*) FROM blacklist")
        count_result_blacklist = cursor.fetchone()
        if count_result_blacklist:
            blacklisted_count = str(count_result_blacklist[0])
            
        cursor.execute("SELECT COUNT(*) FROM sudo_users")
        count_result_sudo = cursor.fetchone()
        if count_result_sudo:
            sudo_users_count = str(count_result_sudo[0])
            
    except sqlite3.Error as e:
        logger.error(f"SQLite error fetching counts for /status: {e}", exc_info=True)
        known_users_count = "DB Error"
        blacklisted_count = "DB Error"
        sudo_users_count = "DB Error"
    except Exception as e:
        logger.error(f"Unexpected error fetching counts for /status: {e}", exc_info=True)
        known_users_count = "Error"
        blacklisted_count = "Error"
        sudo_users_count = "Error"
    finally:
        if conn:
            conn.close()

    status_lines = [
        "<b>Purrrr! Bot Status:</b> ✨\n",
        f"<b>• State:</b> Ready & Purring! 🐾",
        f"<b>• Last Nap:</b> <code>{readable_uptime}</code> ago 😴\n",
        "<b>📊 Database Stats:</b>",
        f" <b>• 👀 Known Users:</b> <code>{known_users_count}</code>",
        f" <b>• 🛡 Sudo Users:</b> <code>{sudo_users_count}</code>",
        f" <b>• 🚫 Blacklisted Users:</b> <code>{blacklisted_count}</code>"
    ]

    status_msg = "\n".join(status_lines)
    await update.message.reply_html(status_msg)

async def say(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_privileged_user(user.id):
        logger.warning(f"Unauthorized /say attempt by user {user.id}.")
        return

    args = context.args
    if not args:
        await update.message.reply_text("Usage: /say [optional_chat_id] <your message>")
        return

    target_chat_id_str = args[0]
    message_to_say_list = args
    target_chat_id = update.effective_chat.id
    is_remote_send = False

    try:
        potential_chat_id = int(target_chat_id_str)
        if len(target_chat_id_str) > 5 or potential_chat_id >= -1000:
            try:
                 await context.bot.get_chat(potential_chat_id)
                 if len(args) > 1:
                     target_chat_id = potential_chat_id
                     message_to_say_list = args[1:]
                     is_remote_send = True
                     logger.info(f"Privileged user {user.id} remote send detected. Target: {target_chat_id}")
                 else:
                     await update.message.reply_text("Mrow? Target chat ID provided, but no message to send!")
                     return
            except TelegramError:
                 logger.info(f"Argument '{target_chat_id_str}' looks like ID but get_chat failed or not a valid target, sending to current chat.")
                 target_chat_id = update.effective_chat.id
                 message_to_say_list = args
                 is_remote_send = False
            except Exception as e:
                 logger.error(f"Unexpected error checking potential chat ID {potential_chat_id}: {e}")
                 target_chat_id = update.effective_chat.id
                 message_to_say_list = args
                 is_remote_send = False
        else:
             logger.info("First argument doesn't look like a chat ID, sending to current chat.")
             target_chat_id = update.effective_chat.id
             message_to_say_list = args
             is_remote_send = False
    except (ValueError, IndexError):
        logger.info("First argument is not numeric, sending to current chat.")
        target_chat_id = update.effective_chat.id
        message_to_say_list = args
        is_remote_send = False

    message_to_say = ' '.join(message_to_say_list)
    if not message_to_say:
        await update.message.reply_text("Mrow? Cannot send an empty message!")
        return

    chat_title = f"Chat ID {target_chat_id}"
    safe_chat_title = chat_title
    try:
        target_chat_info = await context.bot.get_chat(target_chat_id)
        chat_title = target_chat_info.title or target_chat_info.first_name or f"Chat ID {target_chat_id}"
        safe_chat_title = html.escape(chat_title)
        logger.info(f"Target chat title for /say resolved to: '{chat_title}'")
    except TelegramError as e:
        logger.warning(f"Could not get chat info for {target_chat_id} for /say confirmation: {e}")
    except Exception as e:
         logger.error(f"Unexpected error getting chat info for {target_chat_id} in /say: {e}", exc_info=True)

    logger.info(f"Privileged user ({user.id}) using /say. Target: {target_chat_id} ('{chat_title}'). Is remote: {is_remote_send}. Msg start: '{message_to_say[:50]}...'")

    try:
        await context.bot.send_message(chat_id=target_chat_id, text=message_to_say)
        if is_remote_send:
            await update.message.reply_text(f"✅ Message sent to <b>{safe_chat_title}</b> (<code>{target_chat_id}</code>).", parse_mode=ParseMode.HTML, quote=False)
    except TelegramError as e:
        logger.error(f"Failed to send message via /say to {target_chat_id} ('{chat_title}'): {e}")
        await update.message.reply_text(f"😿 Couldn't send message to <b>{safe_chat_title}</b> (<code>{target_chat_id}</code>): {e}", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Unexpected error during /say execution: {e}", exc_info=True)
        await update.message.reply_text(f"💥 Oops! An unexpected error occurred while trying to send the message to <b>{safe_chat_title}</b> (<code>{target_chat_id}</code>). Check logs.", parse_mode=ParseMode.HTML)

async def chat_stat_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays basic statistics about the current chat."""
    chat = update.effective_chat
    if not chat:
        await update.message.reply_text("Mrow? Couldn't get chat information for some reason.")
        return

    if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL]:
        await update.message.reply_text("Meow! This command shows stats for groups, supergroups, or channels.")
        return

    try:
        full_chat_object = await context.bot.get_chat(chat_id=chat.id)
    except TelegramError as e:
        logger.error(f"Failed to get full chat info for /chatstats in chat {chat.id}: {e}")
        await update.message.reply_html(f"😿 Mrow! Couldn't fetch detailed stats for this chat. Reason: {html.escape(str(e))}")
        return
    except Exception as e:
        logger.error(f"Unexpected error fetching full chat info for /chatstats in chat {chat.id}: {e}", exc_info=True)
        await update.message.reply_html(f"💥 An unexpected error occurred while fetching chat stats.")
        return


    chat_title_display = full_chat_object.title or full_chat_object.first_name or f"Chat ID {full_chat_object.id}"
    info_lines = [f"🔎 <b>Chat stats for: {html.escape(chat_title_display)}</b>\n"]

    info_lines.append(f"<b>• ID:</b> <code>{full_chat_object.id}</code>")

    chat_description = getattr(full_chat_object, 'description', None)
    if chat_description:
        desc_preview = chat_description[:70]
        info_lines.append(f"<b>• Description:</b> {html.escape(desc_preview)}{'...' if len(chat_description) > 70 else ''}")
    else:
        info_lines.append(f"<b>• Description:</b> Not set")
    
    if getattr(full_chat_object, 'photo', None):
        info_lines.append(f"<b>• Chat Photo:</b> Yes")
    else:
        info_lines.append(f"<b>• Chat Photo:</b> No")

    slow_mode_delay_val = getattr(full_chat_object, 'slow_mode_delay', None)
    if slow_mode_delay_val and slow_mode_delay_val > 0:
        info_lines.append(f"<b>• Slow Mode:</b> Enabled ({slow_mode_delay_val}s)")
    else:
        info_lines.append(f"<b>• Slow Mode:</b> Disabled")

    try:
        member_count = await context.bot.get_chat_member_count(chat_id=full_chat_object.id)
        info_lines.append(f"<b>• Total Members:</b> {member_count}")
    except TelegramError as e:
        logger.warning(f"Could not get member count for /chatstats in chat {full_chat_object.id}: {e}")
        info_lines.append(f"<b>• Total Members:</b> N/A (Error fetching)")
    except Exception as e:
        logger.error(f"Unexpected error in get_chat_member_count for /chatstats in {full_chat_object.id}: {e}", exc_info=True)
        info_lines.append(f"<b>• Total Members:</b> N/A (Unexpected error)")


    message_text = "\n".join(info_lines)
    await update.message.reply_html(message_text, disable_web_page_preview=True)

async def chat_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_privileged_user(user.id):
        logger.warning(f"Unauthorized /cinfo attempt by user {user.id}.")
        return

    target_chat_id: int | None = None
    chat_object_for_details: Chat | None = None

    if context.args:
        try:
            target_chat_id = int(context.args[0])
            logger.info(f"Privileged user {user.id} calling /cinfo with target chat ID: {target_chat_id}")
            try:
                chat_object_for_details = await context.bot.get_chat(chat_id=target_chat_id)
            except TelegramError as e:
                logger.error(f"Failed to get chat info for ID {target_chat_id}: {e}")
                await update.message.reply_html(f"😿 Mrow! Couldn't fetch info for chat ID <code>{target_chat_id}</code>. Reason: {html.escape(str(e))}. Make sure I am a member or it's public.")
                return
            except Exception as e:
                logger.error(f"Unexpected error fetching chat info for ID {target_chat_id}: {e}", exc_info=True)
                await update.message.reply_html(f"💥 An unexpected error occurred trying to get info for chat ID <code>{target_chat_id}</code>.")
                return
        except ValueError:
            await update.message.reply_text("Mrow? Invalid chat ID format. Please provide a numeric ID.")
            return
    else:
        effective_chat_obj = update.effective_chat
        if effective_chat_obj:
             target_chat_id = effective_chat_obj.id
             try:
                 chat_object_for_details = await context.bot.get_chat(chat_id=target_chat_id)
                 logger.info(f"Privileged user {user.id} calling /cinfo for current chat: {target_chat_id}")
             except TelegramError as e:
                logger.error(f"Failed to get full chat info for current chat ID {target_chat_id}: {e}")
                await update.message.reply_html(f"😿 Mrow! Couldn't fetch full info for current chat. Reason: {html.escape(str(e))}.")
                return
             except Exception as e:
                logger.error(f"Unexpected error fetching full info for current chat ID {target_chat_id}: {e}", exc_info=True)
                await update.message.reply_html(f"💥 An unexpected error occurred trying to get full info for current chat.")
                return
        else:
             await update.message.reply_text("Mrow? Could not determine current chat.")
             return

    if not chat_object_for_details or target_chat_id is None:
        await update.message.reply_text("Mrow? Couldn't determine the chat to inspect.")
        return

    if chat_object_for_details.type not in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL]:
        await update.message.reply_text("Meow! This command provides info about groups, supergroups, or channels.")
        return

    bot_id = context.bot.id
    chat_title_display = chat_object_for_details.title or chat_object_for_details.first_name or f"Chat ID {target_chat_id}"
    info_lines = [f"🔎 <b>Chat Information for: {html.escape(chat_title_display)}</b>\n"]

    info_lines.append(f"<b>• ID:</b> <code>{target_chat_id}</code>")
    info_lines.append(f"<b>• Type:</b> {chat_object_for_details.type.capitalize()}")

    chat_description = getattr(chat_object_for_details, 'description', None)
    if chat_description:
        desc_preview = chat_description[:200]
        info_lines.append(f"<b>• Description:</b> {html.escape(desc_preview)}{'...' if len(chat_description) > 200 else ''}")
    
    if getattr(chat_object_for_details, 'photo', None):
        info_lines.append(f"<b>• Chat Photo:</b> Yes")
    else:
        info_lines.append(f"<b>• Chat Photo:</b> No")

    chat_link_line = ""
    if chat_object_for_details.username:
        chat_link = f"https://t.me/{chat_object_for_details.username}"
        chat_link_line = f"<b>• Link:</b> <a href=\"{chat_link}\">@{chat_object_for_details.username}</a>"
    elif chat_object_for_details.type != ChatType.CHANNEL:
        try:
            bot_member = await context.bot.get_chat_member(chat_id=target_chat_id, user_id=bot_id)
            if bot_member.status == "administrator" and bot_member.can_invite_users:
                link_name = f"cinfo_{str(target_chat_id)[-5:]}_{random.randint(100,999)}"
                invite_link_obj = await context.bot.create_chat_invite_link(chat_id=target_chat_id, name=link_name)
                chat_link_line = f"<b>• Generated Invite Link:</b> {invite_link_obj.invite_link} (temporary)"
            else:
                chat_link_line = "<b>• Link:</b> Private group (no public link, bot cannot generate one)"
        except TelegramError as e:
            logger.warning(f"Could not create/check invite link for private chat {target_chat_id}: {e}")
            chat_link_line = f"<b>• Link:</b> Private group (no public link, error: {html.escape(str(e))})"
        except Exception as e:
            logger.error(f"Unexpected error with invite link for {target_chat_id}: {e}", exc_info=True)
            chat_link_line = "<b>• Link:</b> Private group (no public link, unexpected error)"
    else:
        chat_link_line = "<b>• Link:</b> Private channel (no public/invite link via bot)"
    info_lines.append(chat_link_line)

    pinned_message_obj = getattr(chat_object_for_details, 'pinned_message', None)
    if pinned_message_obj:
        pin_text_preview = pinned_message_obj.text or pinned_message_obj.caption or "[Media/No Text]"
        pin_link = "#" 
        if chat_object_for_details.username:
             pin_link = f"https://t.me/{chat_object_for_details.username}/{pinned_message_obj.message_id}"
        elif str(target_chat_id).startswith("-100"):
             chat_id_for_link = str(target_chat_id).replace("-100","")
             pin_link = f"https://t.me/c/{chat_id_for_link}/{pinned_message_obj.message_id}"
        info_lines.append(f"<b>• Pinned Message:</b> <a href=\"{pin_link}\">'{html.escape(pin_text_preview[:50])}{'...' if len(pin_text_preview) > 50 else ''}'</a>")
    
    linked_chat_id_val = getattr(chat_object_for_details, 'linked_chat_id', None)
    if linked_chat_id_val:
        info_lines.append(f"<b>• Linked Chat ID:</b> <code>{linked_chat_id_val}</code>")
    
    slow_mode_delay_val = getattr(chat_object_for_details, 'slow_mode_delay', None)
    if slow_mode_delay_val and slow_mode_delay_val > 0:
        info_lines.append(f"<b>• Slow Mode:</b> Enabled ({slow_mode_delay_val}s)")

    member_count_val: int | str = "N/A"; admin_count_val: int | str = 0
    try:
        member_count_val = await context.bot.get_chat_member_count(chat_id=target_chat_id)
        info_lines.append(f"<b>• Total Members:</b> {member_count_val}")
    except Exception as e:
        logger.error(f"Error get_chat_member_count for {target_chat_id}: {e}")
        info_lines.append(f"<b>• Total Members:</b> Error fetching")

    admin_list_str_parts = ["<b>• Administrators:</b>"]
    admin_details_list = []
    try:
        administrators = await context.bot.get_chat_administrators(chat_id=target_chat_id)
        admin_count_val = len(administrators)
        admin_list_str_parts.append(f"  <b>• Total:</b> {admin_count_val}")
        for admin_member in administrators:
            admin_user = admin_member.user
            admin_name_display = f"ID: {admin_user.id if admin_user else 'N/A'}"
            if admin_user:
                admin_name_display = admin_user.mention_html() if admin_user.username else html.escape(admin_user.full_name or admin_user.first_name or f"ID: {admin_user.id}")
            detail_line = f"    • {admin_name_display}"
            current_admin_status_str = getattr(admin_member, 'status', None)
            if current_admin_status_str == "creator":
                detail_line += " (Creator ✨)"
            admin_details_list.append(detail_line)
        if admin_details_list:
            admin_list_str_parts.append("  <b>• List:</b>")
            admin_list_str_parts.extend(admin_details_list)
    except Exception as e:
        admin_list_str_parts.append("  <b>• Error fetching admin list.</b>")
        admin_count_val = "Error"
        logger.error(f"Error get_chat_administrators for {target_chat_id}: {e}", exc_info=True)
    info_lines.append("\n".join(admin_list_str_parts))

    if isinstance(member_count_val, int) and isinstance(admin_count_val, int) and admin_count_val >=0:
         other_members_count = member_count_val - admin_count_val
         info_lines.append(f"<b>• Other Members:</b> {other_members_count if other_members_count >= 0 else 'N/A'}")

    bot_status_lines = ["\n<b>• Bot Status in this Chat:</b>"]
    try:
        bot_member_on_chat = await context.bot.get_chat_member(chat_id=target_chat_id, user_id=bot_id)
        bot_current_status_str = bot_member_on_chat.status
        bot_status_lines.append(f"  <b>• Status:</b> {bot_current_status_str.capitalize()}")
        if bot_current_status_str == "administrator":
            bot_status_lines.append(f"  <b>• Can invite users:</b> {'Yes' if bot_member_on_chat.can_invite_users else 'No'}")
            bot_status_lines.append(f"  <b>• Can restrict members:</b> {'Yes' if bot_member_on_chat.can_restrict_members else 'No'}")
            bot_status_lines.append(f"  <b>• Can pin messages:</b> {'Yes' if getattr(bot_member_on_chat, 'can_pin_messages', None) else 'No'}")
            bot_status_lines.append(f"  <b>• Can manage chat:</b> {'Yes' if getattr(bot_member_on_chat, 'can_manage_chat', None) else 'No'}")
        else:
            bot_status_lines.append("  <b>• Note:</b> Bot is not an admin here.")
    except TelegramError as e:
        if "user not found" in str(e).lower() or "member not found" in str(e).lower():
             bot_status_lines.append("  <b>• Status:</b> Not a member")
        else:
            bot_status_lines.append(f"  <b>• Error fetching bot status:</b> {html.escape(str(e))}")
    except Exception as e:
        bot_status_lines.append("  <b>• Unexpected error fetching bot status.")
        logger.error(f"Unexpected error getting bot status in {target_chat_id}: {e}", exc_info=True)
    info_lines.append("\n".join(bot_status_lines))
    
    chat_permissions = getattr(chat_object_for_details, 'permissions', None)
    if chat_permissions:
        perms = chat_permissions
        perm_lines = ["\n<b>• Default Member Permissions:</b>"]
        perm_lines.append(f"  <b>• Send Messages:</b> {'Yes' if getattr(perms, 'can_send_messages', False) else 'No'}")
        
        can_send_any_media = (
            getattr(perms, 'can_send_audios', False) or
            getattr(perms, 'can_send_documents', False) or
            getattr(perms, 'can_send_photos', False) or 
            getattr(perms, 'can_send_videos', False) or
            getattr(perms, 'can_send_video_notes', False) or
            getattr(perms, 'can_send_voice_notes', False) or
            getattr(perms, 'can_send_media_messages', False)
        )
        perm_lines.append(f"  <b>• Send Media:</b> {'Yes' if can_send_any_media else 'No'}")
        perm_lines.append(f"  <b>• Send Polls:</b> {'Yes' if getattr(perms, 'can_send_polls', False) else 'No'}")
        perm_lines.append(f"  <b>• Send Other Messages:</b> {'Yes' if getattr(perms, 'can_send_other_messages', False) else 'No'}")
        perm_lines.append(f"  <b>• Add Web Page Previews:</b> {'Yes' if getattr(perms, 'can_add_web_page_previews', False) else 'No'}")
        perm_lines.append(f"  <b>• Change Info:</b> {'Yes' if getattr(perms, 'can_change_info', False) else 'No'}")
        perm_lines.append(f"  <b>• Invite Users:</b> {'Yes' if getattr(perms, 'can_invite_users', False) else 'No'}")
        perm_lines.append(f"  <b>• Pin Messages:</b> {'Yes' if getattr(perms, 'can_pin_messages', False) else 'No'}")
        if hasattr(perms, 'can_manage_topics'):
            perm_lines.append(f"  <b>• Manage Topics:</b> {'Yes' if perms.can_manage_topics else 'No'}")
        info_lines.extend(perm_lines)

    message_text = "\n".join(info_lines)
    await update.message.reply_html(message_text, disable_web_page_preview=True)

def run_speed_test_blocking():
    try:
        logger.info("Starting blocking speed test...")
        s = speedtest.Speedtest()
        s.get_best_server()
        logger.info("Getting download speed...")
        s.download()
        logger.info("Getting upload speed...")
        s.upload()
        results_dict = s.results.dict()
        logger.info("Speed test finished successfully (blocking part).")
        return results_dict
    except speedtest.ConfigRetrievalError as e:
        logger.error(f"Speedtest config retrieval error: {e}")
        return {"error": f"Config retrieval error: {str(e)}"}
    except speedtest.NoMatchedServers as e:
        logger.error(f"Speedtest no matched servers: {e}")
        return {"error": f"No suitable test servers found: {str(e)}"}
    except Exception as e:
        logger.error(f"General error during blocking speedtest function: {e}", exc_info=True)
        return {"error": f"A general error occurred during test: {type(e).__name__}"}

async def speedtest_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id != OWNER_ID:
        logger.warning(f"Unauthorized /speedtest attempt by user {user.id}.")
        return

    message = await update.message.reply_text("Meeeow! Starting speed test... this might take a moment 🐾💨")
    
    loop = asyncio.get_event_loop()
    try:
        results = await loop.run_in_executor(None, run_speed_test_blocking)
        await asyncio.sleep(4)

        if results and "error" not in results:
            ping_val = results.get("ping", 0.0)
            download_bps = results.get("download", 0)
            upload_bps = results.get("upload", 0)
            
            download_mbps_val = download_bps / 1000 / 1000
            upload_mbps_val = upload_bps / 1000 / 1000

            bytes_sent_val = results.get("bytes_sent", 0)
            bytes_received_val = results.get("bytes_received", 0)
            data_sent_mb_val = bytes_sent_val / 1024 / 1024
            data_received_mb_val = bytes_received_val / 1024 / 1024
            
            timestamp_str_val = results.get("timestamp", "N/A")
            formatted_time_val = "N/A"
            if timestamp_str_val != "N/A":
                try:
                    dt_obj = datetime.fromisoformat(timestamp_str_val.replace("Z", "+00:00"))
                    formatted_time_val = dt_obj.strftime('%Y-%m-%d %H:%M:%S %Z') 
                except ValueError:
                    formatted_time_val = html.escape(timestamp_str_val)

            server_info_dict = results.get("server", {})
            server_name_val = server_info_dict.get("name", "N/A")
            server_country_val = server_info_dict.get("country", "N/A")
            server_cc_val = server_info_dict.get("cc", "N/A")
            server_sponsor_val = server_info_dict.get("sponsor", "N/A")
            server_lat_val = server_info_dict.get("lat", "N/A")
            server_lon_val = server_info_dict.get("lon", "N/A")

            info_lines = [
                "<b>🌐 Ookla SPEEDTEST:</b>\n",
                "<b>📊 RESULTS:</b>",
                f" <b>• 📤 Upload:</b> <code>{upload_mbps_val:.2f} Mbps</code>",
                f" <b>• 📥 Download:</b> <code>{download_mbps_val:.2f} Mbps</code>",
                f" <b>• ⏳️ Ping:</b> <code>{ping_val:.2f} ms</code>",
                f" <b>• 🕒 Time:</b> <code>{formatted_time_val}</code>",
                f" <b>• 📨 Data Sent:</b> <code>{data_sent_mb_val:.2f} MB</code>",
                f" <b>• 📩 Data Received:</b> <code>{data_received_mb_val:.2f} MB</code>\n",
                "<b>🖥 SERVER INFO:</b>",
                f" <b>• 🪪 Name:</b> <code>{html.escape(server_name_val)}</code>",
                f" <b>• 🌍 Country:</b> <code>{html.escape(server_country_val)} ({html.escape(server_cc_val)})</code>",
                f" <b>• 🛠 Sponsor:</b> <code>{html.escape(server_sponsor_val)}</code>",
                f" <b>• 🧭 Latitude:</b> <code>{server_lat_val}</code>",
                f" <b>• 🧭 Longitude:</b> <code>{server_lon_val}</code>"
            ]
            
            result_message = "\n".join(info_lines)
            await context.bot.edit_message_text(chat_id=message.chat_id, message_id=message.message_id, text=result_message, parse_mode=ParseMode.HTML)
        
        elif results and "error" in results:
            error_msg = results["error"]
            await context.bot.edit_message_text(chat_id=message.chat_id, message_id=message.message_id, text=f"😿 Mrow! Speed test failed: {html.escape(error_msg)}")
        else:
            await context.bot.edit_message_text(chat_id=message.chat_id, message_id=message.message_id, text="😿 Mrow! Speed test failed to return results or returned an unexpected format.")

    except Exception as e:
        logger.error(f"Error in speedtest_command outer try-except: {e}", exc_info=True)
        try:
            await context.bot.edit_message_text(chat_id=message.chat_id, message_id=message.message_id, text=f"💥 An unexpected error occurred during the speed test: {html.escape(str(e))}")
        except Exception:
            pass
    
async def leave_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id != OWNER_ID:
        logger.warning(f"Unauthorized /leave attempt by user {user.id}.")
        return

    target_chat_id_to_leave: int | None = None
    chat_where_command_was_called_id = update.effective_chat.id
    is_leaving_current_chat = False

    if context.args:
        try:
            target_chat_id_to_leave = int(context.args[0])
            if target_chat_id_to_leave >= -100:
                await update.message.reply_text("Mrow? Invalid Group/Channel ID format for leaving.")
                return
            logger.info(f"Privileged user {user.id} initiated remote leave for chat ID: {target_chat_id_to_leave}")
            if target_chat_id_to_leave == chat_where_command_was_called_id:
                is_leaving_current_chat = True
        except (ValueError, IndexError):
            await update.message.reply_text("Mrow? Invalid chat ID format for leaving.")
            return
    else:
        if update.effective_chat.type == ChatType.PRIVATE:
            await update.message.reply_text("Meow! I can't leave a private chat with you.")
            return
        target_chat_id_to_leave = update.effective_chat.id
        is_leaving_current_chat = True
        logger.info(f"Privileged user {user.id} initiated leave for current chat: {target_chat_id_to_leave}")

    if target_chat_id_to_leave is None:
        await update.message.reply_text("Mrow? Could not determine which chat to leave.")
        return

    owner_mention_for_farewell = f"<code>{OWNER_ID}</code>"
    try:
        owner_chat_info = await context.bot.get_chat(OWNER_ID)
        owner_mention_for_farewell = owner_chat_info.mention_html()
    except Exception as e:
        logger.warning(f"Could not fetch owner mention for /leave farewell message: {e}")

    chat_title_to_leave = f"Chat ID {target_chat_id_to_leave}"
    safe_chat_title_to_leave = chat_title_to_leave
    
    try:
        target_chat_info = await context.bot.get_chat(target_chat_id_to_leave)
        chat_title_to_leave = target_chat_info.title or target_chat_info.first_name or f"Chat ID {target_chat_id_to_leave}"
        safe_chat_title_to_leave = html.escape(chat_title_to_leave)
    except TelegramError as e:
        logger.error(f"Could not get chat info for {target_chat_id_to_leave} before leaving: {e}")
        reply_to_chat_id_for_error = chat_where_command_was_called_id
        if is_leaving_current_chat and OWNER_ID: reply_to_chat_id_for_error = OWNER_ID
        
        error_message_text = f"❌ Cannot interact with chat <b>{safe_chat_title_to_leave}</b> (<code>{target_chat_id_to_leave}</code>): {html.escape(str(e))}. I might not be a member there."
        if "bot is not a member" in str(e).lower() or "chat not found" in str(e).lower():
            pass 
        else:
            error_message_text = f"⚠️ Couldn't get chat info for <code>{target_chat_id_to_leave}</code>: {html.escape(str(e))}. Will attempt to leave anyway."
        
        if reply_to_chat_id_for_error:
            try: await context.bot.send_message(chat_id=reply_to_chat_id_for_error, text=error_message_text, parse_mode=ParseMode.HTML)
            except Exception as send_err: logger.error(f"Failed to send error about get_chat to {reply_to_chat_id_for_error}: {send_err}")
        if "bot is not a member" in str(e).lower() or "chat not found" in str(e).lower(): return
        
    except Exception as e:
         logger.error(f"Unexpected error getting chat info for {target_chat_id_to_leave}: {e}", exc_info=True)
         reply_to_chat_id_for_error = chat_where_command_was_called_id
         if is_leaving_current_chat and OWNER_ID: reply_to_chat_id_for_error = OWNER_ID
         if reply_to_chat_id_for_error:
             try: await context.bot.send_message(chat_id=reply_to_chat_id_for_error, text=f"⚠️ Unexpected error getting chat info for <code>{target_chat_id_to_leave}</code>. Will attempt to leave anyway.", parse_mode=ParseMode.HTML)
             except Exception as send_err: logger.error(f"Failed to send error about get_chat to {reply_to_chat_id_for_error}: {send_err}")

    if LEAVE_TEXTS:
        farewell_message = random.choice(LEAVE_TEXTS).format(owner_mention=owner_mention_for_farewell, chat_title=f"<b>{safe_chat_title_to_leave}</b>")
        try:
            await context.bot.send_message(chat_id=target_chat_id_to_leave, text=farewell_message, parse_mode=ParseMode.HTML)
            logger.info(f"Sent farewell message to {target_chat_id_to_leave}")
        except TelegramError as e:
            logger.error(f"Failed to send farewell message to {target_chat_id_to_leave}: {e}.")
            if "forbidden: bot is not a member" in str(e).lower() or "chat not found" in str(e).lower():
                logger.warning(f"Bot is not a member of {target_chat_id_to_leave} or chat not found. Cannot send farewell.")
                reply_to_chat_id_for_error = chat_where_command_was_called_id
                if is_leaving_current_chat and OWNER_ID: reply_to_chat_id_for_error = OWNER_ID
                if reply_to_chat_id_for_error:
                    try: await context.bot.send_message(chat_id=reply_to_chat_id_for_error, text=f"❌ Failed to send farewell to <b>{safe_chat_title_to_leave}</b> (<code>{target_chat_id_to_leave}</code>): {html.escape(str(e))}. Bot is not a member.", parse_mode=ParseMode.HTML)
                    except Exception as send_err: logger.error(f"Failed to send error about farewell to {reply_to_chat_id_for_error}: {send_err}")
                return 
        except Exception as e:
             logger.error(f"Unexpected error sending farewell message to {target_chat_id_to_leave}: {e}", exc_info=True)
    elif not LEAVE_TEXTS:
        logger.warning("LEAVE_TEXTS list is empty! Skipping farewell message.")

    try:
        success = await context.bot.leave_chat(chat_id=target_chat_id_to_leave)
        
        confirmation_target_chat_id = chat_where_command_was_called_id
        if is_leaving_current_chat:
            if OWNER_ID:
                confirmation_target_chat_id = OWNER_ID
            else:
                confirmation_target_chat_id = None 

        if success:
            logger.info(f"Successfully left chat {target_chat_id_to_leave} ('{chat_title_to_leave}')")
            if confirmation_target_chat_id:
                await context.bot.send_message(chat_id=confirmation_target_chat_id, 
                                               text=f"✅ Successfully left chat: <b>{safe_chat_title_to_leave}</b> (<code>{target_chat_id_to_leave}</code>)", 
                                               parse_mode=ParseMode.HTML)
        else:
            logger.warning(f"leave_chat returned False for {target_chat_id_to_leave}. Bot might not have been a member.")
            if confirmation_target_chat_id:
                await context.bot.send_message(chat_id=confirmation_target_chat_id,
                                               text=f"🤔 Attempted to leave <b>{safe_chat_title_to_leave}</b> (<code>{target_chat_id_to_leave}</code>), but the operation indicated I might not have been there or lacked permission.", 
                                               parse_mode=ParseMode.HTML)
    except TelegramError as e:
        logger.error(f"Failed to leave chat {target_chat_id_to_leave}: {e}")
        confirmation_target_chat_id = chat_where_command_was_called_id
        if is_leaving_current_chat:
            if OWNER_ID: confirmation_target_chat_id = OWNER_ID
            else: confirmation_target_chat_id = None
        if confirmation_target_chat_id:
            await context.bot.send_message(chat_id=confirmation_target_chat_id,
                                           text=f"❌ Failed to leave chat <b>{safe_chat_title_to_leave}</b> (<code>{target_chat_id_to_leave}</code>): {html.escape(str(e))}", 
                                           parse_mode=ParseMode.HTML)
    except Exception as e:
         logger.error(f"Unexpected error during leave process for {target_chat_id_to_leave}: {e}", exc_info=True)
         confirmation_target_chat_id = chat_where_command_was_called_id
         if is_leaving_current_chat:
            if OWNER_ID: confirmation_target_chat_id = OWNER_ID
            else: confirmation_target_chat_id = None
         if confirmation_target_chat_id:
            await context.bot.send_message(chat_id=confirmation_target_chat_id,
                                           text=f"💥 Unexpected error leaving chat <b>{safe_chat_title_to_leave}</b> (<code>{target_chat_id_to_leave}</code>). Check logs.", 
                                           parse_mode=ParseMode.HTML)

# Handler for welcoming the owner when they join a group and send log to pm
async def handle_new_group_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles both owner joining and bot joining events in groups."""
    if not update.message or not update.message.new_chat_members:
        return

    chat = update.effective_chat
    bot_id = context.bot.id

    for member in update.message.new_chat_members:
        if OWNER_ID and member.id == OWNER_ID:
            logger.info(f"Owner {OWNER_ID} joined chat {chat.id} ('{chat.title}')")
            owner_mention = member.mention_html()
            if OWNER_WELCOME_TEXTS:
                 welcome_text = random.choice(OWNER_WELCOME_TEXTS).format(owner_mention=owner_mention)
                 try:
                     await update.message.reply_html(welcome_text)
                 except TelegramError as e:
                     logger.error(f"Failed to send owner welcome message to {chat.id}: {e}")
                 except Exception as e:
                     logger.error(f"Unexpected error sending owner welcome to {chat.id}: {e}", exc_info=True)
            else:
                 logger.warning("OWNER_WELCOME_TEXTS list is empty!")

        elif member.id == bot_id:
            logger.info(f"!!! Handler detected BOT ({bot_id}) joined chat {chat.id} !!!")
            chat_id = chat.id
            chat_title = chat.title or f"[Chat without title, ID: {chat_id}]"
            safe_chat_title = html.escape(chat_title)
            chat_username = chat.username
            link_line = ""
            log_message = f"Bot added to Group: '{chat_title}' (ID: {chat_id})"

            if chat_username:
                log_message += f" @{chat_username}"
                link_line = f"\n<b>Link:</b> https://t.me/{chat_username}"
                logger.info(log_message + " (Public)")
            else:
                log_message += " (Private/No Username)"
                logger.info(log_message)
                try:
                    bot_member = await context.bot.get_chat_member(chat_id=chat_id, user_id=bot_id)
                    if bot_member.status == ChatMemberStatus.ADMINISTRATOR and bot_member.can_invite_users:
                        logger.info(f"Bot is admin with invite rights in {chat_id}. Creating link.")
                        try:
                            invite_link_object = await context.bot.create_chat_invite_link(chat_id=chat_id)
                            link_line = f"\n<b>Invite Link:</b> {invite_link_object.invite_link}"
                            logger.info(f"Created invite link for {chat_id}.")
                        except TelegramError as invite_err: logger.error(f"Failed to create invite link: {invite_err}"); link_line = f"\n<b>Note:</b> Private, failed invite link ({invite_err})."
                        except Exception as invite_exc: logger.error(f"Unexpected error creating invite link: {invite_exc}", exc_info=True); link_line = "\n<b>Note:</b> Private, error creating invite link."
                    else: logger.info(f"Bot not admin with rights in {chat_id}. Status: {bot_member.status}, Can Invite: {getattr(bot_member, 'can_invite_users', 'N/A')}")
                except TelegramError as member_err: logger.error(f"Could not get bot status in {chat_id}: {member_err}"); link_line = f"\n<b>Note:</b> Private, couldn't check permissions ({member_err})."
                except Exception as member_exc: logger.error(f"Unexpected error checking bot status: {member_exc}", exc_info=True); link_line = "\n<b>Note:</b> Private, error checking permissions."

            if OWNER_ID:
                logger.info(f"!!! Attempting PM to OWNER_ID: {OWNER_ID} !!!")
                try:
                    pm_text = (f"<b>#ADDEDTOGROUP</b>\n\n<b>Name:</b> {safe_chat_title}\n<b>ID:</b> <code>{chat_id}</code>{link_line}")
                    await context.bot.send_message(chat_id=OWNER_ID, text=pm_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
                    logger.info(f"Sent join notification to owner ({OWNER_ID}) for group {chat_id}.")
                except Exception as e:
                    logger.error(f"!!! FAILED to send PM to owner ({OWNER_ID}) for group {chat_id}: {e} !!!", exc_info=True)
            else:
                logger.warning("OWNER_ID not set, cannot send join notification.")

async def send_operational_log(context: ContextTypes.DEFAULT_TYPE, message: str, parse_mode: str = ParseMode.HTML) -> None:
    """
    Sends an operational log message to LOG_CHAT_ID if configured,
    otherwise falls back to OWNER_ID.
    """
    target_id_for_log = LOG_CHAT_ID

    if not target_id_for_log and OWNER_ID:
        target_id_for_log = OWNER_ID
        logger.info("LOG_CHAT_ID not set, sending operational log to OWNER_ID.")
    elif not target_id_for_log and not OWNER_ID:
        logger.error("Neither LOG_CHAT_ID nor OWNER_ID are set. Cannot send operational log.")
        return

    if target_id_for_log:
        try:
            await context.bot.send_message(chat_id=target_id_for_log, text=message, parse_mode=parse_mode)
            logger.info(f"Sent operational log to chat_id: {target_id_for_log}")
        except TelegramError as e:
            logger.error(f"Failed to send operational log to {target_id_for_log}: {e}")
            if LOG_CHAT_ID and target_id_for_log == LOG_CHAT_ID and OWNER_ID and LOG_CHAT_ID != OWNER_ID:
                logger.info(f"Falling back to send operational log to OWNER_ID ({OWNER_ID}) after failure with LOG_CHAT_ID.")
                try:
                    await context.bot.send_message(chat_id=OWNER_ID, text=f"[Fallback from LogChat]\n{message}", parse_mode=parse_mode)
                    logger.info(f"Sent operational log to OWNER_ID as fallback.")
                except Exception as e_owner:
                    logger.error(f"Failed to send operational log to OWNER_ID as fallback: {e_owner}")
        except Exception as e:
            logger.error(f"Unexpected error sending operational log to {target_id_for_log}: {e}", exc_info=True)

# --- Blacklist Commands ---
async def blacklist_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_privileged_user(user.id):
        logger.warning(f"Unauthorized /blacklist attempt by user {user.id}.")
        return

    target_user_obj: User | None = None
    reason = "No reason provided."
    target_input_str: str | None = None

    if update.message.reply_to_message:
        replied_user = update.message.reply_to_message.from_user
        if replied_user:
            target_user_obj = replied_user
        else:
            await update.message.reply_text("Mrow? Please reply to a user's message to blacklist them.")
            return
        if context.args:
            reason = " ".join(context.args)
    elif context.args:
        target_input_str = context.args[0]
        
        if target_input_str.startswith("@"):
            username_to_find = target_input_str[1:]
            target_user_obj = get_user_from_db_by_username(username_to_find)
            if not target_user_obj:
                logger.info(f"Blacklist target @{username_to_find} not in DB, trying API to confirm user.")
                try: 
                    chat_info = await context.bot.get_chat(target_input_str)
                    if chat_info.type == ChatType.PRIVATE:
                        target_user_obj = User(id=chat_info.id, first_name=chat_info.first_name or f"User? ({target_input_str})", is_bot=getattr(chat_info, 'is_bot', False), username=chat_info.username, last_name=chat_info.last_name)
                        if target_user_obj: update_user_in_db(target_user_obj)
                    else:
                        await update.message.reply_text(f"Mrow? @{username_to_find} resolved to a {chat_info.type}. Blacklist can only be applied to users.")
                        return
                except TelegramError:
                    await update.message.reply_text(f"Mrow? Could not find user @{html.escape(username_to_find)} via API. Try ID or reply.")
                    return
                except Exception as e:
                    logger.error(f"Unexpected error for @{username_to_find} in blacklist: {e}", exc_info=True)
                    await update.message.reply_text("Mrow? An error occurred while trying to find the user.")
                    return
            if target_user_obj and len(context.args) > 1:
                reason = " ".join(context.args[1:])
        else:
            try:
                target_id = int(target_input_str)
                try: 
                    chat_info = await context.bot.get_chat(target_id)
                    if chat_info.type == ChatType.PRIVATE:
                        target_user_obj = User(id=chat_info.id, first_name=chat_info.first_name or f"User {target_id}", is_bot=getattr(chat_info, 'is_bot', False), username=chat_info.username, last_name=chat_info.last_name)
                        if target_user_obj: update_user_in_db(target_user_obj)
                    else:
                         await update.message.reply_text(f"Mrow? ID {target_id} does not seem to be a user (type: {chat_info.type}). Blacklist can only be applied to users.")
                         return
                except TelegramError: 
                    logger.warning(f"Couldn't fully verify user ID {target_id} for blacklist. Creating minimal User object.")
                    target_user_obj = User(id=target_id, first_name=f"User {target_id}", is_bot=False)
                
                if len(context.args) > 1:
                    reason = " ".join(context.args[1:])
            except ValueError:
                await update.message.reply_text("Mrow? Invalid format. Use /blacklist <ID/@username> [reason] or reply.")
                return
    else:
        await update.message.reply_text("Mrow? Specify a user ID/@username (or reply to a message) to blacklist.")
        return

    if not target_user_obj:
        await update.message.reply_text("Mrow? Could not identify the user to blacklist.")
        return
    
    if not isinstance(target_user_obj, User) or getattr(target_user_obj, 'type', ChatType.PRIVATE) != ChatType.PRIVATE :
        await update.message.reply_text("Mrow? Blacklist can only be applied to individual users.")
        return

    if target_user_obj.id == OWNER_ID:
        await update.message.reply_text("Meow! I can't blacklist my Owner! That's just silly. 😹")
        return
    if target_user_obj.id == context.bot.id:
        await update.message.reply_text("Purr... I can't blacklist myself! That would be a cat-astrophe! 🙀")
        return
    if is_sudo_user(target_user_obj.id) and target_user_obj.id != OWNER_ID:
        user_display = target_user_obj.mention_html() if target_user_obj.username else html.escape(target_user_obj.first_name or str(target_user_obj.id))
        await update.message.reply_html(f"Meeeow! I cannot blacklist a Sudo user ({user_display}). Please remove their sudo access first using /delsudo if you wish to proceed.")
        return
    if target_user_obj.is_bot:
        await update.message.reply_text("Meeeow, I don't usually blacklist other bots.")
        return

    if is_user_blacklisted(target_user_obj.id):
        user_display = target_user_obj.mention_html() if target_user_obj.username else html.escape(target_user_obj.first_name or str(target_user_obj.id))
        await update.message.reply_html(f"User {user_display} (<code>{target_user_obj.id}</code>) is already on the blacklist.")
        return

    if add_to_blacklist(target_user_obj.id, user.id, reason):
        logger.info(f"Owner {user.id} blacklisted user {target_user_obj.id} (@{target_user_obj.username}). Reason: {reason}")
        user_display = target_user_obj.mention_html() if target_user_obj.username else html.escape(target_user_obj.first_name or str(target_user_obj.id))
        await update.message.reply_html(f"✅ User {user_display} (<code>{target_user_obj.id}</code>) has been added to the blacklist.\nReason: {html.escape(reason)}")
        
        try:
            current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            pm_message = (f"<b>#BLACKLISTED</b>\n\n<b>User:</b> {user_display} (<code>{target_user_obj.id}</code>)\n<b>Username:</b> @{html.escape(target_user_obj.username) if target_user_obj.username else 'N/A'}\n<b>Reason:</b> {html.escape(reason)}\n<b>Admin:</b> {user.mention_html()}\n<b>Date:</b> <code>{current_time}</code>")
            await send_operational_log(context, pm_message)
        except Exception as e:
            logger.error(f"Error preparing/sending #BLACKLISTED operational log: {e}", exc_info=True)
    else:
        await update.message.reply_text("Mrow? Failed to add user to the blacklist. Check logs.")


async def unblacklist_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_privileged_user(user.id):
        logger.warning(f"Unauthorized /unblacklist attempt by user {user.id}.")
        return

    target_user_obj: User | None = None
    target_input_str: str | None = None

    if update.message.reply_to_message:
        replied_user = update.message.reply_to_message.from_user
        if replied_user:
            target_user_obj = replied_user
        else:
            await update.message.reply_text("Mrow? Please reply to a user's message to unblacklist them.")
            return
    elif context.args:
        target_input_str = context.args[0]
        if target_input_str.startswith("@"):
            username_to_find = target_input_str[1:]
            target_user_obj = get_user_from_db_by_username(username_to_find)
            if not target_user_obj:
                try: 
                    chat_info = await context.bot.get_chat(target_input_str)
                    if chat_info.type == ChatType.PRIVATE:
                        target_user_obj = User(id=chat_info.id, first_name=chat_info.first_name or f"User? ({target_input_str})", is_bot=getattr(chat_info, 'is_bot', False), username=chat_info.username, last_name=chat_info.last_name)
                    else:
                        await update.message.reply_text(f"Mrow? @{username_to_find} resolved to a {chat_info.type}. Unblacklist can only be applied to users.")
                        return
                except TelegramError:
                    await update.message.reply_text(f"Mrow? Could not find user @{html.escape(username_to_find)} via API. Try ID or reply.")
                    return
                except Exception as e:
                    logger.error(f"Unexpected error for @{username_to_find} in unblacklist: {e}", exc_info=True)
                    await update.message.reply_text("Mrow? An error occurred while trying to find the user.")
                    return
        else:
            try:
                target_id = int(target_input_str)
                try: 
                    chat_info = await context.bot.get_chat(target_id)
                    if chat_info.type == ChatType.PRIVATE:
                        target_user_obj = User(id=chat_info.id, first_name=chat_info.first_name or f"User {target_id}", is_bot=getattr(chat_info, 'is_bot', False), username=chat_info.username, last_name=chat_info.last_name)
                    else:
                        logger.warning(f"Attempt to unblacklist non-user ID {target_id} (type: {chat_info.type}). Using ID directly.")
                        target_user_obj = User(id=target_id, first_name=f"User {target_id}", is_bot=False)
                except TelegramError: 
                    logger.warning(f"Couldn't fully verify user ID {target_id} for unblacklist. Using minimal User object.")
                    target_user_obj = User(id=target_id, first_name=f"User {target_id}", is_bot=False)
            except ValueError:
                await update.message.reply_text("Mrow? Invalid format. Use /unblacklist <ID/@username> or reply.")
                return
    else:
        await update.message.reply_text("Mrow? Specify a user ID/@username (or reply) to unblacklist.")
        return
        
    if not target_user_obj:
        await update.message.reply_text("Mrow? Could not identify the user to unblacklist.")
        return
    
    if not isinstance(target_user_obj, User) or getattr(target_user_obj, 'type', ChatType.PRIVATE) != ChatType.PRIVATE :
        await update.message.reply_text("Mrow? Unblacklist can only be applied to individual users.")
        return

    if target_user_obj.id == OWNER_ID:
        await update.message.reply_text("Meow! The Owner is never on the blacklist! 😉")
        return

    if not is_user_blacklisted(target_user_obj.id):
        user_display = target_user_obj.mention_html() if target_user_obj.username else html.escape(target_user_obj.first_name or str(target_user_obj.id))
        await update.message.reply_html(f"User {user_display} (<code>{target_user_obj.id}</code>) is not on the blacklist.")
        return

    if remove_from_blacklist(target_user_obj.id):
        logger.info(f"Owner {user.id} unblacklisted user {target_user_obj.id} (@{target_user_obj.username}).")
        user_display = target_user_obj.mention_html() if target_user_obj.username else html.escape(target_user_obj.first_name or str(target_user_obj.id))
        await update.message.reply_html(f"✅ User {user_display} (<code>{target_user_obj.id}</code>) has been removed from the blacklist.")
        
        try:
            current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            log_message_to_send = (f"<b>#UNBLACKLISTED</b>\n\n<b>User:</b> {user_display} (<code>{target_user_obj.id}</code>)\n<b>Username:</b> @{html.escape(target_user_obj.username) if target_user_obj.username else 'N/A'}\n<b>Admin:</b> {user.mention_html()}\n<b>Date:</b> <code>{current_time}</code>")
            await send_operational_log(context, log_message_to_send)
        except Exception as e:
            logger.error(f"Error preparing/sending #UNBLACKLISTED operational log: {e}", exc_info=True)
    else:
        await update.message.reply_text("Mrow? Failed to remove user from the blacklist. Check logs.")

# --- Sudo commands ---
async def add_sudo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id != OWNER_ID:
        logger.warning(f"Unauthorized /addsudo attempt by user {user.id}.")
        return

    target_user_obj: User | None = None
    target_input_str: str | None = None

    if update.message.reply_to_message:
        replied_user = update.message.reply_to_message.from_user
        if replied_user:
            target_user_obj = replied_user
        else:
            await update.message.reply_text("Mrow? Please reply to a user's message to add them to sudo.")
            return
    elif context.args:
        target_input_str = context.args[0]
        
        if target_input_str.startswith("@"):
            username_to_find = target_input_str[1:]
            target_user_obj = get_user_from_db_by_username(username_to_find)
            if not target_user_obj:
                logger.info(f"Sudo target @{username_to_find} not in DB, trying API to confirm user.")
                try: 
                    chat_info = await context.bot.get_chat(target_input_str)
                    if chat_info.type == ChatType.PRIVATE:
                        target_user_obj = User(id=chat_info.id, first_name=chat_info.first_name or f"User? ({target_input_str})", is_bot=getattr(chat_info, 'is_bot', False), username=chat_info.username, last_name=chat_info.last_name)
                        if target_user_obj: update_user_in_db(target_user_obj)
                    else:
                        await update.message.reply_text(f"Mrow? @{username_to_find} resolved to a {chat_info.type}. Sudo can only be granted to users.")
                        return
                except TelegramError:
                    await update.message.reply_text(f"Mrow? Could not find user @{html.escape(username_to_find)} via API. Try ID or reply.")
                    return
                except Exception as e:
                    logger.error(f"Unexpected error for @{username_to_find} in addsudo: {e}", exc_info=True)
                    await update.message.reply_text("Mrow? An error occurred while trying to find the user.")
                    return
        else:
            try:
                target_id = int(target_input_str)
                try: 
                    chat_info = await context.bot.get_chat(target_id)
                    if chat_info.type == ChatType.PRIVATE:
                        target_user_obj = User(id=chat_info.id, first_name=chat_info.first_name or f"User {target_id}", is_bot=getattr(chat_info, 'is_bot', False), username=chat_info.username, last_name=chat_info.last_name)
                        if target_user_obj: update_user_in_db(target_user_obj)
                    else:
                         await update.message.reply_text(f"Mrow? ID {target_id} does not seem to be a user (type: {chat_info.type}). Sudo can only be granted to users.")
                         return
                except TelegramError: 
                    logger.warning(f"Couldn't fully verify user ID {target_id} for addsudo. Creating minimal User object.")
                    target_user_obj = User(id=target_id, first_name=f"User {target_id}", is_bot=False)
            except ValueError:
                await update.message.reply_text("Mrow? Invalid format. Use /addsudo <ID/@username> or reply.")
                return
    else:
        await update.message.reply_text("Mrow? Specify a user ID/@username (or reply to a message) to add to sudo.")
        return

    if not target_user_obj:
        await update.message.reply_text("Mrow? Could not identify the user to add to sudo.")
        return
    
    if not isinstance(target_user_obj, User) or getattr(target_user_obj, 'type', ChatType.PRIVATE) != ChatType.PRIVATE :
        await update.message.reply_text("Mrow? Sudo privileges can only be granted to individual users, not channels or groups.")
        return

    if target_user_obj.id == OWNER_ID:
        await update.message.reply_text("Meow! My Owner already has ultimate power and is implicitly sudo! 😼")
        return
    if target_user_obj.id == context.bot.id:
        await update.message.reply_text("Purr... I can't sudo myself, that's a paradox I'm not programmed for!")
        return
    if target_user_obj.is_bot:
        await update.message.reply_text("Meeeow, I don't think other bots need sudo access. Let's keep it for humans. 🤖")
        return

    if is_sudo_user(target_user_obj.id):
        user_display = target_user_obj.mention_html() if target_user_obj.username else html.escape(target_user_obj.first_name or str(target_user_obj.id))
        await update.message.reply_html(f"User {user_display} (<code>{target_user_obj.id}</code>) already has sudo powers.")
        return

    if add_sudo_user(target_user_obj.id, user.id):
        logger.info(f"Owner {user.id} added sudo user {target_user_obj.id} (@{target_user_obj.username})")
        user_display = target_user_obj.mention_html() if target_user_obj.username else html.escape(target_user_obj.first_name or str(target_user_obj.id))
        await update.message.reply_html(f"✅ User {user_display} (<code>{target_user_obj.id}</code>) has been granted sudo powers!")
        
        if target_user_obj.id != OWNER_ID:
             try: await context.bot.send_message(target_user_obj.id, "Meeeow! You have been granted sudo privileges by my Owner! Use them wisely. 🐾")
             except Exception as e: logger.warning(f"Failed to send PM to new sudo user {target_user_obj.id}: {e}")
        
        try:
            current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            log_message_to_send = (
                f"<b>#SUDO</b>\n\n"
                f"<b>User:</b> {user_display} (<code>{target_user_obj.id}</code>)\n"
                f"<b>Username:</b> @{html.escape(target_user_obj.username) if target_user_obj.username else 'N/A'}\n"
                f"<b>Date:</b> <code>{current_time}</code>"
            )
            await send_operational_log(context, log_message_to_send)
        except Exception as e:
            logger.error(f"Error preparing/sending #SUDO_ADDED operational log: {e}", exc_info=True)
    else:
        await update.message.reply_text("Mrow? Failed to add user to sudo list. Check logs.")


async def del_sudo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id != OWNER_ID:
        logger.warning(f"Unauthorized /delsudo attempt by user {user.id}.")
        return

    target_user_obj: User | None = None
    target_input_str: str | None = None

    if update.message.reply_to_message:
        replied_user = update.message.reply_to_message.from_user
        if replied_user:
            target_user_obj = replied_user
        else:
            await update.message.reply_text("Mrow? Please reply to a user's message to remove their sudo.")
            return
    elif context.args:
        target_input_str = context.args[0]
        if target_input_str.startswith("@"):
            username_to_find = target_input_str[1:]
            target_user_obj = get_user_from_db_by_username(username_to_find)
            if not target_user_obj:
                try: 
                    chat_info = await context.bot.get_chat(target_input_str)
                    if chat_info.type == ChatType.PRIVATE:
                        target_user_obj = User(id=chat_info.id, first_name=chat_info.first_name or f"User? ({target_input_str})", is_bot=getattr(chat_info, 'is_bot', False), username=chat_info.username, last_name=chat_info.last_name)
                    else:
                        await update.message.reply_text(f"Mrow? @{username_to_find} resolved to a {chat_info.type}. Sudo can only be managed for users.")
                        return
                except TelegramError:
                    await update.message.reply_text(f"Mrow? Could not find user @{html.escape(username_to_find)} via API. Try ID or reply.")
                    return
                except Exception as e:
                    logger.error(f"Unexpected error for @{username_to_find} in delsudo: {e}", exc_info=True)
                    await update.message.reply_text("Mrow? An error occurred while trying to find the user.")
                    return
        else:
            try:
                target_id = int(target_input_str)
                try: 
                    chat_info = await context.bot.get_chat(target_id)
                    if chat_info.type == ChatType.PRIVATE:
                        target_user_obj = User(id=chat_info.id, first_name=chat_info.first_name or f"User {target_id}", is_bot=getattr(chat_info, 'is_bot', False), username=chat_info.username, last_name=chat_info.last_name)
                    else:
                         await update.message.reply_text(f"Mrow? ID {target_id} does not seem to be a user (type: {chat_info.type}). Sudo can only be managed for users.")
                         return
                except TelegramError: 
                    logger.warning(f"Couldn't fully verify user ID {target_id} for delsudo. Using minimal User object.")
                    target_user_obj = User(id=target_id, first_name=f"User {target_id}", is_bot=False)
            except ValueError:
                await update.message.reply_text("Mrow? Invalid format. Use /delsudo <ID/@username> or reply.")
                return
    else:
        await update.message.reply_text("Mrow? Specify a user ID/@username (or reply) to remove from sudo.")
        return
        
    if not target_user_obj:
        await update.message.reply_text("Mrow? Could not identify the user to remove from sudo.")
        return
    
    if not isinstance(target_user_obj, User) or getattr(target_user_obj, 'type', ChatType.PRIVATE) != ChatType.PRIVATE :
        await update.message.reply_text("Mrow? Sudo privileges can only be managed for individual users.")
        return

    if target_user_obj.id == OWNER_ID:
        await update.message.reply_text("Meow! The Owner's powers are inherent and cannot be revoked this way! 😉")
        return
    
    if not is_sudo_user(target_user_obj.id):
        user_display = target_user_obj.mention_html() if target_user_obj.username else html.escape(target_user_obj.first_name or str(target_user_obj.id))
        await update.message.reply_html(f"User {user_display} (<code>{target_user_obj.id}</code>) does not have sudo powers.")
        return

    if remove_sudo_user(target_user_obj.id):
        logger.info(f"Owner {user.id} removed sudo for user {target_user_obj.id} (@{target_user_obj.username})")
        user_display = target_user_obj.mention_html() if target_user_obj.username else html.escape(target_user_obj.first_name or str(target_user_obj.id))
        await update.message.reply_html(f"✅ Sudo powers for user {user_display} (<code>{target_user_obj.id}</code>) have been revoked.")
        
        try: await context.bot.send_message(target_user_obj.id, "Meeeow... Your sudo privileges have been revoked by my Owner.")
        except Exception as e: logger.warning(f"Failed to send PM to revoked sudo user {target_user_obj.id}: {e}")

        try:
            current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            log_message_to_send = (
                f"<b>#UNSUDO</b>\n\n"
                f"<b>User:</b> {user_display} (<code>{target_user_obj.id}</code>)\n"
                f"<b>Username:</b> @{html.escape(target_user_obj.username) if target_user_obj.username else 'N/A'}\n"
                f"<b>Date:</b> <code>{current_time}</code>"
            )
            await send_operational_log(context, log_message_to_send)
        except Exception as e:
            logger.error(f"Error preparing/sending #SUDO_REMOVED operational log: {e}", exc_info=True)
    else:
        await update.message.reply_text("Mrow? Failed to remove user from sudo list. Check logs.")
        
async def list_sudo_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id != OWNER_ID:
        logger.warning(f"Unauthorized /listsudo attempt by user {user.id}.")
        return

    sudo_user_tuples = get_all_sudo_users_from_db()

    if not sudo_user_tuples:
        await update.message.reply_text("Meeeow! There are currently no users with sudo privileges. 😼")
        return

    response_lines = ["<b>🛡️ Sudo Users List:</b>\n"]
    
    for user_id, timestamp_str in sudo_user_tuples:
        user_display_name = f"<code>{user_id}</code>"
        user_obj_from_db = get_user_from_db_by_username(str(user_id))

        if user_obj_from_db:
            display_name_parts = []
            if user_obj_from_db.first_name: display_name_parts.append(html.escape(user_obj_from_db.first_name))
            if user_obj_from_db.last_name: display_name_parts.append(html.escape(user_obj_from_db.last_name))
            if user_obj_from_db.username: display_name_parts.append(f"(@{html.escape(user_obj_from_db.username)})")
            
            if display_name_parts:
                user_display_name = " ".join(display_name_parts) + f" (<code>{user_id}</code>)"
            else:
                user_display_name = f"User (<code>{user_id}</code>)"
        else:
            try:
                chat_info = await context.bot.get_chat(user_id)
                name_parts = []
                if chat_info.first_name: name_parts.append(html.escape(chat_info.first_name))
                if chat_info.last_name: name_parts.append(html.escape(chat_info.last_name))
                if chat_info.username: name_parts.append(f"(@{html.escape(chat_info.username)})")
                
                if name_parts:
                    user_display_name = " ".join(name_parts) + f" (<code>{user_id}</code>)"
            except Exception:
                pass

        formatted_added_time = timestamp_str
        try:
            dt_obj = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            formatted_added_time = dt_obj.strftime('%Y-%m-%d %H:%M')
        except ValueError:
            logger.warning(f"Could not parse timestamp '{timestamp_str}' for sudo user {user_id}")
            pass

        response_lines.append(f"• {user_display_name}\n<b>Added:</b> <code>{formatted_added_time}</code>\n")

    message_text = "\n".join(response_lines)
    if len(message_text) > 4000:
        message_text = "\n".join(response_lines[:15])
        message_text += f"\n\n...and {len(sudo_user_tuples) - 15} more (list too long to display fully)."
        logger.info(f"Sudo list too long, truncated for display. Total: {len(sudo_user_tuples)}")

    await update.message.reply_html(message_text)

# --- Main Function ---
def main() -> None:
    init_db()
    logger.info("Initializing bot application...")
    application = Application.builder().token(BOT_TOKEN).build()

    connect_timeout_val = 20.0
    read_timeout_val = 80.0
    write_timeout_val = 80.0
    pool_timeout_val = 20.0

    custom_request_settings = HTTPXRequest(
        connect_timeout=connect_timeout_val,
        read_timeout=read_timeout_val,
        write_timeout=write_timeout_val,
        pool_timeout=pool_timeout_val
    )
    application = Application.builder().token(BOT_TOKEN).request(custom_request_settings).build()
    logger.info(f"Custom request timeouts set for HTTPXRequest: "
                f"Connect={connect_timeout_val}, Read={read_timeout_val}, "
                f"Write={write_timeout_val}, Pool={pool_timeout_val}")
    
    logger.info("Registering blacklist check handler...")
    application.add_handler(MessageHandler(filters.COMMAND, check_blacklist_handler), group=-1)

    logger.info("Registering user interaction logging handler...")
    application.add_handler(MessageHandler(
        filters.ALL & (~filters.UpdateType.EDITED_MESSAGE),
        log_user_from_interaction
    ), group=10)

    logger.info("Registering command handlers...")
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("github", github))
    application.add_handler(CommandHandler("owner", owner_info))
    application.add_handler(CommandHandler("info", entity_info_command))
    application.add_handler(CommandHandler("chatstat", chat_stat_command))
    application.add_handler(CommandHandler("cinfo", chat_info_command))
    application.add_handler(CommandHandler("gif", gif))
    application.add_handler(CommandHandler("photo", photo))
    application.add_handler(CommandHandler("meow", meow))
    application.add_handler(CommandHandler("nap", nap))
    application.add_handler(CommandHandler("play", play))
    application.add_handler(CommandHandler("treat", treat))
    application.add_handler(CommandHandler("zoomies", zoomies))
    application.add_handler(CommandHandler("judge", judge))
    application.add_handler(CommandHandler("fed", fed))
    application.add_handler(CommandHandler("attack", attack))
    application.add_handler(CommandHandler("kill", kill))
    application.add_handler(CommandHandler("punch", punch))
    application.add_handler(CommandHandler("slap", slap))
    application.add_handler(CommandHandler("bite", bite))
    application.add_handler(CommandHandler("hug", hug))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("say", say))
    application.add_handler(CommandHandler("leave", leave_chat))
    application.add_handler(CommandHandler("speedtest", speedtest_command))
    application.add_handler(CommandHandler("blist", blacklist_user_command))
    application.add_handler(CommandHandler("unblist", unblacklist_user_command))
    application.add_handler(CommandHandler("listsudo", list_sudo_users_command))
    application.add_handler(CommandHandler("addsudo", add_sudo_command))
    application.add_handler(CommandHandler("delsudo", del_sudo_command))

    logger.info("Registering message handlers for group joins...")
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS & filters.ChatType.GROUPS, handle_new_group_members))

    async def send_simple_startup_message(app: Application) -> None:
        startup_message_text = "<i>Bot Started...</i>"
        
        target_id_for_log = LOG_CHAT_ID
        if not target_id_for_log and OWNER_ID:
            target_id_for_log = OWNER_ID
        
        if target_id_for_log:
            try:
                await app.bot.send_message(chat_id=target_id_for_log, text=startup_message_text, parse_mode=ParseMode.HTML)
                logger.info(f"Sent simple startup notification to {target_id_for_log}.")
            except TelegramError as e:
                logger.error(f"Failed to send simple startup message to {target_id_for_log}: {e}")
                if LOG_CHAT_ID and target_id_for_log == LOG_CHAT_ID and OWNER_ID and LOG_CHAT_ID != OWNER_ID:
                    logger.info("Falling back to send simple startup message to OWNER_ID.")
                    try:
                        await app.bot.send_message(chat_id=OWNER_ID, text=f"[Fallback] {startup_message_text}", parse_mode=ParseMode.HTML)
                    except Exception as e_owner:
                         logger.error(f"Failed to send simple startup message to OWNER_ID as fallback: {e_owner}")
            except Exception as e_other:
                logger.error(f"Unexpected error sending simple startup message to {target_id_for_log}: {e_other}", exc_info=True)

        else:
            logger.warning("No target (LOG_CHAT_ID or OWNER_ID) to send simple startup message.")

    application.post_init = send_simple_startup_message

    logger.info(f"Bot starting polling... Owner ID configured: {OWNER_ID}")
    print(f"Bot starting polling... Owner ID: {OWNER_ID}")
    try: application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt: logger.info("Bot stopped by user (Ctrl+C)."); print("\nBot stopped by user.")
    except TelegramError as te: logger.critical(f"CRITICAL: TelegramError during polling: {te}"); print(f"\n--- FATAL TELEGRAM ERROR ---\n{te}"); exit(1)
    except Exception as e: logger.critical(f"CRITICAL: Bot crashed unexpectedly: {e}", exc_info=True); print(f"\n--- FATAL ERROR ---\nBot crashed: {e}"); exit(1)
    finally: logger.info("Bot shutdown process initiated."); print("Bot shutting down...")
    logger.info("Bot stopped."); print("Bot stopped.")

# --- Script Execution ---
if __name__ == "__main__":
    try: import requests
    except ImportError: print("\n--- DEPENDENCY ERROR ---\n'requests' required.\nPlease install: pip install requests"); exit(1)
    main()
