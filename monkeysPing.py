import twitch
import discord
import time
import asyncio
import string

# read in IDs
cfg = open("pingConfig.txt", "r")
guildId = int(cfg.readline())
roleId = int(cfg.readline())
channelId = int(cfg.readline())
cfg.close()



client = discord.Client()
helix_api = twitch.Helix('62cznd1um7tlasc70jv2nnxjcjuchi', 'kjakm3beprsnb5kgec38ngmr0wyxdk')

guild = None
role = None
channel = None

toPing = True

async def makeRole():
    global role
    role = await guild.create_role(name="Goobers", mentionable=True)
    roleId = role.id
    cfg = open("pingConfig.txt", "w")
    cfg.write("%i\n" % guildId)
    cfg.write("%i\n" % roleId)
    cfg.write("%i\n" % channelId)
    cfg.close()

def isLive():
    user = helix_api.user('monkeys_forever')
    return user.is_live   

@client.event
async def on_ready():
    global guild, role, channel
    guild = client.get_guild(guildId)
    role = guild.get_role(roleId)
    channel = client.get_channel(channelId)
    if (role == None):
        await makeRole()

@client.event
async def on_message(message):
    if message.content == '!pingme':
        await message.author.add_roles(role)
    elif message.content == '!pingmenot':
        await message.author.remove_roles(role)

async def sendPings():
    message = "https://twitch.tv/monkeys_forever - Stream is now live! "
    message += role.mention
    await channel.send(message)

async def checkLiveAndPing():
    global toPing
    while(True):
        await asyncio.sleep(30)
        if (isLive()):
            if (toPing):
                await sendPings()
                toPing = False
        else:
            toPing = True
        

client.loop.create_task(checkLiveAndPing())
client.run('Nzk0NzQzODM4MzQxNzI2MjM5.X-_Q4A.MWXjRMNrtq9MjF0FoAb0Wpgf2e0')

