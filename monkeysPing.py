import twitch
import discord
import asyncio
import dotenv
import os
import tornado.web
import tornado
import requests
import logging

# setup logging
logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level = logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S'
)


# notification ID last received - to ignore duplicates
lastNotification = 0

# webserver class that will receive and handle http requests
class listener(tornado.web.RequestHandler):
    # post requests - notifications received
    async def post(self):
        global lastNotification
        thisId = self.request.headers.get("Twitch-Notification-Id")
        # ignore duplicate ID
        if (thisId == lastNotification):
            logging.info("Duplicate: " + thisId)
            self.write("")
            return
        lastNotification = thisId
        # convert body to dictionary
        body = tornado.escape.json_decode(self.request.body)
        logging.debug("notification received: " + lastNotification)
        logging.debug(body)
        # send response
        self.write("")
        # check if live notification
        if (body and body['data'] and body['data'][0]['type'] == "live"):
            logging.info("live notification")
            # send pings
            await sendPings()
            
    # get requests - should only see when registering
    def get(self):
        # extract challenge code to send in response
        confirm = self.get_argument('hub.challenge')
        logging.info("Successfully registered")
        self.write(confirm)

# start listening
app = tornado.web.Application([(r"/", listener)])
app.listen(8080)

# load environment file
dotenv.load_dotenv(override=True)

# load IDs from environment variables
guildId = int(os.getenv("GUILD_ID"))
roleId = int(os.getenv("ROLE_ID"))
channelId = int(os.getenv("CHANNEL_ID"))

streamer = os.getenv("STREAMER")

twitchId = os.getenv("TWITCH_ID")
twitchSecret = os.getenv("TWITCH_SECRET")

# init discord client and twitch connection
client = discord.Client()
helix_api = twitch.Helix(twitchId, twitchSecret)

# global variables
guild = None
role = None
channel = None

# authenticates with twitch and registers for notifications
def authAndRegisterTwitch():

    # build URL to receive token
    authurl = "https://id.twitch.tv/oauth2/token?client_id=" + twitchId + "&client_secret=" + twitchSecret + "&grant_type=client_credentials"
    
    # extract response
    req = requests.post(authurl)
    resp = req.json()

    # get user info from name
    user = helix_api.user(streamer)

    # load external IP (to use as callback for twitch webhook)
    ip = requests.get('https://api.ipify.org').text

    # register for stream notifications with twitch webhook
    # lease set for 25 hours - will renew every 24
    webhookurl = "https://api.twitch.tv/helix/webhooks/hub"
    payload = {"hub.mode":"subscribe",
        "hub.topic":"https://api.twitch.tv/helix/streams?user_id=" + user.id,
        "hub.callback": "http://" + ip + ":8080",
        "hub.lease_seconds": 90000
    }
    header = {"Content-Type":"application/json", "Client-ID": twitchId, 'Authorization' : 'Bearer ' + resp['access_token']}

    req = requests.post(webhookurl, headers=header, json = payload)

# creates the Goobers role (to be pinged)
# only called if the role ID in the config file doesn't exist
async def makeRole():
    global role
    role = await guild.create_role(name=os.getenv("ROLE_NAME"), mentionable=True)
    roleId = role.id
    logging.info("CREATED ROLE: " + str(roleId))

# returns boolean indicating live status
def isLive():
    user = helix_api.user(streamer)
    return user.is_live   

# called once discord client is connected
@client.event
async def on_ready():
    logging.info("Discord client connected")
    global guild, role, channel
    game = discord.Game("!pingme to be added, !pingmenot to be removed")
    await client.change_presence(activity=game, status=discord.Status.online)
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
        logging.info("Adding role to user " + str(message.author.id))
        await message.author.add_roles(role)
    elif message.content == '!pingmenot':
        logging.info("Removing role from user " + str(message.author.id))
        await message.author.remove_roles(role)

# sends ping message
async def sendPings():
    message = "https://twitch.tv/" + streamer + " - Stream is now live! "
    message += role.mention
    await channel.send(message)

# job added to the discord client's event loop
# registers for twitch webhook notifications every 24 hours
async def registerDaily():
    while(True):
        logging.info("Registering...")
        authAndRegisterTwitch()
        # sleep for 24 hours before registering again
        await asyncio.sleep(86400)
        
# add daily registration task to client
client.loop.create_task(registerDaily())

# client.loop.create_task(app.run())
# hand control over to the client
client.run(os.getenv("DISCORD_TOKEN"))

