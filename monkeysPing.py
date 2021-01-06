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
import hmac
import hashlib

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

# webserver class that will receive and handle http requests
class listener(tornado.web.RequestHandler):
    # post requests - notifications received
    async def post(self):
        # check signature
        sig = self.request.headers.get('X-Hub-Signature')
        if (sig):
            expectedSig = hmac.new(twitchSecret.encode('utf-8'), msg=self.request.body, digestmod=hashlib.sha256).hexdigest()
            if ("sha256=" + expectedSig != sig):
                logging.info("incorrect notification signature!")
                return
        else:
            logging.info("notification unsigned!")
            return

        # convert body to dictionary
        body = tornado.escape.json_decode(self.request.body)
        # check if live notification
        if (body and body['data'] and body['data'][0]['type'] == "live"):
            logging.info("live notification")
            userId = body['data'][0]['user_id']
            streamId = body['data'][0]['id']
            # check if already seen this stream id
            # indicates title change, etc
            lastStream = db.getLastStreamId(userId)
            if (lastStream == str(streamId)):
                logging.info("stream update for streamer %s - not new live" % userId)
                return
            # mark this as last stream seen live
            if (lastStream == None):
                db.addLastStreamId(userId, streamId)
            else:
                db.setLastStreamId(userId, streamId)
            # send pings
            await sendPings(db.getStreamerSubs(userId))

    # get requests - should only see when registering
    def get(self):
        # check that we requested this
        topic = self.get_argument('hub.topic')
        if (not topic or topic not in pendingSubs):
            return
        # indicate we have received confirmation for this topic
        pendingSubs.remove(topic)
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

# variable for web server
app = None

# init discord client and twitch connection
client = discord.Client()
helix_api = twitch.Helix(twitchId, twitchSecret)

# store twitch token once obtained
# expires periodically - will be updated in background
twitchToken = None

# store pending twitch webhook subscriptions
pendingSubs = []

# checks token with twitch, renews if necessary
# then registers for notifications for each streamer
def authAndRegisterTwitch(streamers):
    # exit if list empty
    if(len(streamers) == 0):
        return
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
            "hub.lease_seconds": 90000,
            "hub.secret": twitchSecret
        }
        header = {"Content-Type":"application/json", "Client-ID": twitchId, 'Authorization' : 'Bearer ' + twitchToken}
        # mark we are waiting for confirmation
        pendingSubs.append(payload['hub.topic'])

        # send notification registration request
        req = requests.post(webhookurl, headers=header, json = payload)

# called once discord client is connected
@client.event
async def on_ready():
    global app
    logging.info("Discord client connected")
    # start listening to twitch API
    app = tornado.web.Application([(r"/", listener)])
    app.listen(int(port))
    # set discord bot status
    game = discord.Game("!pingme monkeys_forever \n !pingmenot monkeys_forever")
    await client.change_presence(activity=game, status=discord.Status.online)

# called when bot is removed from guild
@client.event
async def on_guild_remove(guild):
    # remove subscriptions for that guild from the database
    # no need to manually remove twitch subscriptions - will expire within a day
    db.delAllSubscriptions(guild.id)

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
        await message.add_reaction("👍")
    # commands below require admin privileges
    if str(message.author.id) != admin:
        return
    # add streamer subscription to the current channel+guild
    elif message.content.startswith("!addnotifs"):
        fields = message.content.split()
        user = helix_api.user(fields[1])
        if (len(fields) == 1):
            await message.channel.send("Command !addnotifs requires a streamer as an argument")
            return
        # no user found matching id/name
        if (not user):
            await message.channel.send("Twitch streamer `%s` not found" % fields[1])
            return

        # check to see if subscription to this streamer already exists in this guild
        # if so, don't create a new one
        currentSub = db.findSubscription(user.id, message.guild.id)
        if (currentSub):
            channel = client.get_channel(int(currentSub[0]))
            await message.channel.send("Notifications for streamer `%s` already exist in channel %s" % (user.display_name, channel.mention))
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
        await message.channel.send("Notifications for streamer `%s` added in channel %s for role `%s`" % (user.display_name, message.channel.mention, newRole.name))

    elif message.content.startswith("!removenotifs"):
        fields = message.content.split()
        user = helix_api.user(fields[1])
        if (len(fields) == 1):
            await message.channel.send("Command !removenotifs requires a streamer as an argument")
            return
        # no user found matching id/name
        if (not user):
            await message.channel.send("Twitch streamer `%s` not found" % fields[1])
            return
        # fetch subscription
        currentSub = db.findSubscription(user.id, message.guild.id)
        if (not currentSub):
            await message.channel.send("No notifications for streamer `%s` found" % user.display_name)
            return
        # delete role?
        toDelete = False
        if len(fields) > 2:
            toDelete = fields[2].lower() == "-d"
        if (toDelete):
            print(currentSub)
            role = discord.utils.get(message.guild.roles, id=int(currentSub[1]))
            await role.delete()
        db.delSubscription(user.id, message.guild.id)
        await message.add_reaction("👍")

        

    elif message.content.startswith("!subs"):
        url = "https://api.twitch.tv/helix/webhooks/subscriptions"
        header = {"Client-ID": twitchId, 'Authorization' : 'Bearer ' + twitchToken}
        req = requests.get(url, headers=header)
        print(req.json())

    elif message.content.startswith("!clearsubs"):
        url = "https://api.twitch.tv/helix/webhooks/subscriptions"
        header = {"Client-ID": twitchId, 'Authorization' : 'Bearer ' + twitchToken}
        subs = requests.get(url, headers=header).json()['data']
        await clearSubs(subs)

# removes all subscriptions
async def clearSubs(subs):
    webhookurl = "https://api.twitch.tv/helix/webhooks/hub"
    for sub in subs:
        # only clear subs from THIS server (port number)
        if (":"+port not in sub['callback']):
            continue
        # register for stream notifications with twitch webhook
        # lease set for 25 hours - will renew every 24
        payload = {"hub.mode":"unsubscribe",
            "hub.topic": sub['topic'],
            "hub.callback": sub['callback'],
            "hub.lease_seconds": 0,
            "hub.secret": twitchSecret
        }
        # mark we are waiting for confirmation
        pendingSubs.append(payload['hub.topic'])
        # build headers and send request
        header = {"Content-Type":"application/json", "Client-ID": twitchId, 'Authorization' : 'Bearer ' + twitchToken}
        requests.post(webhookurl, headers=header, json=payload)



# sends ping message to each sub group
async def sendPings(subs: list):
    # exit if list empty
    if(len(subs) == 0):
        return
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

