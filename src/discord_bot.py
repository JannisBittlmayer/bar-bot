import os
import discord
import json
import requests
import time


# Load config from config.json

script_dir = os.path.dirname(os.path.realpath(__file__))
config_path = os.path.join(script_dir, 'config.json')
with open(config_path) as config_file:
    config = json.load(config_file)
    token = config['token']
    guild_id = config['optional_guild_id']
    rest_order_url = config['rest_order_url']


# To use additional logging, check https://discordpy.readthedocs.io/en/stable/logging.html


# Adapted from https://github.com/Rapptz/discord.py/blob/v2.3.2/examples/app_commands/basic.py

class MyClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        # Create a command tree
        self.tree = discord.app_commands.CommandTree(self)

    if guild_id != "":
        # By doing so, we don't have to wait up to an hour until slash commands are shown to the end-user.
        async def setup_hook(self):
            # This copies the global commands over to our guild.
            myGuild = discord.Object(id=guild_id)
            self.tree.copy_global_to(guild=myGuild)
            await self.tree.sync(guild=myGuild)


# Pick necessary discord intents

intents = discord.Intents.default()
intents.message_content = True


# Create client

client = MyClient(intents=intents)


# Log when bot is ready

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')


# Basic slash command to check if bot is working

@client.tree.command()
async def hello(interaction: discord.Interaction):
    """Says hello!"""
    await interaction.response.send_message(f'Hi, {interaction.user.mention}')


# Get order message

@client.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == client.user:
        return
    # Ignore capitalization of message content
    message_content = message.content.lower()
    # Act upon message if it contains a keyword and the bot is mentioned
    keywords = ['order', 'bestell']
    if any(keyword in message_content for keyword in keywords) and client.user.mentioned_in(message):
        current_time = int(time.time())
        user_id = message.author.id
        order_id = f'{user_id}-{message.id}-{current_time}'
        user_roles = [role.id for role in message.author.roles]
        creation_time = int(message.author.created_at.timestamp())
        display_name = message.author.display_name
        # Send a request to the REST order service
        # Data in custom_data is additionally accessible from CPEE instance when it receives the order
        custom_dict = {'user_roles': user_roles,
                       'display_name': display_name, 'creation_time': creation_time}
        custom_json = json.dumps(custom_dict)
        payload = {'message': message_content, 'user_id': user_id,
                   'timestamp': current_time, 'order_id': order_id, 'custom_data': custom_json}
        r = requests.post(url=rest_order_url, data=payload)
        await message.reply(r.text)


# Run bot

client.run(token)
