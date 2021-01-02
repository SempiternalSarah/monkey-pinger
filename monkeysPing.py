import twitch
import discord
import asyncio
import dotenv
import os

# load environment file
dotenv.load_dotenv(override=True)

# load IDs from environment variables
guildId = int(os.getenv("GUILD_ID"))
roleId = int(os.getenv("ROLE_ID"))
channelId = int(os.getenv("CHANNEL_ID"))

# init discord client and twitch connection
client = discord.Client()
helix_api = twitch.Helix(os.getenv("TWITCH_ID"), os.getenv("TWITCH_SECRET"))

# global variables
guild = None
role = None
channel = None

# to ping if stream live - false if already pinged
# set to true when bot sees that stream is offline
toPing = False

# creates the Goobers role (to be pinged)
# only called if the role ID in the config file doesn't exist
async def makeRole():
    global role
    role = await guild.create_role(name="Goobers", mentionable=True)
    roleId = role.id
    print(roleId)

# returns boolean indicating live status
def isLive():
    user = helix_api.user('monkeys_forever')
    return user.is_live   

# called once discord client is connected
@client.event
async def on_ready():
    global guild, role, channel
    # store guild, role, and channel information
    guild = client.get_guild(guildId)
    role = guild.get_role(roleId)
    channel = client.get_channel(channelId)
    # if role not found - create one
    if (role == None):
        await makeRole()

# called every message - only reacts to the commands
@client.event
async def on_message(message):
    if message.content == '!pingme':
        await message.author.add_roles(role)
    elif message.content == '!pingmenot':
        await message.author.remove_roles(role)

# sends ping message
async def sendPings():
    message = "https://twitch.tv/monkeys_forever - Stream is now live! "
    message += role.mention
    await channel.send(message)

# async task that checks if stream live every 30 seconds
# pings if appropriate
async def checkLiveAndPing():
    global toPing
    while(True):
        await asyncio.sleep(10)
        if (isLive()):
            if (toPing):
                await sendPings()
                toPing = False
        else:
            toPing = True
        
# add stream checking/pinging task to client
client.loop.create_task(checkLiveAndPing())
# hand control over to the client
client.run(os.getenv("DISCORD_TOKEN"))

