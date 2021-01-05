import dotenv
import twitch
import discord
import asyncio
import os
import tornado.web
import tornado
import requests
import logging
from databaseManager import DatabaseManager
from models.discordTwitchSubscription import DiscordTwitchSubscription

# load environment file
dotenv.load_dotenv(override=True)

# setup logging
logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level = logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S'
)

# connect to database

db = DatabaseManager()

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
            await sendPings(db.getStreamerSubs(body['data'][0]['id']))

    # get requests - should only see when registering
    def get(self):
        # extract challenge code to send in response
        confirm = self.get_argument('hub.challenge')
        logging.info("Successfully registered")
        self.write(confirm)

# streamer name
streamer = os.getenv("STREAMER")

# twitch dev details
twitchId = os.getenv("TWITCH_ID")
twitchSecret = os.getenv("TWITCH_SECRET")

# port
port = os.getenv("TTV_PORT")

# default live message
defaultMessage = os.getenv("DEFAULT_LIVE_MESSAGE")

# global admin discord ID
admin = os.getenv("GLOBAL_ADMIN_ID")

# start listening
app = tornado.web.Application([(r"/", listener)])
app.listen(int(port))

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
        "hub.callback": "http://" + ip + port,
        "hub.lease_seconds": 90000
    }
    header = {"Content-Type":"application/json", "Client-ID": twitchId, 'Authorization' : 'Bearer ' + resp['access_token']}

    # send notification registration request
    req = requests.post(webhookurl, headers=header, json = payload)

# called once discord client is connected
@client.event
async def on_ready():
    logging.info("Discord client connected")
    game = discord.Game("!pingme to be added, !pingmenot to be removed")
    await client.change_presence(activity=game, status=discord.Status.online)

# called every message - only reacts to the commands
@client.event
async def on_message(message):
    if message.content == '!pingme':
        logging.info("Adding role to user " + str(message.author.id))
        await message.author.add_roles(role)
    elif message.content == '!pingmenot':
        logging.info("Removing role from user " + str(message.author.id))
        await message.author.remove_roles(role)
    elif message.content.startswith("!subscribe"):
        logging.info("Adding subscription: " + message.content)
        fields = message.content.split()
        user = helix_api.user(fields[1])
        if (user):
            uid = user.id
        else:
            await message.channel.send("Twitch streamer %s not found" % fields[1])
            return

        if len(fields) >= 3:
            newRole = discord.utils.get(message.guild.roles, id=fields[2])
            if not newRole:
                newRole = discord.utils.get(message.guild.roles, name=fields[2])
            else:
                newRole = await message.guild.create_role(name=fields[2], mentionable=True)
        else:   
            newRole = await message.guild.create_role(name=user.display_name+" pings", mentionable=True)
        
        db.addStreamerSub(DiscordTwitchSubscription(user.id, message.guild.id, message.channel.id, newRole.id, defaultMessage))
        await message.author.add_roles(newRole)

# sends ping message to each sub group
async def sendPings(subs: list[DiscordTwitchSubscription]):
    # all will be about the same streamer
    streamer = helix_api.user(subs[0].streamerId)
    for sub in subs:
        guild = client.get_guild(sub.guildId)
        role = guild.get_role(sub.roleId)
        message = sub.message.replace("$link", "https://twitch.tv/" + streamer.display_name)
        message = message.replace("$role", role.mention)
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

