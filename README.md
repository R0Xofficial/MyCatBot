![MyCatBot](https://github.com/R0Xofficial/MyCatbot/blob/main/banner.png)

# MyCatBot - Your Fun, Furry Assistant

Meet **MyCatBot**, the playful and quirky cat-themed Telegram bot that will make your chats more fun! Whether you want to hear a random meow, trigger a zoomie attack, or just get some cuddles, this bot is here to make your day better — one paw at a time!

## Features

- **Random Cat Responses**: Get hilarious and random responses, just like your real-life furry friend would give.
- **Cat-Like Actions**: Watch the bot act like a cat, from zoomies to pouncing and cuddles.
- **Simple and Fun Commands**: Easy-to-use commands for everyone, whether you're looking to chat or just have a laugh.
- **Owner & SUDO Commands**: Exclusive commands to manage things and keep the cat-spiracy under control.

## How to run

1. Clone repo:
   
Run **git clone https://github.com/R0Xofficial/MyCatBot catbot**

3. Install requirements
   
Run **pip install -r requirements.txt**

2. Run **cp ~/catbot/envtemp.sh ~/catbot/env.sh**

3. Set your environment in env.sh (use this command: **nano ~/catbot/env.sh**)

4. To run bot use command:

**cd ~/catbot && . ./env.sh && python catbot.py**

If you want run test bot version use command:

**cd ~/catbot && . ./env.sh && python catbot_test.py**

# Bot Commands:
/start - Shows the welcome message. ✨<br>
/help - Shows this help message. ❓<br>
/github - Get the link to my source code! 💻<br>
/owner - Info about my designated human! ❤️<br>
/sudocmds - List sudo commands. 👷‍♂️<br>

# User Commands:
/info <ID/@user/reply> - Get info about a user. 👤<br>
/chatstat - Get basic stats about the current chat. 📈<br>
/kickme - Kick yourself from chat. 👋<br>
/listadmins - Show the list of administrators in the current chat. 📃<br>
Note: /admins works too

# Management Commands:
/ban <ID/@user/reply> [Time] [Reason] - Ban user in chat. ⛔️<br>
/unban <ID/@user/reply> - Unban user in chat. 🔓<br>
/mute <ID/@user/reply> [Time] [Reason] - Mute user in chat. 🚫<br>
/unmute <ID/@user/reply> - Unmute user in chat. 🎙 <br>
Note: [Time] is optional<br>
/kick <ID/@user/reply> [Reason] - Kick user from chat. ⚠️<br>
/promote <ID/@user/reply> [Title] - Promote a user to administrator. 👷‍♂️<br>
Note: [Title] is optional<br>
/demote <ID/@user/reply> - Demote an administrator to a regular member. 🙍‍♂️<br>
/pin <loud|notify> - Pin the replied message. 📌<br>
/unpin - Unpin the replied message. 📍<br>
/purge <silent> - Deletes user messages up to the replied-to message. 🗑<br>
/report <ID/@user/reply> [reason] - Report user. ⚠️<br>

Security:
/enforcegban <yes/no> - Enable/disable Global Ban enforcement in this chat. 🛡️<br>
(Chat Creator only)

4FUN Commands:
/gif - Get a random cat GIF! 🖼️<br>
/photo - Get a random cat photo! 📷<br>
/meow - Get a random cat sound or phrase. 🔊<br>
/nap - What's on a cat's mind during naptime? 😴<br>
/play - Random playful cat actions. 🧶<br>
/treat - Demand treats! 🎁<br>
/zoomies - Witness sudden bursts of cat energy! 💥<br>
/judge - Get judged by a superior feline. 🧐<br>
/fed - I just ate, thank you! 😋<br>
/attack <@user/reply> - Launch a playful attack! ⚔️<br>
/kill <@user/reply> - Metaphorically eliminate someone! 💀<br>
/punch <@user/reply> - Deliver a textual punch! 👊<br>
/slap <@user/reply> - Administer a swift slap! 👋<br>
/bite <@user/reply> - Take a playful bite! 😬<br>
/hug <@user/reply> - Offer a comforting hug! 🤗<br>

# Sudo Commands:
/status - Show bot status.<br>
/cinfo [Optional chat ID] - Get detailed info about the current or specified chat.<br>
/say [Optional chat ID] [Your text] - Send message as bot.<br>
/blist <ID/@user/reply> [Reason] - Add user to blacklist.<br>
/unblist <ID/@user/reply> - Remove user from blacklist.<br>
/gban <ID/@user/reply> [Reason] - Ban user globally.<br>
/ungban <ID/@user/reply> - Unban user globally.<br><br>

<i>Note: Commands: /ban, /unban, /mute, /unmute, /kick, /pin, /unpin, /purge; can be used by sudo users even if they are not chat creator/administrator.</i>

# Owner Commands:
/leave [Optional chat ID] - Make the bot leave a chat.<br>
/speedtest - Perform an internet speed test.<br>
/listsudo - List all users with sudo privileges.<br>
/addsudo <ID/@user/reply> - Grants SUDO (bot admin) permissions to a user.<br>
/delsudo <ID/@user/reply> - Revokes SUDO (bot admin) permissions from a user.<br>
