"""
Drop table lastLive
"""

from yoyo import step

__depends__ = {'20210107_01_k2ao6'}

steps = [
    step("DROP TABLE lastLive;")
]
