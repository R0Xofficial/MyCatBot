#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import random
import os
import datetime
from telegram import Update
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ApplicationHandlerStop
)

# --- Logging Setup ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# Reduce logging spam from underlying libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.vendor.ptb_urllib3.urllib3").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# --- Owner ID Configuration & Bot Start Time ---
OWNER_ID = None
BOT_START_TIME = datetime.datetime.now() # Record bot start time

try:
    # Fetch Owner ID from environment variable
    owner_id_str = ("TELEGRAM_OWNER_ID")
    if owner_id_str:
        OWNER_ID = int(owner_id_str)
        logger.info(f"Owner ID loaded: {OWNER_ID}")
    else:
        # If OWNER_ID is not set, log critical error and exit.
        logger.critical("CRITICAL: TELEGRAM_OWNER_ID environment variable not set!")
        print("\n--- FATAL ERROR ---")
        print("Environment variable TELEGRAM_OWNER_ID is not set.")
        print("Set it to your Telegram User ID before starting the bot.")
        exit(1) # Exit with a non-zero code indicates an error
except ValueError:
    # If OWNER_ID is not a valid integer, log critical error and exit.
    logger.critical(f"CRITICAL: Invalid TELEGRAM_OWNER_ID: '{owner_id_str}'. Must be an integer.")
    print("\n--- FATAL ERROR ---")
    print(f"Invalid TELEGRAM_OWNER_ID: '{owner_id_str}'. Must be an integer.")
    exit(1) # Exit with a non-zero code indicates an error
except Exception as e:
    # Catch any other potential exceptions during OWNER_ID processing
    logger.critical(f"CRITICAL: Unexpected error loading OWNER_ID: {e}")
    print(f"\n--- FATAL ERROR ---")
    print(f"Unexpected error loading OWNER_ID: {e}")
    exit(1)


# --- Notes on Group Usage ---
# Bot needs 'Can restrict members' admin permission for /kill and /punch to work.

# --- CAT TEXTS SECTION ---

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


# --- TEXT SECTION END ---

# --- Utility Functions ---

def get_readable_time_delta(delta: datetime.timedelta) -> str:
    """Converts a timedelta into a human-readable string."""
    total_seconds = int(delta.total_seconds())
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if days > 0: parts.append(f"{days}d")
    if hours > 0: parts.append(f"{hours}h")
    if minutes > 0: parts.append(f"{minutes}m")
    # Show seconds if it's the only unit or >= 0
    if seconds >= 0 and not parts: parts.append(f"{seconds}s")
    # Add seconds if > 0 and other units exist
    elif seconds > 0: parts.append(f"{seconds}s")
    return ", ".join(parts) if parts else "0s"

# --- Command Handlers (Public) ---

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
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message."""
    user = update.effective_user
    # Use reply_html for potential formatting in the mention
    await update.message.reply_html(
        f"Meow {user.mention_html()}! I'm the Meow Bot.\n"
        f"Use /help to see available commands for feline fun!"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the help message."""
    # Use reply_html as HELP_TEXT might contain basic HTML in the future
    await update.message.reply_html(HELP_TEXT)

async def send_random_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text_list: list[str], list_name: str) -> None:
    """Sends a random text from the provided list."""
    if not text_list:
        logger.warning(f"Text list '{list_name}' is empty!")
        # Send plain text for this error message
        await update.message.reply_text("Oops! Something went wrong, the text list is empty.")
        return
    chosen_text = random.choice(text_list)
    # Use reply_html to allow potential simple formatting in texts (like *)
    await update.message.reply_html(chosen_text)

# --- Simple Text Command Definitions ---
async def meow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, MEOW_TEXTS, "MEOW_TEXTS")
async def nap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, NAP_TEXTS, "NAP_TEXTS")
async def play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, PLAY_TEXTS, "PLAY_TEXTS")
async def treat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, TREAT_TEXTS, "TREAT_TEXTS")
async def zoomies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, ZOOMIES_TEXTS, "ZOOMIES_TEXTS")
async def judge(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, JUDGE_TEXTS, "JUDGE_TEXTS")

