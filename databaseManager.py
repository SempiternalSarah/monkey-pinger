from mysql.connector import connect
from models.discordTwitchSubscription import DiscordTwitchSubscription
import os

class DatabaseManager:

    def __init__(self):
        self.connection = connect(
        host="localhost",
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        database="discordtwitchbot")

    def getStreamerSubs(self, streamerId):
        query = "SELECT channelId, guildId, roleId, message FROM discordTwitchSubscriptions WHERE streamerId = " + str(streamerId)
        toReturn = []
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            for sub in cursor.fetchall():
                toReturn.append(DiscordTwitchSubscription(streamerId, sub[0], sub[1], sub[2], sub[3]))
            self.connection.commit()
        return toReturn

    def addStreamerSub(self, sub):
        query = "INSERT INTO discordTwitchSubscriptions (streamerId, guildId, channelId, roleId, message) VALUES (%i, %i, %i, %i, \"%s\")" % (sub.streamerId, sub.guildId, sub.channelId, sub.roleId, sub.message)
        print(query)
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            self.connection.commit()
