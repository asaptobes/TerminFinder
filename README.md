# Stuttgart Expat Termin Hunter 🤖

This is an automated tool to help expats find elusive residence permit appointments at the Stuttgart Ausländerbehörde. 

## Requirements
You must have Python installed. Then, install the required libraries:
`pip install playwright python-telegram-bot`
`playwright install`

## How it works
This script continuously checks the Konsentas portal every 60 seconds. When an appointment drops, it bypasses the menus, sounds an audio alarm, and sends a Telegram notification to your phone so you can claim it before it's gone.

## Setup Instructions
1. Download the code to your computer.
2. Open the file and add your personal details to the `MY_DETAILS` section.
3. Add your own Telegram Bot Token (so the bot messages *you*, not me).
4. Run the script!

*Note: Please use responsibly. Do not lower the 60-second timer, or you risk getting your IP address banned by the municipality.*
