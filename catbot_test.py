#!/usr/bin/env python
# -*- coding: utf-8 -*-

# --- Cat Bot - A simple Telegram bot with fun cat actions ---
# Includes owner protection, simulation commands, GIF/Photo fetching, and owner commands.
# Uses environment variables for configuration (Token, Owner ID).

import logging
import random
import os       # Required for os.getenv()
import datetime # Required for uptime/ping
import requests # Required for /gif and /photo
from telegram import Update, constants # Import constants
from telegram.ext import Application, CommandHandler, ContextTypes
# Optional Debug Imports
# from telegram.ext import MessageHandler, filters, ApplicationHandlerStop
from telegram.error import TelegramError # To catch potential errors

# --- Logging Configuration ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# Reduce log noise from underlying libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.vendor.ptb_urllib3.urllib3").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING) # Added for httpx's dependency

logger = logging.getLogger(__name__)

# --- Owner ID Configuration & Bot Start Time ---
OWNER_ID = None
BOT_START_TIME = datetime.datetime.now() # Record bot start time

# --- Load configuration from environment variables ---
# This is the SECURE way to handle sensitive data.
# Make sure you set the variables using 'export' in the terminal!
try:
    # Load Owner ID
    owner_id_str = os.getenv("TELEGRAM_OWNER_ID")
    if owner_id_str:
        OWNER_ID = int(owner_id_str)
        logger.info(f"Owner ID loaded: {OWNER_ID}")
    else:
        # Critical error if the variable is not set
        logger.critical("CRITICAL: TELEGRAM_OWNER_ID environment variable not set!")
        print("\n--- FATAL ERROR ---")
        print("Environment variable TELEGRAM_OWNER_ID is not set.")
        print("Set it to your numeric Telegram User ID before starting the bot.")
        exit(1) # Exit with a non-zero code indicates an error
except ValueError:
    logger.critical(f"CRITICAL: Invalid TELEGRAM_OWNER_ID: '{owner_id_str}'. Must be an integer.")
    print("\n--- FATAL ERROR ---")
    print(f"Invalid TELEGRAM_OWNER_ID: '{owner_id_str}'. Must be an integer.")
    exit(1) # Exit with a non-zero code indicates an error
except Exception as e:
    logger.critical(f"CRITICAL: Unexpected error loading OWNER_ID: {e}")
    print(f"\n--- FATAL ERROR --- \n{e}")
    exit(1)

# Load Bot Token (also via os.getenv)
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    logger.critical("CRITICAL: TELEGRAM_BOT_TOKEN environment variable not set!")
    print("\n--- FATAL ERROR ---")
    print("Environment variable TELEGRAM_BOT_TOKEN is not set.")
    print("Set it using 'export' before running the bot.")
    exit(1)
# logger.debug(f"DEBUG: Read token fragment: '{BOT_TOKEN[:6]}...{BOT_TOKEN[-4:]}'") # Uncomment to debug token

# --- CAT TEXTS SECTION ---

# /meow texts
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
]

# /nap texts
NAP_TEXTS = [
    "Zzzzz... 😴", "Dreaming of chasing mice... <i>big</i> ones. 🐭", "Do not disturb the royal nap. 👑",
    "Found the perfect sunbeam. Bliss. ☀️", "Curled up in a tight ball. Maximum floof.", "Too comfy to move. Send help (later).",
    "Just five more minutes... or five hours. ⏰", "Sleeping level: <b>Expert</b>. 🏆",
    "Charging my batteries for zoomies. 🔋", "Is it nap time yet? Oh, it always is. ✅",
    "Comfort is my middle name. Danger is my game (when awake).", "Where's the warmest spot? That's where I am. 🔥",
    "Sleeping with one eye open... always vigilant. 👀", "Purring on standby. <pre>Low rumble activated.</pre>", "Don't wake the sleeping beast! 🐲",
    "Do not poke the floof. 🚫👈", "Nap interrupted? Prepare for passive-aggressive ignoring.",
    "Dreaming of an endless tuna buffet. 🍣", "This blanket is now a fortress of solitude. 🏰",
    "Shhh... dreaming of world domination (and snacks). 🌍🍪", "Soft spot detected. Initiating nap sequence.",
    "Eyes closed. Thoughts: <i>none</i>. Brain empty.", "Current status: melted into the couch. Send snacks.",
    "If I fits, I naps. The box dimension is cozy. 📦", "My snore is a delicate symphony. 🎶 ...or a chainsaw.",
    "I changed position. That counts as exercise for the day. 💪", "Napping: a full-time job. Very demanding.",
    "Too tired to care. Still cute, though. 😉", "I blinked slowly. That was my major effort for this hour.",
    "Sleeping through the apocalypse. Wake me when it's over. ☄️", "Gravity is stronger during nap time. It's science.",
    "My fur absorbs sleep energy. And your dark clothing.", "Nap level: <b>transcendence</b>. 🧘",
    "Out of order until further notice. 🚫", "Occupied: enter the nap zone at your own risk. ⚠️",
    "Cushion claimed. Do not attempt reclamation. 🚩", "I nap therefore I am. (Mostly nap).",
    "Nap goal: 16 hours achieved. Aiming for 20. 🥇", "Stretched once. Exhausting. Need another nap.",
    "Curled like a perfect croissant. 🥐", "Horizontal and proud of it. <pre>horizontal</pre>",
    "The world can wait. My nap cannot. ✋", "Entering low-power mode... 💤",
]

