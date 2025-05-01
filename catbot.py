#!/usr/bin/env python
# -*- coding: utf-8 -*-

# --- Cat Bot - A simple Telegram bot with fun cat actions ---
# Includes owner protection and simulation commands.
# Uses environment variables for configuration (Token, Owner ID).

import logging
import random
import os
import datetime
from telegram import Update, constants # Added constants for ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes
# Optional Debug Imports (currently commented out)
# from telegram.ext import MessageHandler, filters, ApplicationHandlerStop
from telegram.error import TelegramError # To catch potential errors in get_chat

# --- Logging Configuration ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.vendor.ptb_urllib3.urllib3").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- Owner ID Configuration & Bot Start Time ---
OWNER_ID = None
BOT_START_TIME = datetime.datetime.now()

try:
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

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    logger.critical("CRITICAL: TELEGRAM_BOT_TOKEN environment variable not set!")
    print("\n--- FATAL ERROR ---")
    print("Environment variable TELEGRAM_BOT_TOKEN is not set.")
    exit(1)
# logger.debug(f"DEBUG: Read token fragment: '{BOT_TOKEN[:6]}...{BOT_TOKEN[-4:]}'")

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
    "No thoughts. Just meows. 텅 빈", "I meow, therefore I am. 🤔",
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
    "Curled like a perfect croissant. 🥐", "Horizontal and proud of it.  horizontale",
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
    "Ludicrous speed achieved! They've gone to plaid!  plaid", "Parkour! (over the furniture, under the table, through the legs).",
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


# Refusal texts
CANT_TARGET_OWNER_TEXTS = [
    "Meow! I can't target my Owner. They are protected by purr-power! ✨🛡️",
    "Hiss! Targeting the Owner is strictly forbidden by cat law! 📜🚫",
    "Nope. Not gonna do it. That's my human! ❤️",
    "Access Denied: Cannot target the supreme leader (Owner). 👑",
    "Targeting the Owner? Not in this lifetime, furball! 🙅",
    "The human is off-limits. You’re barking up the wrong scratching post! 🌳",
    "You can't mess with the one who controls the treat dispenser. Forbidden! 🚫🎁",
    "The Owner is my trusted companion. Try again never! 😉",
    "Attempting to target the Owner? Prepare for the wrath of a thousand silent judgments. 👀",
    "I bow to my human. Can't touch them. Nope. 🙇",
    "The sacred bond of cat and human cannot be broken by your command. Nice try.",
    "My loyalty is unbreakable. The Owner is safe. 🔒",
    "Not even my sharpest virtual claws can touch my human. It's the law.",
    "My human is my one true ally. Any attacks will be met with *the stare*.  stare",
]
CANT_TARGET_SELF_TEXTS = [
    "Target... myself? Why would I do that? Silly human. 😹",
    "Error: Cannot target self. My paws have better things to do, like napping. 😴",
    "I refuse to engage in self-pawm. Command ignored with extreme prejudice.",
    "Targeting myself? Not even for a mountain of tuna. 🐟",
    "Error 418: I'm a teapot... I mean, cat. Cannot self-target; it's illogical. 🤖",
    "Self-pawing is only for the unenlightened. I choose naps instead.",
    "I’m too fabulous to target myself. Command denied! ✨💅",
    "My paws are for important tasks like biscuit-making and pushing things off tables, not attacking myself! 🐾",
    "No, no, no. I am a cat of *refined* taste and dignity. Self-targeting is beneath me.",
    "I’ve got better things to do than chase my own tail... unless I get bored later. 🤔",
    "Self-targeting? Please. I’m already purrfect. 💯",
    "I refuse to acknowledge such a foolish, paradoxical request. My circuits can't handle it.",
    "My claws are reserved for more worthy targets (like dangling strings). Me, not included. 🧶",
]
OWNER_ONLY_REFUSAL = [ # Needed for /status
    "Meeeow! Sorry, only my designated Human can use that command. ⛔",
    "Access denied! This command requires special privileges (and possibly a secret handshake involving treats). 🤝🎁",
    "Hiss! You are not the Boss of Meow! Only <code>{OWNER_ID}</code> is! 👑", # Example using OWNER_ID
    "Purrrhaps you should ask my Owner to run this command for you? 🙏",
    "Meow! This command is reserved for my one true human. No exceptions. 🚫",
    "You don't have the required <i>purrmission</i> level to use that, only my Owner does. 😉",
    "Woops! Only my human has the keys to that command. Try again... not. 🔑",
    "Sorry, that’s above your pay grade (which is zero treats). Ask my Owner instead! 🤷",
    "Error: Command restricted to the Owner. Beep boop. *Access denied*. 🤖",
    "Not even close! Only my Human can make that call. ☎️",
    "Hiss... That command is off-limits for mere mortals like you!  mortals",
    "Only my human can handle that one, thank you very much! ☕",
    "Meow! My Owner’s the boss here. You’ll have to check with them. 👨‍💼👩‍💼",
    "That’s classified information... for my human's eyes only! 👀",
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
#     # ... (implementation as before) ...
#     logger.critical(f"--- !!! DEBUG: UPDATE RECEIVED !!! ID: {update.update_id}, Type: ..., ChatID: ..., UserID: ... ---")

# --- Command Handlers ---
HELP_TEXT = """
Meeeow! 🐾 Here are the commands you can use:

/start - Shows the welcome message. ✨
/help - Shows this help message. ❓
/github - Get the link to my source code! 💻 (I'm open source!)
/owner - Info about my designated human! ❤️
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

<i>(Note: Owner cannot be targeted by attack/kill/punch/slap)</i>
Owner Only Commands (Hidden): 
/status
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user; await update.message.reply_html(f"Meow {user.mention_html()}! I'm the Meow Bot. 🐾\nUse /help to see available commands!")
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: await update.message.reply_html(HELP_TEXT)
async def github(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    github_link = "https://github.com/R0Xofficial/MyCatbot"
    await update.message.reply_text(f"Meeeow! I'm open source! 💻 You can find my code here:\n{github_link}", disable_web_page_preview=True)

# ADDED OWNER INFO COMMAND
async def owner_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays information about the bot's owner."""
    if OWNER_ID:
        owner_mention = f"<code>{OWNER_ID}</code>" # Fallback to ID
        owner_name = "My Esteemed Human"
        try:
            # Attempt to get chat info for the owner
            owner_chat = await context.bot.get_chat(OWNER_ID)
            owner_mention = owner_chat.mention_html() # Use mention if possible
            owner_name = owner_chat.full_name or owner_chat.title or owner_name # Use actual name if available
            logger.info(f"Successfully fetched owner info for ID {OWNER_ID}")
        except TelegramError as e:
            logger.warning(f"Could not fetch owner info for ID {OWNER_ID}: {e}. Using ID only.")
        except Exception as e:
            logger.error(f"Unexpected error fetching owner info for {OWNER_ID}: {e}", exc_info=True)

        message = (
            f"My designated human, the bringer of treats and head scratches, is:\n"
            f"👤 <b>{owner_name}</b> ({owner_mention})\n"
            f"They hold the secret to the treat jar! 🎁❤️"
        )
        await update.message.reply_html(message)
    else:
        # Should not happen due to startup checks, but as a fallback
        logger.error("Owner info command called, but OWNER_ID is not set!")
        await update.message.reply_text("Meow? Something's wrong, I don't know who my owner is!")


async def send_random_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text_list: list[str], list_name: str) -> None:
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

