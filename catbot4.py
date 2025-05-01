import logging
import random
import os
import datetime
from telegram import Update
from telegram.constants import ParseMode
# Corrected import line:
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ApplicationHandlerStop

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Owner ID Configuration ---
OWNER_ID = None
BOT_START_TIME = datetime.datetime.now() # Record bot start time

try:
    owner_id_str = ("TELEGRAM_OWNER_ID")
    if owner_id_str:
        OWNER_ID = int(owner_id_str)
        logger.info(f"Owner ID loaded: {OWNER_ID}")
    else:
        logger.critical("CRITICAL: TELEGRAM_OWNER_ID environment variable not set!")
        print("\n--- ERROR ---")
        print("Environment variable TELEGRAM_OWNER_ID is not set.")
        print("Set it to your Telegram User ID before starting the bot.")
        exit()
except ValueError:
    logger.critical(f"CRITICAL: Invalid TELEGRAM_OWNER_ID: '{owner_id_str}'. Must be an integer.")
    print("\n--- ERROR ---")
    print(f"Invalid TELEGRAM_OWNER_ID: '{owner_id_str}'. Must be an integer.")
    exit()

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
# /kill (ban simulation) texts - uses {target} placeholder
KILL_TEXTS = [
    "Unleashed the ultimate scratch fury upon {target}. They've been *eliminated*.",
    "Used the forbidden Death Pounce on {target}. They won't be bothering us again.",
    "{target} has been permanently sent to the 'No-Scratches Zone'. Meowhahaha!",
    "My claws have spoken! {target} is banished from this territory.",
    "{target} dared to interrupt nap time. The punishment is... *eternal silence*.",
    "Consider {target} thoroughly shredded and removed.",
    "The council of cats has voted. {target} is OUT!",
]

# /punch (kick simulation) texts - uses {target} placeholder
PUNCH_TEXTS = [
    "Delivered a swift paw-punch to {target}! Sent 'em flying!",
    "{target} got too close to the food bowl. A warning punch was administered.",
    "A quick 'bap!' sends {target} tumbling out of the chat!",
    "My paw connected squarely with {target}. They needed to leave.",
    "{target} learned the hard way not to step on my tail. *Punch!*",
    "Ejected {target} with extreme prejudice (and a paw).",
    "One punch was all it took. Bye bye, {target}!",
]

# Texts for refusing to kill/punch owner/self
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
    if seconds > 0 or not parts: parts.append(f"{seconds}s") # Show seconds if it's the only unit or > 0
    return ", ".join(parts) if parts else "0s"

# --- Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message."""
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

async def meow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, MEOW_TEXTS, "MEOW_TEXTS")
async def nap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, NAP_TEXTS, "NAP_TEXTS")
async def play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, PLAY_TEXTS, "PLAY_TEXTS")
async def treat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, TREAT_TEXTS, "TREAT_TEXTS")
async def zoomies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, ZOOMIES_TEXTS, "ZOOMIES_TEXTS")
async def judge(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, JUDGE_TEXTS, "JUDGE_TEXTS")

async def attack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a playful attack message, targeting a user, with owner/self protection."""
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
    else:
        # Default target is sender - prevent self-attack implicitly
        target_user = update.effective_user
        if target_user.id == context.bot.id: # Prevent targeting bot if sender = bot (shouldn't happen)
             await update.message.reply_html(random.choice(CANT_ATTACK_SELF_TEXTS))
             return
        # Instead of attacking self, maybe just send a confused meow? Or do nothing.
        # Let's just send a random meow instead of attacking self by default.
        logger.info(f"User {update.effective_user.id} used /attack without target. Sending random meow.")
        await send_random_text(update, context, MEOW_TEXTS, "MEOW_TEXTS")
        return


    # --- Protection Checks ---
    if target_user: # Check IDs only if we have a target_user object (from reply)
        if target_user.id == OWNER_ID:
            logger.info(f"Attack attempt on Owner (ID: {OWNER_ID}) by user {update.effective_user.id}. Denied.")
            await update.message.reply_html(random.choice(CANT_ATTACK_OWNER_TEXTS))
            return
        if target_user.id == context.bot.id:
            logger.info(f"Attack attempt on Bot (ID: {context.bot.id}) by user {update.effective_user.id}. Denied.")
            await update.message.reply_html(random.choice(CANT_ATTACK_SELF_TEXTS))
            return

    # --- Proceed with Attack ---
    if target_mention:
        chosen_template = random.choice(ATTACK_TEXTS)
        message_text = chosen_template.format(target=target_mention)
        await update.message.reply_html(message_text)
    else: # Should only happen if context.args was used but didn't start with @
        await update.message.reply_text("Who should I attack? Reply to someone or use /attack @username")


# --- Owner Only Commands ---

async def owner_only_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Filter to check if the user is the owner. Stops update processing if not."""
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        logger.warning(f"Unauthorized command attempt by user {user_id} for: {update.message.text}")
        refusal_text = random.choice(OWNER_ONLY_REFUSAL)
        await update.message.reply_html(refusal_text)
        raise ApplicationHandlerStop # Stop processing this update further
    # If we reach here, the user is the owner, continue processing

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a status message (owner only)."""
    # Owner check is handled by the filter now

    # Ping calculation
    now = datetime.datetime.now(datetime.timezone.utc) # Use timezone-aware now
    message_time = update.message.date # Already timezone-aware
    ping_delta = now - message_time
    ping_ms = int(ping_delta.total_seconds() * 1000)

    # Uptime calculation
    uptime_delta = datetime.datetime.now() - BOT_START_TIME
    readable_uptime = get_readable_time_delta(uptime_delta)

    status_message = (
        f" Purrrr! Bot Status:\n"
        f"- <b>Uptime:</b> {readable_uptime}\n"
        f"- <b>Ping:</b> {ping_ms} ms\n"
        f"- <b>Owner ID:</b> {OWNER_ID}\n"
        f"- Ready for naps and treats!"
    )
    logger.info(f"Owner (ID: {update.effective_user.id}) requested status.")
    await update.message.reply_html(status_message)


async def kill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Simulates banning a user (owner only)."""
    # Owner check handled by filter

    if not update.message.reply_to_message:
        await update.message.reply_text("You need to reply to the user you want to *metaphorically* kill.")
        return

    target_user = update.message.reply_to_message.from_user

    # Protection checks
    if target_user.id == OWNER_ID:
        logger.info(f"Kill attempt on Owner (ID: {OWNER_ID}) by owner. Denied.")
        await update.message.reply_html(random.choice(CANT_KILL_PUNCH_OWNER_TEXTS))
        return
    if target_user.id == context.bot.id:
        logger.info(f"Kill attempt on Bot (ID: {context.bot.id}) by owner. Denied.")
        await update.message.reply_html(random.choice(CANT_KILL_PUNCH_SELF_TEXTS))
        return

    # Proceed with simulation
    target_mention = target_user.mention_html()
    chosen_template = random.choice(KILL_TEXTS)
    message_text = chosen_template.format(target=target_mention)

    logger.info(f"Owner (ID: {update.effective_user.id}) used /kill on user {target_user.id} ({target_mention}). Simulation sent.")
    await update.message.reply_html(message_text)
    # To *actually* ban (if bot is admin):
    # try:
    #     await context.bot.ban_chat_member(chat_id=update.effective_chat.id, user_id=target_user.id)
    #     await update.message.reply_text(f"Okay, {target_mention} has been banned (for real this time).")
    # except Exception as e:
    #     logger.error(f"Failed to ban user {target_user.id}: {e}")
    #     await update.message.reply_text(f"Meow! I couldn't *actually* ban {target_mention}. Do I have admin rights?")

