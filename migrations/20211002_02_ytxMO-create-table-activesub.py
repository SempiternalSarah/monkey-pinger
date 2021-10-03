"""
Create table activeSub
"""

from yoyo import step

__depends__ = {'20210107_01_k2ao6'}

steps = [
    step("CREATE TABLE activeSub (subscriptionId VARCHAR(50), streamerId VARCHAR(50), subSecret VARCHAR(50), PRIMARY KEY (subscriptionId));")
]
