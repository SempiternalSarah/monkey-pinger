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
        query = "SELECT guildId, channelId, roleId, message FROM discordTwitchSubscriptions WHERE streamerId = " + str(streamerId)
        toReturn = []
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            for sub in cursor.fetchall():
                toReturn.append(DiscordTwitchSubscription(streamerId, sub[0], sub[1], sub[2], sub[3]))
            self.connection.commit()
        return toReturn

    def addStreamerSub(self, sub):
        query = "INSERT INTO discordTwitchSubscriptions (streamerId, guildId, channelId, roleId, message) VALUES (%i, %i, %i, %i, \"%s\")" % (sub.streamerId, sub.guildId, sub.channelId, sub.roleId, sub.message)
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            self.connection.commit()

    def getAllStreamers(self):
        query = "SELECT DISTINCT streamerId FROM discordTwitchSubscriptions"
        toReturn = []
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            for streamer in cursor.fetchall():
                toReturn.append(streamer[0])
            self.connection.commit()
        return toReturn

    def findSubscription(self, streamerId, guildId):
        query = "SELECT channelId, roleId FROM discordTwitchSubscriptions WHERE streamerId = %s AND guildId = %s" % (streamerId, guildId)
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchall()
            if result:
                return result[0]
            return None

    def streamerExists(self, streamerId):
        query = "SELECT COUNT(1) FROM discordTwitchSubscriptions WHERE streamerId = %s" % str(streamerId)
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()
            return result[0]

    def getLastStreamId(self, streamerId):
        query = "SELECT streamId FROM lastLive WHERE streamerId = %s" % str(streamerId)
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()
            if result:
                return result[0]
            return None

    def setLastStreamId(self, streamerId, streamId):
        query = "UPDATE lastLive SET streamId = %s WHERE streamerId = %s" % (str(streamId), str(streamerId))
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            self.connection.commit()

    def addLastStreamId(self, streamerId, streamId):
        query = "INSERT INTO lastLive (streamerId, streamId) VALUES (%s, %s)" % (str(streamerId), str(streamId))
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            self.connection.commit()
    
    def delSubscription(self, streamerId, guildId):
        query = "DELETE FROM discordTwitchSubscriptions WHERE streamerId = %s AND guildId = %s" % (streamerId, guildId)
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            self.connection.commit()

    def delAllSubscriptions(self, guildId):
        query = "DELETE FROM discordTwitchSubscriptions WHERE guildId = %s" % (guildId)
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            self.connection.commit()

    def getAllSubscriptions(self, guildId):
        query = "SELECT streamerId FROM discordTwitchSubscriptions WHERE guildId = %s" % (guildId)
        toReturn = []
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            for streamer in cursor.fetchall():
                toReturn.append(streamer)
            return toReturn