async def punch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Simulates kicking a user (owner only)."""
    # Owner check handled by filter

    if not update.message.reply_to_message:
        await update.message.reply_text("You need to reply to the user you want to *playfully* punch out.")
        return

    target_user = update.message.reply_to_message.from_user

    # Protection checks
    if target_user.id == OWNER_ID:
        logger.info(f"Punch attempt on Owner (ID: {OWNER_ID}) by owner. Denied.")
        await update.message.reply_html(random.choice(CANT_KILL_PUNCH_OWNER_TEXTS))
        return
    if target_user.id == context.bot.id:
        logger.info(f"Punch attempt on Bot (ID: {context.bot.id}) by owner. Denied.")
        await update.message.reply_html(random.choice(CANT_KILL_PUNCH_SELF_TEXTS))
        return

    # Proceed with simulation
    target_mention = target_user.mention_html()
    chosen_template = random.choice(PUNCH_TEXTS)
    message_text = chosen_template.format(target=target_mention)

    logger.info(f"Owner (ID: {update.effective_user.id}) used /punch on user {target_user.id} ({target_mention}). Simulation sent.")
    await update.message.reply_html(message_text)
    # To *actually* kick (if bot is admin and can restrict):
    # Kick usually implies a temporary removal allowing rejoin, ban is more permanent.
    # Often requires unbanning immediately after banning for a "kick" effect.
    # try:
    #     chat_id=update.effective_chat.id
    #     await context.bot.ban_chat_member(chat_id=chat_id, user_id=target_user.id)
    #     await context.bot.unban_chat_member(chat_id=chat_id, user_id=target_user.id) # Unban immediately for kick effect
    #     await update.message.reply_text(f"Okay, {target_mention} has been kicked (for real this time).")
    # except Exception as e:
    #     logger.error(f"Failed to kick user {target_user.id}: {e}")
    #     await update.message.reply_text(f"Meow! I couldn't *actually* kick {target_mention}. Do I have admin rights?")


def main() -> None:
    """Starts the bot."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.critical("CRITICAL: TELEGRAM_BOT_TOKEN environment variable not set!")
        print("\n--- ERROR ---")
        print("You haven't set the TELEGRAM_BOT_TOKEN environment variable.")
        print("Set it before starting the catbot :]")
        return

    # OWNER_ID check now happens reliably at the top

    application = Application.builder().token(token).build()

    # --- Owner Only Handlers Group ---
    # Use group 0 for owner checks, run before default group (-1)
    owner_handler_group = 0

    # Add the filter *before* the owner commands in the same group.
    # It will run first for any update potentially matching the commands in this group.
    # This uses the CORRECTLY IMPORTED MessageHandler
    application.add_handler(MessageHandler(filters.COMMAND, owner_only_filter), group=owner_handler_group)

    # Owner commands will only be reached if the filter above doesn't raise ApplicationHandlerStop
    application.add_handler(CommandHandler("status", status), group=owner_handler_group)
    application.add_handler(CommandHandler("kill", kill), group=owner_handler_group)
    application.add_handler(CommandHandler("punch", punch), group=owner_handler_group)

    # --- Public Handlers Group (default group -1) ---
    # These run after group 0 handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("meow", meow))
    application.add_handler(CommandHandler("nap", nap))
    application.add_handler(CommandHandler("play", play))
    application.add_handler(CommandHandler("treat", treat))
    application.add_handler(CommandHandler("zoomies", zoomies))
    application.add_handler(CommandHandler("judge", judge))
    application.add_handler(CommandHandler("attack", attack))

    logger.info(f"Bot started. Uptime counter running. Owner ID: {OWNER_ID}")
    application.run_polling()
    logger.info("Bot stopped.")

if __name__ == "__main__":
    # No longer need the separate import here as it's at the top
    main()
