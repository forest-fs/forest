"""
Discord bot factory and runner used by :mod:`forest.main`.
"""

from forest.platforms.discord.bot import create_bot, run_bot

__all__ = ["create_bot", "run_bot"]