# /play texts
PLAY_TEXTS = [
    "*Batting at an invisible speck* ✨", "Attack the dangly thing! 🧶", "Where's the string? Show me!",
    "<b>Pounce!</b> 💥", "Wrestling the toy mouse... I WON! 🏆🐭", "Hide and seek? I'm under the couch. You can't see me! 👀",
    "My hunting instincts are tingling! 🏹", "Chasing my own tail! It's elusive! 🌀",
    "Got the zoomies - must play! 💨", "Do I hear a crinkle ball? 🎶",
    "Ambush from around the corner! Surprise! 😼", "Hunting your feet under the covers. Beware! 🦶",
    "This toy insulted my ancestors. It must perish. 💀", "Curtain climbing commencing! To the top! 🧗",
    "Bring the wand toy! The feathery one! 🎣",
    "That sock looked at me funny. It must be disciplined. 🧦", "Time to sprint at full speed—for absolutely no reason.",
    "<i>*Pounces dramatically, misses entirely*</i> ... Calculated.", "I'm a fierce jungle predator. Fear my tiny roar! 🦁",
    "Couch? More like launchpad! 🚀", "Tag, you're it! *disappears*",
    "I heard a noise three rooms away. Attack mode: ON. 🚨", "Sneak... sneak... <b>POUNCE!</b>",
    "Everything is a toy if you're brave enough. Especially that expensive vase.",
    "Why walk when you can <i>leap</i> across the void between furniture?", "Zoomies in progress. Please stand back. 🚧",
    "The toy moved. Or did it? Existential crisis incoming... must bat! 🤔", "*tail flick* Battle begins now. ⚔️",
    "Your pen? Mine now. For batting practice. 🖊️", "Under the bed is my secret battle arena. 🛏️",
    "I'm training for the Cat Olympics. Gold in Napping and Pouncing. 🏅", "This paper bag is my kingdom. All hail Bag Cat! 👑🛍️",
    "Rug folded? Perfect ambush spot! 🧐", "Sneaky mode: activated. Ninja level. 🥷",
    "*wild eyes* Something... is about to happen... 🤪",
    "You’ll never catch me—<i>zoom!</i> ⚡", "Interrupt play? Unforgivable. Prepare for ankle attack.",
    "Ceiling? Might reach it this time. Gravity is merely a suggestion. 🚀", "I fight shadows for dominance. The shadows are winning.",
    "Don't blink. You'll miss my spectacular fail. 😹", "The Temptation of the Cardboard Box! Irresistible! 📦",
]

# /treat texts
TREAT_TEXTS = [
    "Treats, please! 🙏", "My bowl echoes with emptiness. Fill it! 😩", "Did you say... <i>tuna</i>? 🐟 Where?!",
    "I performed a cute trick (existing). Where's my reward? 🎁",
    "I can hear the treat bag rustling from three rooms away. Supersonic ears! 👂", "Feed me, peasant! ...I mean, beloved human. ❤️",
    "A snack would be purrfect. 💯", "I solemnly swear I am up to no good... unless there are treats involved. Then I'm an angel. 😇",
    "The fastest way to my heart is through my stomach. 💖", "Just a little nibble? Pleeeease?🥺",
    "Staring at you with big, cute eyes... 🥺 It's super effective! Give treat!",
    "Does that cupboard contain treats? Must investigate. 🕵️",
    "My internal clock says it's <b>snack time</b>. ⏰",
    "In exchange for a treat, I shall allow <i>one</i> (1) pet. Maybe.", "Food is life. Treats are heaven. ✨",
    "This meow was not free. It costs one (1) treat. Pay up. 💰",
    "Bribery? Accepted—if treats are involved. Especially salmon flavor. 🍣",
    "I saw you open the fridge. I demand the cheese tax! 🧀 Or just treats.",
    "No treat? I am lodging an official complaint with the Pawthorities. 📝",
    "If I stare long enough, treats will magically appear. It's the law of attraction. 👀✨",
    "Did someone say <code>snack</code>? Or was that my stomach rumbling?",
    "I knocked that over. Where's my compensatory snack reward? 🤔",
    "Don't make me do the sad eyes... too late. 🥺 Give in.",
    "The treat jar just winked at me. I swear. It wants to be opened. 😉",
    "Will purr for snacks. Loudly. 🔊",
    "Refusing treats is a punishable offense. The penalty is... more meowing.",
    "Yes, I did sit like a perfect loaf. Now feed me the reward bread (treats). 🍞",
    "A single treat is merely an appetizer. I demand a pile. A mountain! ⛰️",
    "The treat tax is due. Pay up, hooman.",
    "I'll scream until rewarded. It's a valid negotiation tactic. 📢",
    "I sniffed something tasty. Hand it over, no questions asked.👃",
    "I have acquired the taste... of <i>everything</i>. Give treats.",
    "That sound... was that the drawer of dreams? The Treat Treasury? ✨",
    "I've been a very good cat... for the last five seconds. That counts! ✅",
    "Resistance is futile. Your treats will be assimilated. 🤖",
    "My love language is 'receiving treats'. 💬❤️",
]

