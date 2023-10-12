import subprocess

try:
    import requests
except:
    subprocess.check_call(["pip", "install", "requests"])
    import requests

try:
    from discord_webhook import DiscordWebhook, DiscordEmbed  # Documentation on https://github.com/lovvskillz/python-discord-webhook
except:
    subprocess.check_call(["pip", "install", "discord_webhook"])
    from discord_webhook import DiscordWebhook, DiscordEmbed

from datetime import datetime, timedelta
import json
import logging
import os
from pathlib import Path
import signal
import sys
import time
import traceback


# CRCON PLAYER COUNT CHECK DEFAULT VALUES: once CONFIG_FILE is created (with the first execution), you can edit the settings directly in there to avoid stopping this script.
CONFIG_FILE = "config.json"                 # DEFAULT: "config.json"            || You can use the full path to the config file if you'd like to have it in a particular folder that is not where this Python script is
SERVER_NAME = "YOUR_SERVER_NAME"            # It will be automatically updated after the first player count check, here you're just setting the default value
CRCON_URL = "http://localhost:7010"         # DEFAULT: "http://localhost:7010"  || This is the URL of your CRCON installation (more info: https://github.com/MarechJ/hll_rcon_tool/), use either "http(s)://IP:PORT" or "http(s)://SUB.DOMAIN.EXT"
PLAYER_COUNT_THRESHOLD = 5                  # DEFAULT: 5                        || When this threshold has been reached, the seed ping will be sent on Discord
PLAYER_COUNT_SEEDED = 30                    # DEFAULT: 30                       || When this threshold has been reached, the seed ping will NOT be sent on Discord
CHECK_INTERVAL_FAST = 60                    # DEFAULT: 60                       || Checking every 60 seconds when the server player count is less than PLAYER_COUNT_THRESHOLD, but higher than 0
CHECK_INTERVAL_SLOW = 600                   # DEFAULT: 600                      || Checking every 10 minutes when the server player count is 0
SEED_COOLDOWN_TIME = 18 * 3600              # DEFAULT: 18 * 3600                || Checking 18 hours after a seed ping has been sent

# DISCORD WEBHOOK DEFAULT VALUES: once CONFIG_FILE is created (with the first execution), you can edit the settings directly in there to avoid stopping this script.
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/11...17/scf...pJB"                # If you don't know how to get one, check the Discord Support: https://support.discord.com/hc/articles/228383668-Intro-to-Webhooks
DISCORD_WEBHOOK_CONTENT = "@here\nHELLO WORLD, I AM AN AUTOMATED SEEDING MESSAGE."        # IMPORTANT: This is the actual Discord ping -- mention a role with <@&ROLE_ID>.
DISCORD_WEBHOOK_ALLOWED_MENTIONS = {
    "parse": ["roles", "users", "everyone"],
    "roles": [],
    "users": []
}
EMBED_TITLE = ""                                                                # DEFAULT: ""      || Keep this empty to let it update automatically with the current server name
EMBED_BODY = "Hey, we're seeding our server and we could use your help to get it populated!\n\n- Players currently online: **{0}**\n- Current map: **{1}**"
EMBED_COLOR = "03b2f8"                                                          # DEFAULT: "03b2f8"
EMBED_FOOTER_TEXT = "Made by dr_nylon for the HLL Community."                   # DEFAULT: "Made by dr_nylon for the HLL Community."
EMBED_FOOTER_ICON_URL = "https://avatars.githubusercontent.com/u/37863835"      # DEFAULT: "https://avatars.githubusercontent.com/u/37863835" <-- dr_nylon's avatar


# Set up logging
logging.basicConfig(filename="hll_seed_ping.log", level=logging.INFO)
logger = logging.getLogger("hll_seed_ping")


# Function to create a virtual environment if it doesn't exist
def create_virtualenv():
    try:
        subprocess.check_call(["python3", "-m", "venv", "venv"])
        print(f"Virtual Environment CREATED.")

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to create virtual environment: {e}")
        sys.exit(1)


# Function to activate the virtual environment
def activate_virtualenv():
    activate_command = os.path.join("venv", "bin", "activate")
    if os.path.exists(activate_command):
        subprocess.Popen(f"source {activate_command}", shell=True, executable="/bin/bash")
    print(f"Virtual Environment ACTIVATED.")


