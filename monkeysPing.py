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
import urllib.parse as urlp

import string
import random

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

# load global moderators
globalMods = db.getGlobalMods()

# webserver class that will receive and handle http requests
class listener(tornado.web.RequestHandler):
    # post requests - notifications received or subscription confirmations
    async def post(self):
        # subscription confirmation
        if (self.request.headers.get('Twitch-Eventsub-Message-Type') == 'webhook_callback_verification'):
            # convert body to dictionary
            body = tornado.escape.json_decode(self.request.body)
            for pd, secret in pendingSubs:
                if (pd['id'] != body['subscription']['id'] or pd['condition']['broadcaster_user_id'] != body['subscription']['condition']['broadcaster_user_id']):
                    continue
                # found the matching subscription
                # check signature
                sig = self.request.headers.get('Twitch-Eventsub-Message-Signature')
                hmcMsg = self.request.headers.get('Twitch-Eventsub-Message-Id').encode('utf-8') + self.request.headers.get('Twitch-Eventsub-Message-Timestamp').encode('utf-8') + self.request.body
                if (sig):
                    expectedSig = hmac.new(secret.encode('utf-8'), msg=hmcMsg, digestmod=hashlib.sha256).hexdigest()
                    print(sig, expectedSig)
                    if ("sha256=" + expectedSig != sig):
                        logging.info("incorrect notification signature!")
                        return
                else:
                    logging.info("notification unsigned!")
                    return
                # respond to the request
                self.write(body['challenge'])
                pendingSubs.remove((pd, secret))
            return

        elif(self.request.headers.get('Twitch-Eventsub-Message-Type') == 'notification'):
            # convert body to dictionary
            body = tornado.escape.json_decode(self.request.body)
            if (body['type'] = ['stream.online'])
            userId = body['condition']['broadcaster_user_id'])
            # send pings
            await sendPings(db.getStreamerSubs(userId))
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

# streamer name
streamer = os.getenv("STREAMER")

# twitch dev details
twitchId = os.getenv("TWITCH_ID")
twitchSecret = os.getenv("TWITCH_SECRET")

# port
port = os.getenv("TTV_PORT")

# default live message
defaultMessage = os.getenv("DEFAULT_LIVE_MESSAGE")

# variable for web server
app = tornado.web.Application([(r"/", listener)])

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
    global twitchToken, ip
    # URL to check token
    if (twitchToken != None):
        valurl = "https://id.twitch.tv/oauth2/validate"
        header = {"Client-ID": twitchId, 'Authorization' : 'Bearer ' + twitchToken}
        req = requests.get(valurl, headers=header).json()
        expiry = 0
        if ('expires_in' in req):
            expiry = req['expires_in']
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

    for streamer in streamers:
        # register for stream notifications with twitch webhook
        # these ones do not expire (check every day just in case?)
        letters = string.ascii_lowercase + string.ascii_uppercase + string.digits
        subSecret = ''
        for i in range(20):
            subSecret += random.choice(letters)

        webhookurl = "https://api.twitch.tv/helix/eventsub/subscriptions"
        payload = {
            "type": "stream.online",
            "version": "1",
            "condition": {
                "broadcaster_user_id": streamer
            },
            "transport": {
                "method": "webhook",
                "callback": "https://ahsarah.com:443",
                "secret": subSecret,
            }
        }

        header = {"Content-Type":"application/json", "Client-ID": twitchId, 'Authorization' : 'Bearer ' + twitchToken}

        # send notification registration request
        req = requests.post(webhookurl, headers=header, json = payload)


        # save request pending confirmation from Twitch
        if(req.ok):
            pendingSubs.append((req.json()['data'][0], subSecret))

# returns privilege level of user
def getPrivilege(user, channel):
    if str(user.id) in globalMods:
        return 9
    if(user.permissions_in(channel).manage_guild):
        return 8
    return 0
    