# /zoomies texts
ZOOMIES_TEXTS = [
    "Hyperdrive activated! 🚀", "<i>*Streaks past at Mach 1*</i> 💨", "Wall climbing initiated! 🧗",
    "Can't stop, won't stop! 🌪️", "Running laps around the house! Like, actual laps! 🏃",
    "The floor is lava... and a racetrack! 🔥🏁", "Did a ghost just tickle me? <b>MUST RUN!</b> 👻",
    "Sudden burst of uncontrollable energy! 💥", "My ancestors were cheetahs, probably. 🐆",
    "Leaving a trail of chaos and displaced cushions in my wake.", "Skidded around the corner! <i>Drift King!</i> 🏎️",
    "Ludicrous speed achieved! They've gone to plaid! <pre>plaid</pre>", "Parkour! (over the furniture, under the table, through the legs).",
    "I don't know why I'm running, but the urge is <b>COMPULSORY</b>!", "This is better than catnip! (Maybe). 🌿",
    "I'm speed. Pure, unfiltered, chaotic speed. ⚡",
    "Floor traction: optional. Wall traction: engaged.",
    "Bounce off the wall. Calculate trajectory. Repeat. 📐",
    "Launching off the couch in 3... 2... <b>ZOOM!</b> 🚀",
    "The hallway is my personal drag strip. 🛣️",
    "Invisible enemy detected—engaging turbo mode! Pew pew! ✨",
    "Sprinting like rent's due and I spent it on treats! 💸",
    "<i>*thunderous paws approaching rapidly*</i> <pre>THUMP THUMP THUMP</pre>",
    "Warning: Nothing in the house is safe during Code Zoomies. 🚧",
    "Running in circles until gravity reminds me who's boss. Or I get dizzy.",
    "Alert: 2 AM zoomies have officially begun. Prepare for impact. 🌙",
    "Energy level: <b>UNCONTAINABLE</b>. System overload! 🤯",
    "Is this what lightning feels like? ZAP! ⚡",
    "Acceleration: 100%. Steering: <i>questionable</i>. Braking: nonexistent.",
    "Kitchen counter? Just another parkour obstacle! Leapt it! 💪",
    "The zoomies chose me—I had no say in the matter. It is destiny.",
    "Yeeting myself across the room with grace... and maybe a crash landing. 🤸",
    "Speed mode: <b>ON</b>. Logic: <b>OFF</b>. Fun: <b>MAXIMUM</b>.",
    "Vroom vroom, motherfluffer. 🚗💨",
    "You blinked. I’m now on top of the bookshelf. How? Magic. ✨",
    "My pupils are dilated. The zoom is upon me! ⚫⚫",
]

# /judge texts
JUDGE_TEXTS = [
    "Judging your life choices... <i>harshly</i>. 🧐", "That outfit is... questionable. Did you even consult a cat? 🤔",
    "I saw what you did. I'm not impressed. Try again. 😒",
    "My disappointment is immeasurable, and my day is ruined. 😩",
    "<i>*Slow blink of profound disapproval*</i>", "Are you <b>sure</b> about that decision? Really? 🤨",
    "Silence. Just pure, condescending silence. Let it sink in. 🤫", "I am watching. <b>Always</b> watching. 👀",
    "You call <i>that</i> a proper petting technique? Amateur. 🙄", "Hmmph. 😤", "Did you really think <i>this</i> cheap toy is what I desired? Pathetic. 🧸",
    "Your very existence amuses... and deeply annoys me. Simultaneously.", "You need better ideas. Perhaps consult a feline advisor (me).",
    "Shaking my head in pity (internally, of course. Externally I'm just staring).",
    "I could do that better... if I had opposable thumbs and the slightest motivation. Which I don't.",
    "I've seen kittens make more logical decisions. 🍼",
    "You're lucky I'm too comfortable right now to overthrow you. 👑",
    "Oh, you again. Sigh. 😮‍💨", "Please... try harder. For my sake.",
    "Even the dog (if present, otherwise imagine one) knows better. 🐶", "That's your plan? Bold move. Stupid, but bold. 🤡",
    "I expected nothing, and I’m still let down. Impressive. 📉",
    "<i>*rolls eyes so hard they almost fall out*</i> (in feline, naturally)", "You may pet me. But know that I am silently judging your technique.",
    "Your behavior is being recorded for future mockery and blackmail.",
    "I meow because I must express my needs, not because you deserve my attention.",
    "No treat? No respect. Simple economics. 🤷", "My tail has more common sense than your entire brain. 🧠",
    "I’d help, but watching you struggle and fail is far more entertaining.🍿",
    "That attempt at affection was… noted. And immediately disregarded. 📝",
    "You exist. That's... unfortunate for the general ambiance.",
    "<i>*judging intensifies to critical levels*</i>", "Wow. Just… <code>wow</code>. Not in a good way.",
    "I blink in sheer disbelief at your ongoing series of questionable choices.",
    "You may continue embarrassing yourself. I'll be over here, judging.",
    "Is 'subpar' your default setting? Asking for a friend (me). 🤔",
]

