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
/start - Shows the welcome message. ✨

/help - Shows this help message. ❓

/github - Get the link to my source code! 💻

/owner - Info about my designated human! ❤️

# User Commands:
/info [ID/reply/@user] - Get info about a user. 👤

/chatstat - Get basic stats about the current chat. 📈

/kickme - Kick yourself from chat. 👋

/listadmins - Show the list of administrators in the current chat.
Note: /admins works too

# Management Commands:
/ban [ID/reply/@user] [Time] [Reason] - Ban user in chat. ⛔️

/mute [ID/reply/@user] [Time] [Reason] - Mute user in chat. 🚫<br>
Note: [Time] is optional

/kick [ID/reply/@user] [Reason] - Kick user from chat. ⚠️

/promote [ID/reply/@user] [admin_title] - Promote a user to administrator. 👷‍♂️<br>
Note: [admin_title] is optional

/demote [ID/reply/@user] - Demote an administrator to a regular member. 🙍‍♂️

/pin [silent] - Pin the replied message. 📌

/unpin - Unpin the replied message. 📍

/purge [silent] - Deletes user messages up to the replied-to message.

# 4FUN Commands:
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

## (Note: Owner cannot be targeted by attack/kill/punch/slap/bite/hug)

# SUDO commands:

/status - Show bot status.

/cinfo [optional_chat_ID] - Get detailed info about the current or specified chat. 

/say [optional_chat_id] [your text] - Send message as bot.

/blist [ID/reply/@user] [reason] - Add user to blacklist.

/unblist [ID/reply/@user] - Remove user from blacklist.

# Owner Commands:

/leave [optional_chat_id] - Make the bot leave a chat.

/speedtest - Perform an internet speed test.

/listsudo - List all users with sudo privileges.

/addsudo [ID/reply/@user] - Grants SUDO (bot admin) permissions to a user.

/delsudo [ID/reply/@user] - Revokes SUDO (bot admin) permissions from a user.