# Function to install required packages
def install_required_packages():
    try:
        subprocess.check_call(["venv/bin/pip", "install", "requests"])
        subprocess.check_call(["venv/bin/pip", "install", "discord_webhook"])
        print(f"The required modules were INSTALLED.")

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install required packages: {e}")
        sys.exit(1)


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


# Function to save changes to the configuration file (see "CONFIG_FILE" above)
def save_config():
    with open(CONFIG_FILE, 'w') as file:
        json.dump(config, file, indent=4, cls=DateTimeEncoder)
    print(f"The configuration file {CONFIG_FILE} has been successfully SAVED.")


# Function to load the configuration file (see "CONFIG_FILE" above)
def load_config():
    global config
    try:
        with open(CONFIG_FILE, 'r') as file:
            config = json.load(file)
            if 'time_last_seed_message' in config:
                config['time_last_seed_message'] = datetime.fromisoformat(config['time_last_seed_message'])
            else:
                config["time_last_seed_message"] = datetime(1970, 1, 1)
        print(f"The configuration file {CONFIG_FILE} has been successfully OPENED.")

    except FileNotFoundError:
        # Handle no CONFIG_FILE
        print(f"No configuration file found. Creating {CONFIG_FILE} with the default settings.")
        config = {
            "server_name": SERVER_NAME,
            "api_url": CRCON_URL + "/api/public_info",
            "player_count_threshold": PLAYER_COUNT_THRESHOLD,
            "player_count_seeded": PLAYER_COUNT_SEEDED,
            "check_interval": CHECK_INTERVAL_SLOW,
            "seed_cooldown_time": SEED_COOLDOWN_TIME,
            "last_player_count": 0,
            "time_last_player_count": datetime(1970, 1, 1),
            "time_last_seed_message": datetime(1970, 1, 1),
            "webhook_url": DISCORD_WEBHOOK_URL,
            "webhook_content": DISCORD_WEBHOOK_CONTENT,
            "webhook_allowed_mentions": DISCORD_WEBHOOK_ALLOWED_MENTIONS,
            "embed_title": EMBED_TITLE,
            "embed_body": EMBED_BODY,
            "embed_color": EMBED_COLOR,
            "embed_footer_text": EMBED_FOOTER_TEXT,
            "embed_footer_icon_url": EMBED_FOOTER_ICON_URL
        }
        save_config()

    except json.decoder.JSONDecodeError:
        # Handle invalid JSON
        print(f"The configuration file {CONFIG_FILE} contains invalid JSON. Creating a new one with the default settings.")
        config = {
            "server_name": SERVER_NAME,
            "api_url": CRCON_URL + "/api/public_info",
            "player_count_threshold": PLAYER_COUNT_THRESHOLD,
            "player_count_seeded": PLAYER_COUNT_SEEDED,
            "check_interval": CHECK_INTERVAL_SLOW,
            "seed_cooldown_time": SEED_COOLDOWN_TIME,
            "last_player_count": 0,
            "time_last_player_count": datetime(1970, 1, 1),
            "time_last_seed_message": datetime(1970, 1, 1),
            "webhook_url": DISCORD_WEBHOOK_URL,
            "webhook_content": DISCORD_WEBHOOK_CONTENT,
            "webhook_allowed_mentions": DISCORD_WEBHOOK_ALLOWED_MENTIONS,
            "embed_title": EMBED_TITLE,
            "embed_body": EMBED_BODY,
            "embed_color": EMBED_COLOR,
            "embed_footer_text": EMBED_FOOTER_TEXT,
            "embed_footer_icon_url": EMBED_FOOTER_ICON_URL
        }
        save_config()


