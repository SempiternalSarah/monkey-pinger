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

    def maybeReconnect(self):
        if self.connection.is_connected():
            return
        self.connection.reconnect()

    def getStreamerSubs(self, streamerId):
        self.maybeReconnect()
        query = "SELECT guildId, channelId, roleId, message FROM discordTwitchSubscriptions WHERE streamerId = " + str(streamerId)
        toReturn = []
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            for sub in cursor.fetchall():
                toReturn.append(DiscordTwitchSubscription(streamerId, sub[0], sub[1], sub[2], sub[3]))
            self.connection.commit()
        return toReturn

    def addStreamerSub(self, sub):
        self.maybeReconnect()
        query = "INSERT INTO discordTwitchSubscriptions (streamerId, guildId, channelId, roleId, message) VALUES (%i, %i, %i, %i, \"%s\")" % (sub.streamerId, sub.guildId, sub.channelId, sub.roleId, sub.message)
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            self.connection.commit()

    def getAllStreamers(self):
        self.maybeReconnect()
        query = "SELECT DISTINCT streamerId FROM discordTwitchSubscriptions"
        toReturn = []
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            for streamer in cursor.fetchall():
                toReturn.append(streamer[0])
            self.connection.commit()
        return toReturn

    def findSubscription(self, streamerId, guildId):
        self.maybeReconnect()
        query = "SELECT channelId, roleId FROM discordTwitchSubscriptions WHERE streamerId = %s AND guildId = %s" % (streamerId, guildId)
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchall()
            if result:
                return result[0]
            return None
            
    def getActiveSubscription(self, subId):
        self.maybeReconnect()
        query = "SELECT subscriptionId, streamerId, subSecret FROM activeSub WHERE subscriptionId = %s" % str(subId)
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()
            if result:
                return result[0]
            return None
    
    def findActiveSubscription(self, streamerId):
        self.maybeReconnect()
        query = "SELECT subscriptionId, streamerId, subSecret FROM activeSub WHERE streamerId = %s" % str(streamerId)
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()
            if result:
                return result[0]
            return None

    def streamerExists(self, streamerId):
        self.maybeReconnect()
        query = "SELECT COUNT(1) FROM discordTwitchSubscriptions WHERE streamerId = %s" % str(streamerId)
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()
            return result[0]
    
    def delSubscription(self, streamerId, guildId):
        self.maybeReconnect()
        query = "DELETE FROM discordTwitchSubscriptions WHERE streamerId = %s AND guildId = %s" % (streamerId, guildId)
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            self.connection.commit()

    def delAllSubscriptions(self, guildId):
        self.maybeReconnect()
        query = "DELETE FROM discordTwitchSubscriptions WHERE guildId = %s" % (guildId)
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            self.connection.commit()

    def getAllSubscriptions(self, guildId):
        self.maybeReconnect()
        query = "SELECT streamerId FROM discordTwitchSubscriptions WHERE guildId = %s" % (guildId)
        toReturn = []
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            for streamer in cursor.fetchall():
                toReturn.append(streamer)
            return toReturn
    
    def getGlobalMods(self):
        self.maybeReconnect()
        query = "SELECT userId FROM globalMods"
        toReturn = []
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            for mod in cursor.fetchall():
                toReturn.append(mod[0])
            return toReturn

    def addGlobalMod(self, userId):
        self.maybeReconnect()
        query = "INSERT INTO globalMods (userId) VALUES (%s)" % str(userId)
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            self.connection.commit()