# /attack texts - uses {target} placeholder (simulation only)
ATTACK_TEXTS = [
    "Launched a sneak attack on {target}'s ankles! <i>Got 'em!</i> 💥",
    "Performed the forbidden pounce onto {target}'s keyboard. Mwahaha! ⌨️😈",
    "Used {target}'s leg as a scratching post. Meowch! Consider it tenderized. 🦵",
    "I jumped on {target}'s head and demanded immediate attention! 👑",
    "Ambushed {target} from under the bed! Rawr! 🦁",
    "Calculated trajectory... Pounced on {target}'s unsuspecting back! Bullseye! 🎯",
    "Unleashed fury upon {target}'s favorite sweater. It looked at me funny. 🧶😠",
    "Bunny-kicked {target}'s arm into submission. Resistance is futile! 🐇",
    "Surprise attack! {target} never saw it coming. Ninja cat! 🥷",
    "Stalked {target} across the room... then attacked a dust bunny instead. Close call, {target}! 😅",
    "Bit {target}'s toes. They were wigglin'. Asking for it. 🦶",
    "Clawed my way up {target}'s leg. I needed a better view... of the ceiling. 🧗",
    "A swift <i>bap bap bap</i> to {target}'s face! Wake up! 👋",
    "Tangled {target} in a web of... well, mostly just my own enthusiasm and some yarn. 🕸️",
    "Practiced my hunting skills on {target}. You're welcome for the training! 😼",
    "Surprise belly trap activated on {target}! Resistance only makes it funnier! 😂",
    "Stealth mode: <b>ON</b>. {target} never had a chance. 😎",
    "Executed a triple spin aerial strike on {target}'s lap! 10/10 landing!🤸",
    "Launched missile lock on {target}'s snack. Target acquired. Now it’s mine. 🚀🍪",
    "Tail-whipped {target} in a moment of pure, unadulterated chaos. 🌀",
    "Nibbled gently on {target}'s fingers. Just a taste test. 🤏",
    "Came in like a fur-covered wrecking ball—sorry, not sorry, {target}. 💣",
    "Rode the curtain down like a pirate... straight into {target}'s dignity. Arrr! 🏴‍☠️",
    "Jumped out of the laundry basket to assert dominance over {target}. Fear me!🧺",
    "Leaped from shelf to shelf... until physics disagreed. Crash-landed on {target}. Oopsie! 🤷",
    "{target}, your hoodie string looked suspiciously like a snake. It had to be done. 🐍",
    "Dramatically tackled {target}'s shadow. Nailed it. Mission success! 😎",
    "Sprinted across {target} at 3 AM. It's tradition. 🕒",
    "Initiated Operation: Sock Sabotage. {target} is now vulnerable and sockless. 🧦",
    "Stared intently at {target} for 10 seconds... then pounced without mercy! Gotcha! ✨",
    "Used {target} as a launching pad for greater heights. Sorry! 🚀",
]

# /kill (simulation only) texts - uses {target} placeholder
KILL_TEXTS = [
    "Unleashed the ultimate scratch fury upon {target}. They've been *metaphorically eliminated*. ☠️",
    "Used the forbidden Death Pounce simulation on {target}. They won't be bothering us again (in theory). 👻",
    "{target} has been permanently sent to the 'No-Scratches Zone' (in my mind). Meowhahaha! 😂",
    "My claws have spoken! {target} is banished from this territory (symbolically). 🚫",
    "{target} dared to interrupt nap time. The punishment is... *imaginary eternal silence*. 🤫",
    "Consider {target} thoroughly shredded (in a simulation) and removed. 💨",
    "The council of cats has voted. {target} is OUT (of my good graces)! 🗳️",
    "Executed a tactical fluff strike—{target} no longer exists (in this chat's narrative). 💥",
    "Marked {target} for deletion... via disapproving glare and a flurry of imaginary paws. 🐾",
    "Declared textual war on {target}. Victory achieved in 3.2 seconds of message chaos. 🚩",
    "Delivered a judgmental paw slap—{target} is now cat history (metaphorically). 👋",
    "Launched a nap-ruining revenge assault. {target} is no more (emotionally speaking). 😠",
    "Sent {target} to the Shadow Realm (aka ignored). 👥",
    "Clawed {target}'s name off the Treat List. Permanently. 📝",
    "One swift tail flick and {target} was symbolically obliterated. ✨",
    "{target} crossed the line. The line of acceptable noise levels. Now it’s silence (simulation).",
    "I hissed. I pounced (textually). I conquered. {target} has been virtually vanquished. 🏆",
    "{target} forgot to refill my bowl. This is their fictional downfall. 📉",
    "Declared myself ruler. {target} refused to bow. They're now fictionally dethroned. 👑",
    "The prophecy foretold this day... {target}'s textual downfall has come. 📜",
    "Only one can nap in this specific sunbeam. {target} has been ceremonially removed (in spirit). ☀️",
]