# called once discord client is connected
@client.event
async def on_ready():
    global app
    logging.info("Discord client connected")
    # set discord bot status
    game = discord.Game("!pingme {streamername} \n !pingmenot {streamername}")
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
    # show streamers available on the server
    if message.content.startswith("!streamers"):
        streamers = db.getAllSubscriptions(message.guild.id)
        print(streamers)
        if len(streamers) == 0:
            await message.channel.send("No stream notifications found on this server")
            return
        toSend = "This server has notifications available for %i streamer%s: ```\n" % (len(streamers), '' if len(streamers) == 1 else 's')
        users = helix_api.users([int(streamer[0]) for streamer in streamers])
        userNames = [user.display_name for user in users]
        userNames.sort(key=str.casefold)
        for user in userNames:
            toSend += "\t - %s\n" % user
        toSend += "```"
        await message.channel.send(toSend)
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
        
    # ---------
    # ---------

    # commands below require privileges

    # ---------
    # ---------
    
    # add streamer notifications to the current channel+guild
    elif message.content.startswith("!addnotifs"):
        if(getPrivilege(message.author, message.channel) < 5):
            return
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
            newRole = None
            # find role by id
            if (fields[2].isdigit()):
                newRole = discord.utils.get(message.guild.roles, id=int(fields[2]))
            # not valid id - find by name
            if not newRole:
                name = ""
                for x in range(2, len(fields)):
                    name += fields[x]
                    name += " "
                newRole = discord.utils.get(message.guild.roles, name=name)
            # not valid name - make new role with matching name
            if not newRole:
                newRole = await message.guild.create_role(name=name, mentionable=True)
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

    # remove streamer notifications from the guild
    elif message.content.startswith("!removenotifs"):
        if(getPrivilege(message.author, message.channel) < 5):
            return
        fields = message.content.split()
        if (len(fields) == 1):
            await message.channel.send("Command !removenotifs requires a streamer as an argument")
            return
        user = helix_api.user(fields[1])
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
            role = discord.utils.get(message.guild.roles, id=int(currentSub[1]))
            await role.delete()
        db.delSubscription(user.id, message.guild.id)
        await message.add_reaction("👍")

    # get ALL twitch streamers for which this instance of the bot gets notifications
    elif message.content.startswith("!subs"):
        if(getPrivilege(message.author, message.channel) < 9):
            return
        url = "https://api.twitch.tv/helix/eventsub/subscriptions"
        header = {"Client-ID": twitchId, 'Authorization' : 'Bearer ' + twitchToken}
        subs = requests.get(url, headers=header).json()['data']
        userIds = []
        # parse each subscription and add twitch user ID to the list
        for sub in subs:
            print(sub)
            # check that this is a streamer subscription
            if (sub['type'] == 'stream.online'):
                # parse topic for the user ID
                uid = sub['condition']['broadcaster_user_id']
                if (sub['status'] == "enabled"):
                    userIds.append(int(uid))
        # get user objects from IDs
        users = helix_api.users(userIds)
        userNames = [user.display_name for user in users]
        userNames.sort(key=str.casefold)
        # build message including names of all streamers
        toSend = "Bot currently gets notifications for %i streamer%s: ```\n" % (len(userNames), '' if len(userNames) == 1 else 's')
        for name in userNames:
            toSend += "\t - %s\n" % name
        toSend += "```"
        await message.channel.send(toSend)


    elif message.content.startswith("!clearsubs"):
        if(getPrivilege(message.author, message.channel) < 9):
            return
        url = "https://api.twitch.tv/helix/eventsub/subscriptions"
        header = {"Client-ID": twitchId, 'Authorization' : 'Bearer ' + twitchToken}
        subs = requests.get(url, headers=header).json()['data']
        await clearSubs(subs)

    # add global moderator
    elif message.content.startswith("!addmod"):
        if(getPrivilege(message.author, message.channel) < 9):
            return
        fields = message.content.split()
        user = client.get_user(int(fields[1]))
        if (not user):
            await message.channel.send("User not found")
            return
        if (fields[1] in globalMods):
            await message.channel.send("%s is already a global moderator" % user.name)
            return
        globalMods.append(fields[1])
        db.addGlobalMod(fields[1])
        await message.add_reaction("👍")
        

# removes all subscriptions
async def clearSubs(subs):
    webhookurl = "https://api.twitch.tv/helix/eventsub/subscriptions"
    for sub in subs:
        finalUrl = webhookurl + "?id=" + sub['id']
        # build headers and send request
        header = {"Client-ID": twitchId, 'Authorization' : 'Bearer ' + twitchToken}
        temp = requests.delete(finalUrl, headers=header)
        if (not temp.ok):
            print(sub['id'])
            print(temp.json())
        



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
        mention = ''
        if (role):
            mention = role.mention
        message = message.replace("$role", mention)
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

# start listening to twitch API
app.listen(int(port), xheaders=True)

# hand control over to the client
client.run(os.getenv("DISCORD_TOKEN"))