async def attack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a playful attack message (simulation only)."""
    if not ATTACK_TEXTS:
        logger.warning("Text list 'ATTACK_TEXTS' is empty!")
        await update.message.reply_text("Oops! I'm out of attack ideas.")
        return

    target_user = None
    target_mention = None

    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        target_mention = target_user.mention_html()
    elif context.args and context.args[0].startswith('@'):
        target_mention = context.args[0].strip()
        # Protection checks based on ID won't work reliably here
    else:
        # Default target is sender - prevent self-attack implicitly by sending meow instead.
        logger.info(f"User {update.effective_user.id} used /attack without target. Sending random meow.")
        await send_random_text(update, context, MEOW_TEXTS, "MEOW_TEXTS")
        return

    # --- Protection Checks (Only possible if we have target_user from a reply) ---
    if target_user:
        if target_user.id == OWNER_ID:
            logger.info(f"Attack attempt on Owner (ID: {OWNER_ID}) by user {update.effective_user.id}. Denied.")
            await update.message.reply_html(random.choice(CANT_ATTACK_OWNER_TEXTS))
            return
        if target_user.id == context.bot.id:
            logger.info(f"Attack attempt on Bot (ID: {context.bot.id}) by user {update.effective_user.id}. Denied.")
            await update.message.reply_html(random.choice(CANT_ATTACK_SELF_TEXTS))
            return

    # --- Proceed with Attack Simulation ---
    if target_mention:
        chosen_template = random.choice(ATTACK_TEXTS)
        message_text = chosen_template.format(target=target_mention)
        await update.message.reply_html(message_text) # reply_html handles parsing
    else:
        # Fallback for unexpected cases like /attack some_text_not_starting_with_@
         await update.message.reply_text("Who should I attack? Reply to someone or use /attack @username")


# --- Owner Only Functionality ---

async def owner_only_filter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Filter to check if the user is the owner. Stops update processing if not."""
    # Ensure the update has a user associated with it
    if not update.effective_user:
        logger.warning("Received command update without effective_user.")
        raise ApplicationHandlerStop # Cannot verify owner

    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        command_text = "[unknown command]"
        if update.message and update.message.text:
             # Try to get the command part, handle potential errors
             try:
                 command_text = update.message.text.split()[0]
             except IndexError:
                 command_text = update.message.text # If only text, no space
        logger.warning(f"Unauthorized command attempt by user {user_id} for: {command_text}")
        refusal_text = random.choice(OWNER_ONLY_REFUSAL)
        try:
            # Send plain text for refusal, less likely to fail
            await update.message.reply_text(refusal_text)
        except Exception as e:
            logger.error(f"Error sending owner refusal message: {e}")
        # Crucially stop further handlers for this update
        raise ApplicationHandlerStop
    # If we reach here, the user is the owner, continue processing


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a status message (owner only)."""
    # Owner check is handled by the filter above

    # Ping calculation
    ping_ms = "N/A"
    if update.message and update.message.date:
        try:
            # Ensure timezone awareness for accurate calculation
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            message_time_utc = update.message.date.astimezone(datetime.timezone.utc)
            ping_delta = now_utc - message_time_utc
            ping_ms = int(ping_delta.total_seconds() * 1000)
        except Exception as e:
            logger.error(f"Error calculating ping: {e}")
            ping_ms = "Error"

    # Uptime calculation
    uptime_delta = datetime.datetime.now() - BOT_START_TIME
    readable_uptime = get_readable_time_delta(uptime_delta)

    status_message = (
        f"<b>Purrrr! Bot Status:</b>\n"
        f"— Uptime: {readable_uptime}\n"
        f"— Ping: {ping_ms} ms\n"
        f"— Owner ID: {OWNER_ID}\n"
        f"— Status: Ready for naps and treats!"
    )
    logger.info(f"Owner (ID: {update.effective_user.id}) requested status.")
    # Use reply_html as status message contains HTML tags
    await update.message.reply_html(status_message)


async def kill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Bans a user (owner only, requires admin rights)."""
    # Owner check handled by owner_only_filter

    chat = update.effective_chat
    user = update.effective_user # Owner invoking command

    # Check if command used in a group/supergroup where banning is possible
    if chat.type == 'private':
        await update.message.reply_text("This command only works in groups where I can ban users.")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to the user you want to ban.")
        return

    target_user = update.message.reply_to_message.from_user
    target_user_id = target_user.id
    target_mention = target_user.mention_html()
    chat_id = chat.id # Get chat_id for API calls

    logger.info(f"Owner {user.id} attempting /kill on user {target_user_id} in chat {chat_id}.")

    # --- Standard Protection Checks ---
    if target_user_id == OWNER_ID:
        await update.message.reply_html(random.choice(CANT_KILL_PUNCH_OWNER_TEXTS))
        return
    if target_user_id == context.bot.id:
        await update.message.reply_html(random.choice(CANT_KILL_PUNCH_SELF_TEXTS))
        return

    # --- Permission and Status Checks ---
    try:
        # Check bot's permissions IN THIS SPECIFIC CHAT
        bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
        if not (bot_member.status == ChatMemberStatus.ADMINISTRATOR and bot_member.can_restrict_members):
            logger.warning(f"Bot lacks ban permission in chat {chat_id}. Owner: {user.id}")
            await update.message.reply_html(random.choice(BOT_NO_BAN_PERMISSION_TEXTS))
            return

        # Check target's status IN THIS SPECIFIC CHAT
        target_member = await context.bot.get_chat_member(chat_id, target_user_id)
        if target_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            logger.info(f"Attempt to ban admin/owner {target_user_id} by owner {user.id} in chat {chat_id}. Denied.")
            await update.message.reply_html(random.choice(CANT_BAN_ADMIN_TEXTS).format(target=target_mention))
            return

    except TelegramError as e:
        logger.error(f"Error checking permissions/status in chat {chat_id} for user {target_user_id}: {e}")
        await update.message.reply_text(f"Meow! Couldn't check permissions/status due to an error: {e}")
        return
    except Exception as e: # Catch other unexpected errors during checks
         logger.error(f"Unexpected error during permission/status check: {e}", exc_info=True)
         await update.message.reply_text("An unexpected error occurred while checking permissions.")
         return

    # --- Execute Ban ---
    try:
        await context.bot.ban_chat_member(chat_id=chat_id, user_id=target_user_id)
        logger.info(f"Owner {user.id} successfully banned user {target_user_id} in chat {chat_id}.")
        await update.message.reply_html(random.choice(SUCCESS_KILL_TEXTS).format(target=target_mention))

    except TelegramError as e:
        logger.error(f"Failed to ban user {target_user_id} in chat {chat_id} by owner {user.id}: {e}")
        # Provide more specific feedback if possible
        error_message = f"Error: {e}"
        if "user is an administrator of the chat" in str(e).lower():
             error_message = random.choice(CANT_BAN_ADMIN_TEXTS).format(target=target_mention) # Use specific text if known error
        elif "not enough rights" in str(e).lower():
             error_message = random.choice(BOT_NO_BAN_PERMISSION_TEXTS) # Use specific text if known error

        await update.message.reply_html(random.choice(FAILED_ACTION_TEXTS).format(target=target_mention) + f"\n{error_message}")

    except Exception as e: # Catch other unexpected errors during banning
         logger.error(f"Unexpected error during ban: {e}", exc_info=True)
         await update.message.reply_text("An unexpected error occurred while trying to ban.")


