# TLOPO Bot

TLOPO Bot is an automated bot designed for the game "The Legend of Pirates Online" (TLOPO). This bot can detect loot and bosses in the game, allowing for automated interactions based on visual cues.

## Features

- Detects loot and bosses using image processing.
- Simulates mouse clicks and keyboard inputs.
- Configurable regions for loot and boss detection.
- Logging of actions and events for debugging and monitoring.

## Requirements

Before running the bot, ensure you have the following dependencies installed:

- Python 3.x
- `psutil`
- `opencv-python`
- `numpy`
- `Pillow`

You can install the required packages using pip:

```bash
pip install -r [requirements.txt](http://_vscodecontentref_/1)


Configuration
The bot uses a configuration file named bot_config.json to store settings such as detection regions and thresholds. You can force recalibration of these settings by running the bot with the --recalibrate flag.

Usage
To run the bot, execute the following command in your terminal:

To force recalibration of regions, use:

Logging
The bot logs its actions and events to a file named tlopo_bot.log. This log file can be useful for debugging and monitoring the bot's performance.