# Function to send Discord message through a webhook
def send_discord_message(player_count, current_map):
    try:
        print()
        print(f"SEED PING MESSAGE")
        
        # Create the message using the webhook
        webhook = DiscordWebhook(url=config["webhook_url"], rate_limit_retry=True, content=config["webhook_content"], allowed_mentions=config["webhook_allowed_mentions"])
        print(f"The Discord webhook as been CREATED.")

        # Add embed object to webhook
        if EMBED_TITLE == "":
            embed = DiscordEmbed(title=config["server_name"], description=config["embed_body"].format(player_count, current_map), color=config["embed_color"])
        else:
            embed = DiscordEmbed(title=EMBED_TITLE, description=config["embed_body"].format(player_count, current_map), color=config["embed_color"])
        print(f"The embed object for the Discord webhook as been CREATED.")

        # Set author
        #embed.set_author(name="Author Name", url="author url", icon_url="author icon url")

        # Add fields to the embed
        #embed.add_embed_field(name="Field 1", value="Lorem ipsum", inline=False)
        #embed.add_embed_field(name="Field 2", value="dolor sit", inline=False)
        #embed.add_embed_field(name="Field 3", value="amet consetetur", inline=True)
        #embed.add_embed_field(name="Field 4", value="sadipscing elitr", inline=True)

        # Set image
        #embed.set_image(url="your image url")

        # Set thumbnail
        #embed.set_thumbnail(url="your thumbnail url")

        # Set footer
        embed.set_footer(text=config["embed_footer_text"], icon_url=config["embed_footer_icon_url"])
        print(f"The footer of the embed object has been set.")

        # Set timestamp (default is now) accepted types are int, float and datetime
        embed.set_timestamp()
        print(f"The footer timestamp of the embed object has been set.")

        # Finally, add the embed object to the webhook message
        webhook.add_embed(embed)
        print(f"The embed object has been appended to the webhook message.")

        # Send the webhook message
        webhook.execute()
        print(f'Discord webhook message sent at {datetime.now().strftime("%Y/%m/%d %H:%M:%S")}')
        print()

        # TODO: Add logic to edit the Discord message sent until the server is seeded.
        #    webhook.content = "After Edit"
        #    time.sleep(10)
        #    webhook.edit()

    except Exception as e:
        logger.error(f"An error occurred while trying to send the Discord message:\n{traceback.format_exc()}")


# Function to check player count
def check_player_count():
    try:
        print()
        print(f"PLAYER COUNT CHECK")
        response = requests.get(config["api_url"])
        response.raise_for_status()
        data = response.json()
        server_name = data["result"]["name"]
        player_count = data["result"]["player_count"]
        current_map = data["result"]["current_map"]["human_name"]

        print(f"Preparing data to save to {CONFIG_FILE}...")
        config["server_name"] = server_name
        config["last_player_count"] = player_count
        config["time_last_player_count"] = datetime.now()

        # TODO: Add logic to avoid sending messages when the server is "dying" || T0: 60 players, T1: 50 players, T2: 40 players, T3: 39 players --> As things stand now, it will send a seeding message.
        # POSSIBLE SOLUTION:
        #    - TIE THE COOLDOWN TO ONLY THE SEEDING MESSAGE, NOT THE WHOLE SCRIPT EXECUTION
        #        - ALWAYS CHECK FOR PLAYER_COUNT: IF PLAYER_COUNT == 0, THEN CHECK EVERY 15-30 MINS
        #        - NESTED WHILE LOOPS?

        if 0 < player_count < config["player_count_threshold"]:
            print(f"{player_count} player(s) online: setting the check interval to {CHECK_INTERVAL_FAST}.")
            config["check_interval"] = CHECK_INTERVAL_FAST
        elif config["player_count_threshold"] <= player_count < config["player_count_seeded"]:
            send_discord_message(player_count, current_map)
            config["time_last_seed_message"] = datetime.now()
            print(f"Setting the next check in {SEED_COOLDOWN_TIME} seconds.")
            config["check_interval"] = SEED_COOLDOWN_TIME
        else:
            print(f"No players online: setting the check interval to {CHECK_INTERVAL_SLOW}.")
            config["check_interval"] = CHECK_INTERVAL_SLOW

        save_config()

    except Exception as e:
        logger.error(f"An error occurred trying to request the player count from the CRCON server:\n{traceback.format_exc()}")


# Signal handler for SIGTERM and SIGINT
def handle_signals(signum, frame):
    print()
    print(f"Received the shutdown signal. Saving the config file...")
    save_config()
    print(f"Shutting down...")
    print()
    sys.exit(0)


