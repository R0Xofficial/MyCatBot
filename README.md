![MyCatBot](https://github.com/R0Xofficial/MyCatbot/blob/main/banner.png)

# MyCatBot - Your Fun, Furry Assistant

Meet **MyCatBot**, the playful and quirky cat-themed Telegram bot that will make your chats more fun! Whether you want to hear a random meow, trigger a zoomie attack, or just get some cuddles, this bot is here to make your day better — one paw at a time!

## Features

- **Purr-fectly Random Responses**: Get hilarious and unpredictable replies, just like a real cat.
- **Interactive Cat Actions**: Command the bot to meow, nap, pounce, and even have the zoomies!
- **Powerful Moderation Tools**: Behind the cute exterior is a powerful moderator with a full suite of commands to keep your chat safe.
- **Advanced Security**: Protect your group with a global ban system and a user blacklist.
- **Multi-Level Permissions**: Full control for the Owner, with trusted Sudo users to help manage the bot.

## How to run

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/R0Xofficial/MyCatBot catbot
    ```

2.  **Install requirements:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set up your environment variables:**
    Copy the template file:
    ```bash
    cp ~/catbot/envtemp.sh ~/catbot/env.sh
    ```
    Then, edit the file to add your tokens and IDs:
    ```bash
    nano ~/catbot/env.sh
    ```

4.  **Run the bot:**
    Navigate to the bot's directory and run it using the script:
    ```bash
    cd ~/catbot && . ./env.sh && python catbot.py
    ```
    To run the test version of the bot, use:
    ```bash
    cd ~/catbot && . ./env.sh && python catbot_test.py
    ```

---

## Command List<br>

### Bot Commands<br>
- **/start**: Shows the welcome message. ✨<br>
- **/help**: Shows this help message. ❓<br>
- **/github**: Get the link to my source code! 💻<br>
- **/owner**: Info about my designated human! ❤️<br>
- **/sudocmds**: List sudo commands. 👷‍♂️<br>

### User Commands<br>
- **/info <ID/@user/reply>**: Get info about a user. 👤<br>
- **/chatstat**: Get basic stats about the current chat. 📈<br>
- **/kickme**: Kick yourself from the chat. 👋<br>
- **/listadmins**: Show the list of administrators in the current chat. 📃 (Alias: `/admins`)<br>

### Management Commands<br>
- **/ban <ID/@user/reply> [Time] [Reason]**: Ban a user from the chat. ⛔️
- **/unban <ID/@user/reply>**: Unban a user from the chat. 🔓
- **/mute <ID/@user/reply> [Time] [Reason]**: Mute a user in the chat. 🚫
- **/unmute <ID/@user/reply>**: Unmute a user from the chat. 🎙
- **/kick <ID/@user/reply> [Reason]**: Kick a user from the chat. ⚠️
- **/promote <ID/@user/reply> [Title]**: Promote a user to administrator. 👷‍♂️
- **/demote <ID/@user/reply>**: Demote an administrator to a regular member. 🙍‍♂️
- **/pin <loud|notify>**: Pin the replied-to message. 📌
- **/unpin**: Unpin the replied-to message. 📍
- **/purge <silent>**: Deletes messages up to the replied-to message. 🗑
- **/report <ID/@user/reply> [reason]**: Report a user to the administrators. ⚠️

### Security
- **/enforcegban <yes/no>**: Enable/disable Global Ban enforcement in this chat (Chat Creator only). 🛡️

### 4FUN Commands
- **/gif**: Get a random cat GIF! 🖼️<br>
- **/photo**: Get a random cat photo! 📷<br>
- **/meow**: Get a random cat sound or phrase. 🔊<br>
- **/nap**: What's on a cat's mind during naptime? 😴<br>
- **/play**: Random playful cat actions. 🧶<br>
- **/treat**: Demand treats! 🎁<br>
- **/zoomies**: Witness sudden bursts of cat energy! 💥<br>
- **/judge**: Get judged by a superior feline. 🧐<br>
- **/fed**: I just ate, thank you! 😋<br>
- **/attack <@user/reply>**: Launch a playful attack! ⚔️<br>
- **/kill <@user/reply>**: Metaphorically eliminate someone! 💀<br>
- **/punch <@user/reply>**: Deliver a textual punch! 👊<br>
- **/slap <@user/reply>**: Administer a swift slap! 👋<br>
- **/bite <@user/reply>**: Take a playful bite! 😬<br>
- **/hug <@user/reply>**: Offer a comforting hug! 🤗<br>

### Sudo Commands<br>
- **/status**: Show bot status.<br>
- **/cinfo [Optional chat ID]**: Get detailed info about the current or specified chat.<br>
- **/say [Optional chat ID] [Your text]**: Send a message as the bot.<br>
- **/blist <ID/@user/reply> [Reason]**: Add a user to the blacklist.<br>
- **/unblist <ID/@user/reply>**: Remove a user from the blacklist.<br>
- **/gban <ID/@user/reply> [Reason]**: Ban a user globally.<br>
- **/ungban <ID/@user/reply>**: Unban a user globally.<br>
> *Note: Sudo users can use management commands like /ban, /mute, etc., even if they are not chat administrators.*<br>

### Owner Commands<br>
- **/leave [Optional chat ID]**: Make the bot leave a chat.<br>
- **/speedtest**: Perform an internet speed test.<br>
- **/listsudo**: List all users with sudo privileges.<br>
- **/addsudo <ID/@user/reply>**: Grant SUDO (bot admin) permissions to a user.<br>
- **/delsudo <ID/@user/reply>**: Revoke SUDO (bot admin) permissions from a user.<br>
