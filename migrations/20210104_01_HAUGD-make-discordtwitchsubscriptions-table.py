"""
Make discordTwitchSubscriptions table
"""

from yoyo import step

__depends__ = {}

steps = [
    step("CREATE TABLE discordTwitchSubscriptions (streamerId TEXT, guildId TEXT, channelId TEXT, roleId TEXT, message TEXT, PRIMARY KEY (streamerId, guildId));"),
]