async def punch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kicks (bans and unbans) a user (owner only, requires admin rights)."""
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == 'private':
        await update.message.reply_text("This command only works in groups where I can kick users.")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to the user you want to kick.")
        return

    target_user = update.message.reply_to_message.from_user
    target_user_id = target_user.id
    target_mention = target_user.mention_html()
    chat_id = chat.id

    logger.info(f"Owner {user.id} attempting /punch on user {target_user_id} in chat {chat_id}.")

    # --- Standard Protection Checks ---
    if target_user_id == OWNER_ID:
        await update.message.reply_html(random.choice(CANT_KILL_PUNCH_OWNER_TEXTS))
        return
    if target_user_id == context.bot.id:
        await update.message.reply_html(random.choice(CANT_KILL_PUNCH_SELF_TEXTS))
        return

    # --- Permission and Status Checks ---
    try:
        bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
        if not (bot_member.status == ChatMemberStatus.ADMINISTRATOR and bot_member.can_restrict_members):
            logger.warning(f"Bot lacks kick permission in chat {chat_id}. Owner: {user.id}")
            await update.message.reply_html(random.choice(BOT_NO_BAN_PERMISSION_TEXTS))
            return

        target_member = await context.bot.get_chat_member(chat_id, target_user_id)
        if target_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            logger.info(f"Attempt to kick admin/owner {target_user_id} by owner {user.id} in chat {chat_id}. Denied.")
            await update.message.reply_html(random.choice(CANT_BAN_ADMIN_TEXTS).format(target=target_mention))
            return

    except TelegramError as e:
        logger.error(f"Error checking permissions/status in chat {chat_id} for user {target_user_id}: {e}")
        await update.message.reply_text(f"Meow! Couldn't check permissions/status due to an error: {e}")
        return
    except Exception as e:
         logger.error(f"Unexpected error during permission/status check: {e}", exc_info=True)
         await update.message.reply_text("An unexpected error occurred while checking permissions.")
         return

    # --- Execute Kick (Ban + Unban) ---
    try:
        # Ban first
        await context.bot.ban_chat_member(chat_id=chat_id, user_id=target_user_id)
        logger.debug(f"Temporarily banned user {target_user_id} for kick in chat {chat_id}.")

        # Immediately unban
        # only_if_banned=True prevents errors if the user wasn't banned for some reason
        await context.bot.unban_chat_member(chat_id=chat_id, user_id=target_user_id, only_if_banned=True)
        logger.info(f"Owner {user.id} successfully kicked user {target_user_id} in chat {chat_id}.")
        await update.message.reply_html(random.choice(SUCCESS_PUNCH_TEXTS).format(target=target_mention))

    except TelegramError as e:
        logger.error(f"Failed to kick user {target_user_id} in chat {chat_id} by owner {user.id}: {e}")
        # Provide more specific feedback if possible
        error_message = f"Error: {e}"
        # Check common errors
        if "user is an administrator of the chat" in str(e).lower():
             error_message = random.choice(CANT_BAN_ADMIN_TEXTS).format(target=target_mention)
        elif "not enough rights" in str(e).lower():
             error_message = random.choice(BOT_NO_BAN_PERMISSION_TEXTS)
        # If ban worked but unban failed, the user remains banned! Inform the owner.
        elif "user not found" in str(e).lower() and "unban" in str(e).lower(): # Check context for unban error
             error_message = f"Kick failed: Couldn't unban {target_mention}. They might have already left or the ban failed silently. Check manually."
        elif "user was kicked" in str(e).lower(): # Sometimes the error might indicate kick already happened
            logger.info(f"User {target_user_id} might have already been kicked, trying unban again just in case.")
            try: # Attempt unban again if kick seemed successful but errored
                await context.bot.unban_chat_member(chat_id=chat_id, user_id=target_user_id, only_if_banned=True)
                await update.message.reply_html(random.choice(SUCCESS_PUNCH_TEXTS).format(target=target_mention))
                return # Exit cleanly if unban succeeded on retry
            except Exception as unban_e:
                logger.error(f"Retry unban failed for {target_user_id}: {unban_e}")
                error_message = f"Kick seems to have failed ({e}). User may be banned. Please check."


        await update.message.reply_html(random.choice(FAILED_ACTION_TEXTS).format(target=target_mention) + f"\n{error_message}")

    except Exception as e:
         logger.error(f"Unexpected error during kick: {e}", exc_info=True)
         await update.message.reply_text("An unexpected error occurred while trying to kick.")


# --- Main Function ---

def main() -> None:
    """Configures and runs the Telegram bot."""
    # Check for Bot Token first
    token = ("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.critical("CRITICAL: TELEGRAM_BOT_TOKEN environment variable not set!")
        print("\n--- FATAL ERROR ---")
        print("You haven't set the TELEGRAM_BOT_TOKEN environment variable.")
        print("Set it before starting the catbot :]")
        exit(1) # Exit if token is not set

    # OWNER_ID check happens reliably at the top now

    # Build Application
    application = Application.builder().token(token).build()

    # --- Handler Registration ---

    # Owner Only Handlers Group (Group 0 - runs before default group -1)
    owner_handler_group = 0
    # The filter runs first for any command update processed by this group
    application.add_handler(MessageHandler(filters.COMMAND, owner_only_filter), group=owner_handler_group)
    # Actual owner commands - will only be reached if the filter passes
    application.add_handler(CommandHandler("status", status), group=owner_handler_group)
    application.add_handler(CommandHandler("kill", kill), group=owner_handler_group)
    application.add_handler(CommandHandler("punch", punch), group=owner_handler_group)

    # Public Handlers Group (Default Group -1 - runs after group 0)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("meow", meow))
    application.add_handler(CommandHandler("nap", nap))
    application.add_handler(CommandHandler("play", play))
    application.add_handler(CommandHandler("treat", treat))
    application.add_handler(CommandHandler("zoomies", zoomies))
    application.add_handler(CommandHandler("judge", judge))
    application.add_handler(CommandHandler("attack", attack)) # Attack is simulation only

    # --- Start the Bot ---
    logger.info(f"Bot starting polling... Owner ID: {OWNER_ID}")
    try:
        # run_polling blocks until stopped (e.g., by Ctrl+C)
        application.run_polling()
    except KeyboardInterrupt:
         logger.info("Bot stopped by user (Ctrl+C).")
    except TelegramError as te:
         logger.critical(f"CRITICAL: Unhandled TelegramError during polling: {te}", exc_info=True)
         print(f"\n--- FATAL ERROR ---")
         print(f"Bot crashed due to Telegram error: {te}")
         exit(1)
    except Exception as e:
        # Catch any other unexpected errors during runtime
        logger.critical(f"CRITICAL: Bot crashed during runtime: {e}", exc_info=True) # Log traceback
        print(f"\n--- FATAL ERROR ---")
        print(f"Bot crashed: {e}")
        exit(1)
    finally:
        logger.info("Bot shutdown process initiated.")
        # Potentially add cleanup code here if needed

    logger.info("Bot stopped.")

# --- Script Execution ---
if __name__ == "__main__":
    main()
