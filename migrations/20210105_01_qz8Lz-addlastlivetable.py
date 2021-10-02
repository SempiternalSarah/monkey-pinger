"""
addLastLiveTable
"""

from yoyo import step

__depends__ = {'20210104_01_HAUGD-make-discordtwitchsubscriptions-table'}

steps = [
    step("CREATE TABLE lastLive (streamerId VARCHAR(50), streamId VARCHAR(50), PRIMARY KEY (streamerId));")
]
