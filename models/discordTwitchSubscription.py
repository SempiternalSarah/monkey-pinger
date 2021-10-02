
class DiscordTwitchSubscription:
    def __init__(self, streamerId, guildId, channelId, roleId, message):
        self.streamerId = int(streamerId)
        self.guildId = int(guildId)
        self.channelId = int(channelId)
        self.roleId = int(roleId)
        self.message = message