# /punch (simulation only) texts - uses {target} placeholder
PUNCH_TEXTS = [
    "Delivered a swift paw-punch simulation to {target}! Sent 'em flying (in my imagination)! 🥊",
    "{target} got too close to the food bowl. A warning text-punch was administered. 👊",
    "A quick 'bap!' (as text) sends {target} tumbling out of the chat (mentally)! 👋",
    "My textual paw connected squarely with {target}. They needed to leave (this conversation thread). 💬",
    "{target} learned the hard way not to step on my tail (via text). <i>*Punch!*</i>",
    "Ejected {target} with extreme prejudice (and a message). 🚀",
    "One text-punch was all it took. Bye bye, {target}! 👋",
    "Hit {target} with the ol' one-two text combo! 💥",
    "Served {target} a knuckle (paw?) sandwich, text style. 🥪",
    "Pow! Right in the kisser, {target}! (Metaphorically speaking). 😘➡️💥",
    "Administered a dose of Paw-er Punch to {target}! 💪",
    "Booped {target} with force. Consider it a punch. Boop-punch! 👉",
    "This virtual punch is rated E for Everyone (except {target}).",
    "{target} has been textually knocked out! Ding ding ding! 🔔",
    "Sent {target} packing with a virtual haymaker! 💨",
]

# /slap (simulation only) texts - uses {target} placeholder
SLAP_TEXTS = [
    "A swift slap across the face for {target}! That's what you get! 👋😠",
    "<b>*SLAP!*</b> Did {target} feel that through the screen?",
    "My paw is quick! {target} just got virtually slapped. ⚡",
    "Consider {target} thoroughly slapped for their insolence. 🧐",
    "I don't like {target}'s tone... <i>*slap!*</i>",
    "The disrespect! {target} has earned a textual slap. 😤",
    "Incoming paw! {target} received a disciplinary slap message. 📜",
    "Sometimes, a good slap is the only answer. Right, {target}? 😉",
    "Administering a corrective text-slap to {target}.",
    "How dare you, {target}! <i>*Slap delivered via internet.*</i>",
    "Gave {target} the ol’ left paw of justice. Consider yourself virtually smacked! <pre>Smack!</pre>",
    "High-five! To {target}'s face. With force. 🖐️💥",
    "Bap-powered slap combo move: {target} didn't stand a chance!",
    "{target}, meet the wrath of the fluff hand! 👋",
    "Slapped {target} so hard (in my mind) they saw cartoon birds. 🐦💫",
    "Initiated Fluffy Slap Protocol. Target: {target}. Status: Virtually stinging. 🔥",
    "{target} was asking for it with that comment. So I obliged—with textual style.",
    "Hit {target} with a spinning back-paw! Precision slap! 🥋",
    "{target} caught these virtual paws. No regrets. All fluff. 🐾",
    "Cat-fu slap level 100 achieved. {target} received a legendary textual smackdown.",
    "Left paw. Right paw. Precision slapping. {target} got the message. Loud and clear.",
    "I warned {target}. They didn't listen. Now they feel the sting of my words (and imaginary paw).",
    "That's a paddlin'. Or in this case, a slappin', {target}. 🛶➡️👋",
]

# /bite (simulation only) texts - uses {target} placeholder
BITE_TEXTS = [
    "Took a playful nibble out of {target}! 😬 Nom nom.",
    "Chomp! {target} looked too chewable.",
    "My teefs are sharp! {target} just found out. 🦷",
    "Consider {target} affectionately (or not so affectionately) bitten.",
    "It started as a lick, but ended as a bite. Sorry, {target}! 🤷",
    "A love bite for {target}... maybe with a *little* too much enthusiasm. ❤️‍🔥",
    "Those fingers looked like sausages, {target}! Couldn't resist. 🌭",
    "Warning: May bite when overstimulated. {target} learned this lesson.",
    "Just testing my bite strength on {target}. For science! 🧪",
    "Ankle-biter reporting for duty! Target: {target}'s ankle! 🦶",
    "Gotcha, {target}! A quick bite to keep you on your toes.",
    "Is that... skin? Must bite! Sorry {target}.",
    "My teeth said 'hello' to {target}. 👋🦷",
    "Sometimes biting is the only way to express complex feline emotions, {target}.",
    "I bite because I care... or because you moved too fast, {target}. 🤔",
    "The forbidden chomp was deployed on {target}!",
    "A small price to pay ({target}'s skin) for my amusement.",
    "Vampire cat mode activated! 🧛 Biting {target}!",
    "Consider this a warning bite, {target}. The next one might draw... more text.",
    "My teeth: pointy. Your existence, {target}: biteable. Logic is sound.",
    "Tasting the world one bite at a time, starting with {target}.",
    "<code>OM NOM NOM</code> {target} <code>NOM</code>",
]

# Refusal texts
CANT_TARGET_OWNER_TEXTS = [
    "Meow! I can't target my Owner. They are protected by purr-power! ✨🛡️",
    "Hiss! Targeting the Owner is strictly forbidden by cat law! 📜🚫",
    "Nope. Not gonna do it. That's my human! ❤️",
    "Access Denied: Cannot target the supreme leader (Owner). 👑",
    "Targeting the Owner? Not in this lifetime, furball! 🙅",
]
CANT_TARGET_SELF_TEXTS = [
    "Target... myself? Why would I do that? Silly human. 😹",
    "Error: Cannot target self. My paws have better things to do, like napping. 😴",
    "I refuse to engage in self-pawm. Command ignored with extreme prejudice.",
    "Targeting myself? Not even for a mountain of tuna. 🐟",
]
OWNER_ONLY_REFUSAL = [ # Needed for /status and /say
    "Meeeow! Sorry, only my designated Human can use that command. ⛔",
    "Access denied! This command requires special privileges (and possibly a secret handshake involving treats). 🤝🎁",
    "Hiss! You are not the Boss of Meow! Only <code>{OWNER_ID}</code> is! 👑", # Example using OWNER_ID
    "Purrrhaps you should ask my Owner to run this command for you? 🙏",
]

