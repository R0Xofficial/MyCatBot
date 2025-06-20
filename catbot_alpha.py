# MyCatBot - Telegram bot
# Copyright (C) 2025 R0X
# Licensed under the GNU General Public License v3.0
# See the LICENSE file for details.

import logging
import random
import os
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Owner ID Configuration ---
OWNER_ID = None
try:
    # Fetch Owner ID from environment variable
    owner_id_str = ("TELEGRAM_OWNER_ID")
    if owner_id_str:
        OWNER_ID = int(owner_id_str)
        logger.info(f"Owner ID loaded: {OWNER_ID}")
    else:
        logger.error("CRITICAL: TELEGRAM_OWNER_ID environment variable not set!")
        print("\n--- ERROR ---")
        print("Environment variable TELEGRAM_OWNER_ID is not set.")
        print("Set it to your Telegram User ID before starting the bot.")
        exit() # Exit if owner ID is not set
except ValueError:
    logger.error(f"CRITICAL: Invalid TELEGRAM_OWNER_ID: '{owner_id_str}'. Must be an integer.")
    print("\n--- ERROR ---")
    print(f"Invalid TELEGRAM_OWNER_ID: '{owner_id_str}'. Must be an integer.")
    exit() # Exit if owner ID is invalid

# --- Notes on Group Usage ---
# ... (previous notes remain valid)

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

# /attack texts - uses {target} as a placeholder
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

# Texts for refusing to attack owner
CANT_ATTACK_OWNER_TEXTS = [
    "Attack my Owner? Never! They have the treats!",
    "Meow? I would never harm the Hand That Feeds!",
    "Hiss! Don't tell me to attack my favorite human!",
    "Purrrr... I love my owner too much for such shenanigans.",
    "Are you crazy? That's the source of all head scratches!",
    "I respectfully decline. My loyalty lies with the Can Opener.",
]

# Texts for refusing to attack self
CANT_ATTACK_SELF_TEXTS = [
    "Attack... myself? That sounds counter-purrductive.",
    "Why would I do that? I haven't done anything wrong... today.",
    "Meow? I think you're confused. I'm too cute to attack.",
    "My claws are for enemies, not for... me!",
    "Error 404: Self-attack not found. Try attacking a dangling string instead.",
]

# Text for owner-only command refusal
OWNER_ONLY_REFUSAL = [
    "Meeeow! Sorry, only my designated Human can use that command.",
    "Access denied! This command requires special privileges (and treats).",
    "Hiss! You are not the Boss of Meow!",
    "Purrrhaps you should ask my Owner to do that?",
]


# --- TEXT SECTION END ---

# Help message text (public commands)
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
/attack [optional: @username or reply] - Launch a playful attack!
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    user = update.effective_user
    await update.message.reply_html(
        f"Meow {user.mention_html()}! I'm the Meow Bot.\n"
        f"Use /help to see available commands for feline fun!"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the help message."""
    await update.message.reply_html(HELP_TEXT)

async def send_random_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text_list: list[str], list_name: str) -> None:
    """Sends a random text from the provided list."""
    if not text_list:
        logger.warning(f"Text list '{list_name}' is empty!")
        await update.message.reply_text("Oops! Something went wrong, the text list is empty.")
        return

    chosen_text = random.choice(text_list)
    await update.message.reply_html(chosen_text)

async def meow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a random /meow cat text."""
    await send_random_text(update, context, MEOW_TEXTS, "MEOW_TEXTS")

async def nap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a random /nap text."""
    await send_random_text(update, context, NAP_TEXTS, "NAP_TEXTS")

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a random /play text."""
    await send_random_text(update, context, PLAY_TEXTS, "PLAY_TEXTS")

async def treat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a random /treat text."""
    await send_random_text(update, context, TREAT_TEXTS, "TREAT_TEXTS")

async def zoomies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a random /zoomies text."""
    await send_random_text(update, context, ZOOMIES_TEXTS, "ZOOMIES_TEXTS")

async def judge(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a random /judge text."""
    await send_random_text(update, context, JUDGE_TEXTS, "JUDGE_TEXTS")

async def attack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a playful attack message, targeting a user, with owner/self protection."""
    if not ATTACK_TEXTS:
        logger.warning("Text list 'ATTACK_TEXTS' is empty!")
        await update.message.reply_text("Oops! I'm out of attack ideas.")
        return

    target_user = None
    target_mention = None
    is_self_target_attempt = False

    # Determine target
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        target_mention = target_user.mention_html()
    elif context.args and context.args[0].startswith('@'):
        target_mention = context.args[0].strip()
        # Note: We don't get the user ID easily from just a username mention here
    else:
        # Default target is the sender
        target_user = update.effective_user
        target_mention = target_user.mention_html()
        is_self_target_attempt = True # User is trying to target themselves explicitly or implicitly

    # --- Protection Checks ---
    if target_user: # Only check IDs if we have a target_user object
        # Check if target is Owner
        if target_user.id == OWNER_ID:
            logger.info(f"Attack attempt on Owner (ID: {OWNER_ID}) by user {update.effective_user.id}. Denied.")
            refusal_text = random.choice(CANT_ATTACK_OWNER_TEXTS)
            await update.message.reply_html(refusal_text)
            return # Stop processing

        # Check if target is the bot itself
        if target_user.id == context.bot.id:
            logger.info(f"Attack attempt on Bot (ID: {context.bot.id}) by user {update.effective_user.id}. Denied.")
            refusal_text = random.choice(CANT_ATTACK_SELF_TEXTS)
            await update.message.reply_html(refusal_text)
            return # Stop processing

    # --- Proceed with Attack ---
    if target_mention:
        chosen_template = random.choice(ATTACK_TEXTS)
        message_text = chosen_template.format(target=target_mention)
        await update.message.reply_html(message_text)
    else:
        # Fallback if somehow target_mention is still None (shouldn't happen)
        await update.message.reply_text("Who should I attack? Reply to someone or use /attack @username")

# --- Owner Only Command Example ---
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a status message, only usable by the owner."""
    user_id = update.effective_user.id
    if user_id == OWNER_ID:
        logger.info(f"Owner (ID: {user_id}) requested status.")
        await update.message.reply_text("Purrrr! All systems nominal. Ready for naps and treats.")
    else:
        logger.warning(f"Unauthorized status request by user {user_id}.")
        refusal_text = random.choice(OWNER_ONLY_REFUSAL)
        await update.message.reply_html(refusal_text)


def main() -> None:
    """Starts the bot."""
    # Check for Bot Token first
    token = ("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("CRITICAL: TELEGRAM_BOT_TOKEN environment variable not set!")
        print("\n--- ERROR ---")
        print("You haven't set the TELEGRAM_BOT_TOKEN environment variable.")
        print("Set it before starting the catbot :]")
        return # Exit if token is not set

    # OWNER_ID check happens at the top now

    application = Application.builder().token(token).build()

    # Registering commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("meow", meow))
    application.add_handler(CommandHandler("nap", nap))
    application.add_handler(CommandHandler("play", play))
    application.add_handler(CommandHandler("treat", treat))
    application.add_handler(CommandHandler("zoomies", zoomies))
    application.add_handler(CommandHandler("judge", judge))
    application.add_handler(CommandHandler("attack", attack))
    application.add_handler(CommandHandler("status", status)) # Added owner command

    logger.info("Starting bot...")
    application.run_polling()
    logger.info("Bot stopped.")

if __name__ == "__main__":
    main()
