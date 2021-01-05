"""
Make discordTwitchSubscriptions table
"""

from yoyo import step

__depends__ = {}

steps = [
    step("CREATE TABLE discordTwitchSubscriptions (streamerId VARCHAR(50), guildId VARCHAR(50), channelId VARCHAR(50), roleId VARCHAR(50), message VARCHAR(50), PRIMARY KEY (streamerId, guildId));"),
]
