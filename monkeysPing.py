import dotenv
import twitch
import discord
import asyncio
import os
import tornado.web
import tornado
import requests
import logging
import databaseManager
import models.discordTwitchSubscription

# load environment file
dotenv.load_dotenv(override=True)

# setup logging
logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level = logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S'
)

# connect to database

db = databaseManager.DatabaseManager()

# notification ID last received - to ignore duplicates
lastNotification = 0

# last stream live for each streamer - ignore title change events
lastLive = {}

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
            userId = body['data'][0]['user_id']
            # check if already seen this stream id
            # indicates title change, etc
            if (lastLive[userId] == body['data'][0]['id']):
                logging.info("stream update - not new live")
                return
            # mark this as last stream seen live
            lastLive[userId] = body['data'][0]['id']
            # send pings
            await sendPings(db.getStreamerSubs(userId))

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

# store twitch token once obtained
# expires periodically - will be updated in background
twitchToken = None

# checks token with twitch, renews if necessary
# then registers for notifications for each streamer
def authAndRegisterTwitch(streamers):
    global twitchToken
    # URL to check token
    if (twitchToken != None):
        valurl = "https://id.twitch.tv/oauth2/validate"
        header = {"Client-ID": twitchId, 'Authorization' : 'Bearer ' + twitchToken}
        req = requests.get(valurl, headers=header)
        expiry = req.json()['expires_in']
        # mark for renewal if expiry less than an hour away
        if (expiry < 3600):
            twitchToken = None
    # renew token
    if (twitchToken == None):
        # build URL to receive token
        authurl = "https://id.twitch.tv/oauth2/token?client_id=" + twitchId + "&client_secret=" + twitchSecret + "&grant_type=client_credentials"
        
        # extract response
        req = requests.post(authurl)
        twitchToken = req.json()['access_token']

    # load external IP (to use as callback for twitch webhook)
    ip = requests.get('https://api.ipify.org').text

    for streamer in streamers:
        # register for stream notifications with twitch webhook
        # lease set for 25 hours - will renew every 24
        webhookurl = "https://api.twitch.tv/helix/webhooks/hub"
        payload = {"hub.mode":"subscribe",
            "hub.topic":"https://api.twitch.tv/helix/streams?user_id=" + streamer,
            "hub.callback": "http://" + ip + ":" + port,
            "hub.lease_seconds": 90000
        }
        header = {"Content-Type":"application/json", "Client-ID": twitchId, 'Authorization' : 'Bearer ' + twitchToken}

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
    # add/remove role from user for a streamer's pings
    if message.content.startswith('!pingme'):
        fields = message.content.split()
        if (fields[0] != '!pingme' and fields[0] != '!pingmenot'):
            return
        if (len(fields) == 1):
            await message.channel.send("Command `%s` requires a streamer as an argument" % fields[0])
            return
        user = helix_api.user(fields[1])
        # no user found matching id/name
        if (not user):
            await message.channel.send("Twitch streamer `%s` not found" % fields[1])
            return
        currentSub = db.findSubscription(user.id, message.guild.id)
        if (not currentSub):
            await message.channel.send("Twitch streamer `%s` notifications not added to this server" % user.display_name)
            return
        roleId = int(currentSub[1])
        role = discord.utils.get(message.guild.roles, id=roleId)
        if message.content.startswith('!pingmenot'):
            logging.info("Removing role %s from user %s" %(role.name, message.author.name))
            await message.author.remove_roles(role)
        else:
            logging.info("Adding role %s to user %s" %(role.name, message.author.name))
            await message.author.add_roles(role)
    # commands below require admin privileges
    if message.author.id != admin:
        return
    # add streamer subscription to the current channel+guild
    elif message.content.startswith("!subscribe"):
        fields = message.content.split()
        user = helix_api.user(fields[1])
        if (len(fields) == 1):
            await message.channel.send("Command !subscribe requires a streamer as an argument")
            return
        # no user found matching id/name
        if (not user):
            await message.channel.send("Twitch streamer %s not found" % fields[1])
            return

        # check to see if subscription to this streamer already exists in this guild
        # if so, don't create a new one
        currentSub = db.findSubscription(user.id, message.guild.id)
        if (currentSub):
            channel = client.get_channel(int(currentSub[0]))
            await message.channel.send("Subscription to streamer `%s` already exists in channel %s" % (user.display_name, channel.mention))
            return
        # 3rd argument is role name/id
        if len(fields) >= 3:
            # find role by id
            newRole = discord.utils.get(message.guild.roles, id=fields[2])
            # not valid id - find by name
            if not newRole:
                newRole = discord.utils.get(message.guild.roles, name=fields[2])
            # not valid name - make new role with matching name
            if not newRole:
                newRole = await message.guild.create_role(name=fields[2], mentionable=True)
        # no role passed - create new role with default name
        else:   
            newRole = await message.guild.create_role(name=user.display_name+" pings", mentionable=True)

        # check to see if this is a subscription to a new streamer
        if (not db.streamerExists(user.id)):
            # register for notifications for this streamer
            authAndRegisterTwitch([user.id])
        # add subscription to database
        db.addStreamerSub(models.discordTwitchSubscription.DiscordTwitchSubscription(user.id, message.guild.id, message.channel.id, newRole.id, defaultMessage))
    elif message.content.startswith("!subs"):
        url = "https://api.twitch.tv/helix/webhooks/subscriptions"
        header = {"Client-ID": twitchId, 'Authorization' : 'Bearer ' + twitchToken}
        req = requests.get(url, headers=header)
        print(req.json())



# sends ping message to each sub group
async def sendPings(subs: list):
    # all will be about the same streamer
    streamer = helix_api.user(subs[0].streamerId)
    for sub in subs:
        # extract subscription information
        guild = client.get_guild(sub.guildId)
        role = guild.get_role(sub.roleId)
        channel = client.get_channel(sub.channelId)
        # build message text from possible placeholders
        message = sub.message.replace("$link", "https://twitch.tv/" + streamer.display_name)
        message = message.replace("$role", role.mention)
        await channel.send(message)

# job added to the discord client's event loop
# registers for twitch webhook notifications every 24 hours
async def registerDaily():
    while(True):
        logging.info("Registering...")
        authAndRegisterTwitch(db.getAllStreamers())
        # sleep for 24 hours before registering again
        await asyncio.sleep(86400)
        
# add daily registration task to client
client.loop.create_task(registerDaily())

# hand control over to the client
client.run(os.getenv("DISCORD_TOKEN"))

