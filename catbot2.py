import logging
import random
import os
from telegram import Update, ParseMode # Added ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

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

# /attack texts - uses {target} as a placeholder for the username/mention
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

# --- TEXT SECTION END ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    user = update.effective_user
    await update.message.reply_html(
        f"Meow {user.mention_html()}! I'm the Meow Bot.\n"
        f"Use these commands for feline fun:\n"
        f"/meow - Random cat sound/phrase\n"
        f"/nap - Thoughts during a nap\n"
        f"/play - Cat's playful actions\n"
        f"/treat - Feed me!\n"
        f"/zoomies - Sudden bursts of energy\n"
        f"/judge - Cat judgments\n"
        f"/attack - Launch a playful attack!" # Added /attack description
    )

async def send_random_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text_list: list[str], list_name: str) -> None:
    """Sends a random text from the provided list."""
    if not text_list:
        logger.warning(f"Text list '{list_name}' is empty!")
        await update.message.reply_text("Oops! Something went wrong, the text list is empty.")
        return

    chosen_text = random.choice(text_list)
    # Use reply_html by default for potential formatting, although not strictly needed here
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
    """Sends a playful attack message, targeting a user."""
    if not ATTACK_TEXTS:
        logger.warning("Text list 'ATTACK_TEXTS' is empty!")
        await update.message.reply_text("Oops! I'm out of attack ideas.")
        return

    target_mention = None
    # Priority 1: Replied message
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        # mention_html creates a clickable link if user has username, otherwise uses first name
        target_mention = target_user.mention_html()
    # Priority 2: Argument starting with @
    elif context.args and context.args[0].startswith('@'):
        target_mention = context.args[0] # Use the provided username text
    # Priority 3: Self-attack
    else:
        target_user = update.effective_user
        target_mention = target_user.mention_html() # Mention self

    if target_mention:
        chosen_template = random.choice(ATTACK_TEXTS)
        # Format the template with the determined target mention
        message_text = chosen_template.format(target=target_mention)
        # Send as HTML to properly render the mention if mention_html() was used
        await update.message.reply_html(message_text, parse_mode=ParseMode.HTML)
    else:
        # This case should theoretically not happen with the logic above, but as a fallback:
        await update.message.reply_text("Who should I attack? Reply to someone or use /attack @username")


def main() -> None:
    """Starts the bot."""
    token = ("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("Error: TELEGRAM_BOT_TOKEN environment variable not set!")
        print("\n--- ERROR ---")
        print("You haven't set the TELEGRAM_BOT_TOKEN environment variable.")
        print("Set it before starting the catbot :]")
        return

    application = Application.builder().token(token).build()

    # Registering commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("meow", meow))
    application.add_handler(CommandHandler("nap", nap))
    application.add_handler(CommandHandler("play", play))
    application.add_handler(CommandHandler("treat", treat))
    application.add_handler(CommandHandler("zoomies", zoomies))
    application.add_handler(CommandHandler("judge", judge))
    application.add_handler(CommandHandler("attack", attack)) # Added attack handler

    logger.info("Starting bot...")
    application.run_polling()
    logger.info("Bot stopped.")

if __name__ == "__main__":
    main()