# --- END OF TEXT SECTION ---

# --- Utility Functions ---
def get_readable_time_delta(delta: datetime.timedelta) -> str:
    """Converts a timedelta into a human-readable string."""
    total_seconds = int(delta.total_seconds()); days, rem = divmod(total_seconds, 86400); hours, rem = divmod(rem, 3600); minutes, seconds = divmod(rem, 60)
    parts = [];
    if days > 0: parts.append(f"{days}d")
    if hours > 0: parts.append(f"{hours}h")
    if minutes > 0: parts.append(f"{minutes}m")
    if seconds >= 0 and not parts: parts.append(f"{seconds}s")
    elif seconds > 0: parts.append(f"{seconds}s")
    return ", ".join(parts) if parts else "0s"

# --- Debug Handler (Optional - uncomment if needed) ---
# async def debug_receive_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#     """Logs any incoming update VERY early."""
#     update_type = "Unknown"; chat_id = "N/A"; user_id = "N/A"; update_id = update.update_id
#     if update.message: update_type = "Message"; chat_id = update.message.chat.id; user_id = update.message.from_user.id if update.message.from_user else "N/A"
#     elif update.callback_query: update_type = "CallbackQuery"; chat_id = update.callback_query.message.chat.id if update.callback_query.message else "N/A"; user_id = update.callback_query.from_user.id
#     logger.critical(f"--- !!! DEBUG: UPDATE RECEIVED !!! ID: {update_id}, Type: {update_type}, ChatID: {chat_id}, UserID: {user_id} ---")

# --- Command Handlers ---
HELP_TEXT = """
Meeeow! 🐾 Here are the commands you can use:

/start - Shows the welcome message. ✨
/help - Shows this help message. ❓
/github - Get the link to my source code! 💻
/owner - Info about my designated human! ❤️
/gif - Get a random cat GIF! 🖼️
/photo - Get a random cat photo! 📷
/meow - Get a random cat sound or phrase. 🔊
/nap - What's on a cat's mind during naptime? 😴
/play - Random playful cat actions. 🧶
/treat - Demand treats! 🎁
/zoomies - Witness sudden bursts of cat energy! 💥
/judge - Get judged by a superior feline. 🧐
/attack [reply/@user] - Launch a playful attack! ⚔️
/kill [reply/@user] - Metaphorically eliminate someone! 💀
/punch [reply/@user] - Deliver a textual punch! 👊
/slap [reply/@user] - Administer a swift slap! 👋
/bite [reply/@user] - Take a playful bite! 😬

<i>(Note: Owner cannot be targeted by attack/kill/punch/slap/bite)</i>
Owner Only Commands (Hidden): 
/status, /say <message>
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the welcome message."""
    user = update.effective_user
    await update.message.reply_html(f"Meow {user.mention_html()}! I'm the Meow Bot. 🐾\nUse /help to see available commands!")
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the help message."""
    await update.message.reply_html(HELP_TEXT)
async def github(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the link to the GitHub repository."""
    github_link = "https://github.com/R0Xofficial/MyCatbot"; await update.message.reply_text(f"Meeeow! I'm open source! 💻 Find my code:\n{github_link}", disable_web_page_preview=True)
async def owner_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays information about the bot's owner."""
    if OWNER_ID:
        owner_mention = f"<code>{OWNER_ID}</code>"; owner_name = "My Esteemed Human"
        try:
            owner_chat = await context.bot.get_chat(OWNER_ID)
            owner_mention = owner_chat.mention_html(); owner_name = owner_chat.full_name or owner_chat.title or owner_name
            logger.info(f"Fetched owner info for ID {OWNER_ID}")
        except TelegramError as e: logger.warning(f"Could not fetch owner info for ID {OWNER_ID}: {e}. Using ID.")
        except Exception as e: logger.error(f"Unexpected error fetching owner info for {OWNER_ID}: {e}", exc_info=True)
        message = (f"My designated human, the bringer of treats 🎁 and head scratches ❤️, is:\n👤 <b>{owner_name}</b> ({owner_mention})\nThey hold the secret to the treat jar! ✨")
        # Use parse_mode explicitly for clarity, although reply_html implies it
        await update.message.reply_html(message, parse_mode=constants.ParseMode.HTML)
    else: logger.error("Owner info cmd called, but OWNER_ID not set!"); await update.message.reply_text("Meow? Can't find owner info!")

async def send_random_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text_list: list[str], list_name: str) -> None:
    """Sends a random text from the provided list."""
    if not text_list: logger.warning(f"List '{list_name}' empty!"); await update.message.reply_text("Oops! List empty."); return
    await update.message.reply_html(random.choice(text_list))

