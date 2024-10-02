from mysql.connector import connect
from models.discordTwitchSubscription import DiscordTwitchSubscription
import os

class DatabaseManager:

    def __init__(self):
        self.connection = connect(
        host="localhost",
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        database=os.getenv("DB_TABLE"))

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

    def addActiveSubscription(self, subId, streamerId, subSecret):
        self.maybeReconnect()
        query = "INSERT INTO activeSub (subscriptionId, streamerId, subSecret) VALUES (\"%s\", %i, \"%s\")" % (subId, int(streamerId), subSecret)
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            self.connection.commit()

    def editActiveSubscription(self, subId, streamerId, subSecret):
        self.maybeReconnect()
        query = "UPDATE activeSub SET subscriptionId = \"%s\", subSecret = \"%s\" WHERE streamerId = \"%s\"" % (str(subId), str(subSecret), str(streamerId))
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            self.connection.commit()
            
    def getActiveSubscription(self, subId):
        self.maybeReconnect()
        query = "SELECT subscriptionId, streamerId, subSecret FROM activeSub WHERE subscriptionId = %s" % str(subId)
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()
            print(result)
            if result:
                return result
            return None
    
    def findActiveSubscription(self, streamerId):
        self.maybeReconnect()
        query = "SELECT subscriptionId, streamerId, subSecret FROM activeSub WHERE streamerId = %s" % str(streamerId)
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()
            if result:
                return result
            return None
    
    def getAllActiveSubscriptions(self):
        self.maybeReconnect()
        query = "SELECT DISTINCT streamerId FROM activeSub"
        toReturn = []
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            for sub in cursor.fetchall():
                toReturn.append(sub)
            return toReturn
    
    def clearActiveSubscriptions(self):
        self.maybeReconnect()
        query = "TRUNCATE TABLE activeSub"
        with self.connection.cursor() as cursor:
            cursor.execute(query)

    def getLastStreamId(self, streamerId):
        self.maybeReconnect()
        query = "SELECT streamId FROM lastLive WHERE streamerId = %s" % str(streamerId)
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()
            if result:
                return result[0]
            return None

    def setLastStreamId(self, streamerId, streamId):
        self.maybeReconnect()
        query = "UPDATE lastLive SET streamId = %s WHERE streamerId = %s" % (str(streamId), str(streamerId))
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            self.connection.commit()

    def addLastStreamId(self, streamerId, streamId):
        self.maybeReconnect()
        query = "INSERT INTO lastLive (streamerId, streamId) VALUES (%s, %s)" % (str(streamerId), str(streamId))
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            self.connection.commit()

    def activeStreamerSubExists(self, streamerId):
        self.maybeReconnect()
        query = "SELECT COUNT(1) FROM activeSub WHERE streamerId = %s" % str(streamerId)
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()
            return result[0]

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
    
    def setPingMessage(self, guildId, streamerId, message):
        self.maybeReconnect()
        query = "UPDATE discordTwitchSubscriptions SET message = %s WHERE guildId = %s AND streamerId = %s" % (guildId, streamerId)
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            self.connection.commit()

    def addGlobalMod(self, userId):
        self.maybeReconnect()
        query = "INSERT INTO globalMods (userId) VALUES (%s)" % str(userId)
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            self.connection.commit()
