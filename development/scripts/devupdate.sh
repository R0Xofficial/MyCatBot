#!/bin/bash

BOT_DIR="~/catbot/development"
PYTHON_SCRIPT_NAME="dev.py"
LOG_FILE="${BOT_DIR}/logs/update_run_dev.log"
ENV_SCRIPT_PATH="${BOT_DIR}/env.sh"
mkdir "${BOT_DIR}/logs"

echo "--------------------------------------" >> "$LOG_FILE"
echo "$(date '+%Y-%m-%d %H:%M:%S %Z'): --- Starting Bot Update Script ---" >> "$LOG_FILE"

echo "$(date): Attempting to close current bot process ($PYTHON_SCRIPT_NAME)..." >> "$LOG_FILE"
pkill -f "$PYTHON_SCRIPT_NAME" >> "$LOG_FILE" 2>&1
PKILL_STATUS=$?
if [ $PKILL_STATUS -eq 0 ]; then
    echo "$(date): pkill command succeeded (found and signaled process/es)." >> "$LOG_FILE"
elif [ $PKILL_STATUS -eq 1 ]; then
    echo "$(date): pkill command found no processes matching $PYTHON_SCRIPT_NAME (this might be OK if bot was already stopped)." >> "$LOG_FILE"
else
    echo "$(date): pkill command failed with status $PKILL_STATUS." >> "$LOG_FILE"
fi
sleep 3

echo "$(date): Navigating to bot directory: $BOT_DIR" >> "$LOG_FILE"
cd "$BOT_DIR" || { echo "$(date): ERROR - Failed to cd to $BOT_DIR. Aborting." >> "$LOG_FILE"; exit 1; }

echo "$(date): Updating source code from git..." >> "$LOG_FILE"
git pull origin main >> "$LOG_FILE" 2>&1
GIT_PULL_STATUS=$?
echo "$(date): Git pull finished with status $GIT_PULL_STATUS." >> "$LOG_FILE"

if [ $GIT_PULL_STATUS -ne 0 ]; then
    echo "$(date): ERROR - Git pull failed. Bot not restarted. Check $LOG_FILE for details." >> "$LOG_FILE"
    git status >> "$LOG_FILE" 2>&1
    git diff >> "$LOG_FILE" 2>&1
    exit 1
fi

echo "$(date): Setting up environment and starting new bot process..." >> "$LOG_FILE"
if [ -f "$ENV_SCRIPT_PATH" ]; then
    echo "$(date): Sourcing environment from $ENV_SCRIPT_PATH" >> "$LOG_FILE"
    . "$ENV_SCRIPT_PATH"
else
    echo "$(date): WARNING - $ENV_SCRIPT_PATH not found. Bot might not start correctly." >> "$LOG_FILE"
fi

nohup python "$PYTHON_SCRIPT_NAME" >> "${BOT_DIR}/bot_run.log" 2>&1 &
NOHUP_STATUS=$?
if [ $NOHUP_STATUS -eq 0 ]; then
    echo "$(date): New bot process ($PYTHON_SCRIPT_NAME) launched in background via nohup." >> "$LOG_FILE"
else
    echo "$(date): ERROR - Failed to launch new bot process with nohup. Status: $NOHUP_STATUS." >> "$LOG_FILE"
fi

echo "$(date): --- Bot Update Script Finished ---" >> "$LOG_FILE"
echo "--------------------------------------" >> "$LOG_FILE"
exit 0