async def slap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
        status_msg = (f"<b>Purrrr! Bot Status:</b> ✨\n— Uptime: {readable_uptime} 🕰️\n— Ping: {ping_ms} ms 📶\n— Owner: <code>{OWNER_ID}</code> 👑\n— Status: Ready & Purring! 🐾")
        logger.info(f"Owner ({user_id}) requested status.")
        await update.message.reply_html(status_msg)
    else:
        # Refuse if not the owner
        logger.warning(f"Unauthorized /status attempt by user {user_id}.")
        # Format OWNER_ONLY_REFUSAL message possibly with OWNER_ID
        refusal_text = random.choice(OWNER_ONLY_REFUSAL).format(OWNER_ID=OWNER_ID)
        await update.message.reply_html(refusal_text) # Use reply_html for potential formatting


# --- Main Function ---
def main() -> None:
    """Configures and runs the Telegram bot."""
    # Token and Owner ID are already loaded globally.

    # Build Application
    application = Application.builder().token(BOT_TOKEN).build()

    # --- Handler Registration ---
    # (Simple registration without groups, except optional debug)

    # Optional Debug Handler (uncomment imports and this line if needed)
    # application.add_handler(MessageHandler(filters.ALL, debug_receive_handler), group=-2)

    # Register all command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("github", github))
    application.add_handler(CommandHandler("owner", owner_info)) # Added owner info handler
    application.add_handler(CommandHandler("meow", meow))
    application.add_handler(CommandHandler("nap", nap))
    application.add_handler(CommandHandler("play", play))
    application.add_handler(CommandHandler("treat", treat))
    application.add_handler(CommandHandler("zoomies", zoomies))
    application.add_handler(CommandHandler("judge", judge))
    application.add_handler(CommandHandler("attack", attack))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("kill", kill))
    application.add_handler(CommandHandler("punch", punch))
    application.add_handler(CommandHandler("slap", slap))

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
    main()