# Main function
def main():
    try:
        # Check if the virtual environment exists and create it if it doesn't
        if not os.path.exists("venv"):
            create_virtualenv()
            activate_virtualenv()
            install_required_packages()

        # Register the signal handler for SIGTERM and SIGINT
        signal.signal(signal.SIGTERM, handle_signals)
        signal.signal(signal.SIGINT, handle_signals)

        print()
        print(f"==========================================================")
        print(f"||  AUTOMATED DISCORD SEED PING FOR THE HLL CRCON TOOL  ||")
        print(f"==========================================================")
        print()
        print(f"    CREATED BY: dr_nylon (https://github.com/adevnylo)")
        print()

        if len(sys.argv) > 1 and sys.argv[1] == "--daemon":
            print(f"             ===|| SERVICE MODE STARTED ||===")
            print()

            try:
                while True:
                    load_config()
                    last_seed_time = config["time_last_seed_message"]
                    if datetime.now() >= last_seed_time + timedelta(seconds=config["check_interval"]):
                        check_player_count()
                    print()
                    print(f'Waiting until {(datetime.now() + timedelta(seconds=config["check_interval"])).strftime("%Y/%m/%d %H:%M:%S")} for the next check...')
                    time.sleep(config["check_interval"])

            except Exception as e:
                logger.error(f"An unexpected error occurred in the daemon:\n{traceback.format_exc()}")
                sys.exit(1)
        else:
            print(f"              ===|| PRINT MODE STARTED ||===")
            print()
            load_config()

            print()
            print(f"==========================================================")
            print(f'||                      STATISTICS                      ||')
            print(f"==========================================================")
            print()

            if config["time_last_player_count"] == datetime(1970, 1, 1):
                print(f'Server: {SERVER_NAME} (Default value set in the Python script)')
                print(f"Player Count: N/A")
                print(f"Last CRCON Check: Never")
                print(f"Last Seed Ping: Never")
                print(f"Next Scheduled Check: N/A")
                print()
                print(f'PLEASE NOTE: Run the script using "--daemon" or run the SystemD service.')
            else:
                print(f'Server: {config["server_name"]}')
                print(f'Player Count: {config["last_player_count"]}')
                print(f'Last CRCON Check: {datetime.strptime(config["time_last_player_count"], "%Y-%m-%dT%H:%M:%S.%f").strftime("%Y/%m/%d %H:%M:%S")}')
                if config["time_last_seed_message"] == datetime(1970, 1, 1):
                    print(f"Last Seed Ping: Never")
                else:
                    print(f'Last Seed Ping: {config["time_last_seed_message"].strftime("%Y/%m/%d %H:%M:%S")}')
                print(f'Next Scheduled Check: {(datetime.strptime(config["time_last_player_count"], "%Y-%m-%dT%H:%M:%S.%f") + timedelta(seconds=int(config["check_interval"]))).strftime("%Y/%m/%d %H:%M:%S")}')

            print()
            print(f"==========================================================")
            print(f'||            CURRENT "SERVICE MODE" CONFIGS            ||')
            print(f"==========================================================")
            print()
            print(f'api_url: {config["api_url"]}')
            print(f'player_count_threshold: {config["player_count_threshold"]}')
            print(f'check_interval: {config["check_interval"]}')
            print(f'seed_cooldown_time: {config["seed_cooldown_time"]}')
            print(f'webhook_url: {config["webhook_url"]}')

            if "\n" in config["webhook_content"]:
                print(f"webhook_content: [MULTIPLE LINES BELOW]")
                print()
                print(f"      =======||  START OF WEBHOOK CONTENT  ||=======")
                print()
                print(f'{config["webhook_content"]}')
                print()
                print(f"       =======||  END OF WEBHOOK CONTENT  ||=======")
                print()
            else:
                print(f'webhook_content: {config["webhook_content"]}')

            if EMBED_TITLE == "":
                print(f'embed_title: {EMBED_TITLE} (Overrides the content of {CONFIG_FILE})')
            else:
                print(f'embed_title: {config["embed_title"]}')

            if "\n" in config["embed_body"]:
                print(f"embed_body: [MULTIPLE LINES BELOW]")
                print()
                print(f"      =======||  START OF EMBED BODY TEXT  ||=======")
                print()
                print(f'{config["embed_body"]}')
                print()
                print(f"       =======||  END OF EMBED BODY TEXT  ||=======")
                print()
            else:
                print(f'embed_body: {config["embed_body"]}')

            print(f'embed_color: {config["embed_color"]}')
            print(f'embed_footer_text: {config["embed_footer_text"]}')
            print(f'embed_footer_icon_url: {config["embed_footer_icon_url"]}')
            print()

    except Exception as e:
        logger.error(f"An unexpected error occurred:\n{traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()
