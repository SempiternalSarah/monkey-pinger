"""
Create table activeSub
"""

from yoyo import step

__depends__ = {'20211002_01_lE3wy-drop-table-lastlive'}

steps = [
    step("CREATE TABLE activeSub (subscriptionId VARCHAR(50), streamerId VARCHAR(50), subSecret VARCHAR(50), PRIMARY KEY (subscriptionId));")
]
