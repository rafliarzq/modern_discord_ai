import discord


def hex_color(value: str) -> discord.Color:
    """Convert a hex color such as '#5865F2' into discord.Color."""
    normalized = value.strip().removeprefix("#")
    if len(normalized) != 6:
        raise ValueError("Hex color must contain exactly 6 characters.")
    return discord.Color(int(normalized, 16))


class Colors:
    SUCCESS = hex_color("#57F287")
    ERROR = hex_color("#ED4245")
    WARNING = hex_color("#FEE75C")
    INFO = hex_color("#5865F2")
    NEUTRAL = hex_color("#99AAB5")
    BAN = hex_color("#ED4245")
    KICK = hex_color("#F47B67")
    TIMEOUT = hex_color("#FAA61A")
    MUTE = hex_color("#E67E22")
    UNMUTE = hex_color("#57F287")
    UNBAN = hex_color("#2ECC71")
    WARN = hex_color("#FEE75C")
    PURGE = hex_color("#5865F2")
    JOIN = hex_color("#57F287")
    LEAVE = hex_color("#ED4245")
    UPDATE = hex_color("#3498DB")
    LOG = hex_color("#95A5A6")