# Simple Text Command Definitions
async def meow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, MEOW_TEXTS, "MEOW_TEXTS")
async def nap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, NAP_TEXTS, "NAP_TEXTS")
async def play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, PLAY_TEXTS, "PLAY_TEXTS")
async def treat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, TREAT_TEXTS, "TREAT_TEXTS")
async def zoomies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, ZOOMIES_TEXTS, "ZOOMIES_TEXTS")
async def judge(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await send_random_text(update, context, JUDGE_TEXTS, "JUDGE_TEXTS")

# Public Simulation Commands with Owner Protection
async def attack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends an attack message (simulation), protects owner/bot."""
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
    """Sends a ban simulation message, protects owner/bot."""
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
    """Sends a kick simulation message, protects owner/bot."""
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

async def slap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a slap simulation message, protects owner/bot."""
    if not SLAP_TEXTS: logger.warning("List 'SLAP_TEXTS' empty!"); await update.message.reply_text("No 'slap' texts."); return
    target_user = None; target_mention = None; target_user_id = None
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        target_user_id = target_user.id; target_mention = target_user.mention_html()
        if target_user_id == OWNER_ID: await update.message.reply_html(random.choice(CANT_TARGET_OWNER_TEXTS)); return
        if target_user_id == context.bot.id: await update.message.reply_html(random.choice(CANT_TARGET_SELF_TEXTS)); return
    elif context.args and context.args[0].startswith('@'): target_mention = context.args[0].strip()
    else: await update.message.reply_text("Who to slap? Reply or use /slap @username."); return
    await update.message.reply_html(random.choice(SLAP_TEXTS).format(target=target_mention))

async def bite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a bite simulation message, protects owner/bot."""
    if not BITE_TEXTS: logger.warning("List 'BITE_TEXTS' empty!"); await update.message.reply_text("No 'bite' texts."); return
    target_user = None; target_mention = None; target_user_id = None
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        target_user_id = target_user.id; target_mention = target_user.mention_html()
        if target_user_id == OWNER_ID: await update.message.reply_html(random.choice(CANT_TARGET_OWNER_TEXTS)); return
        if target_user_id == context.bot.id: await update.message.reply_html(random.choice(CANT_TARGET_SELF_TEXTS)); return
    elif context.args and context.args[0].startswith('@'): target_mention = context.args[0].strip()
    else: await update.message.reply_text("Who to bite? Reply or use /bite @username."); return
    await update.message.reply_html(random.choice(BITE_TEXTS).format(target=target_mention))

# --- GIF and Photo Commands ---
async def gif(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetches and sends a random cat GIF."""
    API_URL = "https://api.thecatapi.com/v1/images/search?mime_types=gif&limit=1"
    headers = {} # Add API key here if you have one
    logger.info("Fetching random cat GIF...")
    try:
        response = requests.get(API_URL, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data and isinstance(data, list) and len(data) > 0 and 'url' in data[0]:
            gif_url = data[0]['url']
            logger.info(f"Found GIF: {gif_url}")
            await update.message.reply_animation(animation=gif_url, caption="Meow! A random GIF for you! 🐾🖼️")
        else:
            logger.warning("No GIF URL found in TheCatAPI response: %s", data)
            await update.message.reply_text("Meow? Couldn't find a GIF now. Try later! 😿")
    except requests.exceptions.Timeout: logger.error("Timeout fetching GIF"); await update.message.reply_text("Hiss! GIF source is slow. Try later. ⏳")
    except requests.exceptions.RequestException as e: logger.error(f"Error fetching GIF: {e}"); await update.message.reply_text("Hiss! Couldn't connect to GIF source. 😿")
    except (IndexError, KeyError, TypeError, ValueError) as e: logger.error(f"Error parsing GIF API response: {e}"); await update.message.reply_text("Mrow! Weird GIF data. 😵‍💫")
    except Exception as e: logger.error(f"Unexpected /gif error: {e}", exc_info=True); await update.message.reply_text("Oops! Unexpected GIF error. 🙀")

async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetches and sends a random cat photo."""
    API_URL = "https://api.thecatapi.com/v1/images/search?limit=1&mime_types=jpg,png"
    headers = {} # Add API key here if you have one
    logger.info("Fetching random cat photo...")
    try:
        response = requests.get(API_URL, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data and isinstance(data, list) and len(data) > 0 and 'url' in data[0]:
            photo_url = data[0]['url']
            logger.info(f"Found Photo: {photo_url}")
            await update.message.reply_photo(photo=photo_url, caption="Purrfect! A random photo for you! 🐾📷")
        else:
            logger.warning("No photo URL found in TheCatAPI response: %s", data)
            await update.message.reply_text("Meow? Couldn't find a photo now. Try later! 😿")
    except requests.exceptions.Timeout: logger.error("Timeout fetching photo"); await update.message.reply_text("Hiss! Photo source is slow. Try later. ⏳")
    except requests.exceptions.RequestException as e: logger.error(f"Error fetching photo: {e}"); await update.message.reply_text("Hiss! Couldn't connect to photo source. 😿")
    except (IndexError, KeyError, TypeError, ValueError) as e: logger.error(f"Error parsing photo API response: {e}"); await update.message.reply_text("Mrow! Weird photo data. 😵‍💫")
    except Exception as e: logger.error(f"Unexpected /photo error: {e}", exc_info=True); await update.message.reply_text("Oops! Unexpected photo error. 🙀")

# --- Owner Only Functionality ---
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a status message (owner only)."""
    user_id = update.effective_user.id
    if user_id == OWNER_ID:
        ping_ms = "N/A"
        if update.message and update.message.date:
            try: now_utc = datetime.datetime.now(datetime.timezone.utc); msg_utc = update.message.date.astimezone(datetime.timezone.utc); ping_ms = int((now_utc - msg_utc).total_seconds() * 1000)
            except Exception as e: logger.error(f"Error calculating ping: {e}"); ping_ms = "Error"
        uptime_delta = datetime.datetime.now() - BOT_START_TIME; readable_uptime = get_readable_time_delta(uptime_delta)
        status_msg = (f"<b>Purrrr! Bot Status:</b> ✨\n— Uptime: {readable_uptime} 🕰️\n— Ping: {ping_ms} ms 📶\n— Owner ID: <code>{OWNER_ID}</code> 👑\n— Status: Ready & Purring! 🐾")
        logger.info(f"Owner ({user_id}) requested status.")
        await update.message.reply_html(status_msg)
    else:
        logger.warning(f"Unauthorized /status attempt by user {user_id}.")
        refusal_text = random.choice(OWNER_ONLY_REFUSAL).format(OWNER_ID=OWNER_ID)
        await update.message.reply_html(refusal_text)

# ADDED SAY COMMAND (Owner Only)
async def say(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a message as the bot (owner only)."""
    user = update.effective_user
    if user.id != OWNER_ID:
        logger.warning(f"Unauthorized /say attempt by user {user.id}.")
        refusal_text = random.choice(OWNER_ONLY_REFUSAL).format(OWNER_ID=OWNER_ID)
        await update.message.reply_html(refusal_text)
        return

    if not context.args:
        await update.message.reply_text("Mrow? What should I say? Usage: /say <your message>")
        return

    message_to_say = ' '.join(context.args)
    logger.info(f"Owner ({user.id}) is using /say in chat {update.effective_chat.id}")
    try:
        # Send message to the same chat where the command was issued
        await context.bot.send_message(chat_id=update.effective_chat.id, text=message_to_say)
        # Optionally, delete the owner's original /say command for cleaner appearance
        # try:
        #     await update.message.delete()
        #     logger.info("Deleted owner's /say command.")
        # except TelegramError as del_err:
        #     logger.warning(f"Could not delete owner's /say command: {del_err}")
    except TelegramError as e:
        logger.error(f"Failed to send message via /say: {e}")
        await update.message.reply_text(f"Meow! Couldn't send the message: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in /say: {e}", exc_info=True)
        await update.message.reply_text("Oops! Something went wrong with /say.")


# --- Main Function ---
def main() -> None:
    """Configures and runs the Telegram bot."""
    # Build Application
    application = Application.builder().token(BOT_TOKEN).build()

    # --- Handler Registration ---
    # Optional Debug Handler
    # from telegram.ext import MessageHandler, filters, ApplicationHandlerStop
    # application.add_handler(MessageHandler(filters.ALL, debug_receive_handler), group=-2)

    # Register all command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("github", github))
    application.add_handler(CommandHandler("owner", owner_info))
    application.add_handler(CommandHandler("gif", gif))
    application.add_handler(CommandHandler("photo", photo)) # Added photo handler
    application.add_handler(CommandHandler("meow", meow))
    application.add_handler(CommandHandler("nap", nap))
    application.add_handler(CommandHandler("play", play))
    application.add_handler(CommandHandler("treat", treat))
    application.add_handler(CommandHandler("zoomies", zoomies))
    application.add_handler(CommandHandler("judge", judge))
    application.add_handler(CommandHandler("attack", attack))
    application.add_handler(CommandHandler("status", status)) # Owner check inside function
    application.add_handler(CommandHandler("kill", kill))     # Public simulation
    application.add_handler(CommandHandler("punch", punch))   # Public simulation
    application.add_handler(CommandHandler("slap", slap))     # Public simulation
    application.add_handler(CommandHandler("bite", bite))     # Public simulation
    application.add_handler(CommandHandler("say", say))       # Added say handler (owner check inside)

    # --- Start the Bot ---
    logger.info(f"Bot starting polling... Owner ID: {OWNER_ID}")
    try:
        application.run_polling()
    except KeyboardInterrupt:
         logger.info("Bot stopped by user (Ctrl+C).")
    except Exception as e:
        logger.critical(f"CRITICAL: Bot crashed during runtime: {e}", exc_info=True)
        print(f"\n--- FATAL ERROR ---")
        print(f"Bot crashed: {e}")
        exit(1)
    finally:
        logger.info("Bot shutdown process initiated.")

    logger.info("Bot stopped.")

# --- Script Execution ---
if __name__ == "__main__":
    # Check for requests library dependency
    try:
        import requests
    except ImportError:
        print("\n--- DEPENDENCY ERROR ---")
        print("The 'requests' library is required for /gif and /photo commands.")
        print("Please install it using: pip install requests")
        exit(1)
    main()
