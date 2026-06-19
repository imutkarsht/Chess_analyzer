"""
Helper utilities for the Load Game dialog panels.
"""
import os
from ....utils.path_utils import get_resource_path

def icon_path(filename: str) -> str:
    return get_resource_path(os.path.join("assets", "icons", filename))

def classify_time_control(tc: str) -> str:
    """Return Bullet/Blitz/Rapid/Classical/Correspondence from a TimeControl string."""
    if not tc or tc in ("-", "?", ""):
        return "Unknown"
    try:
        # Handle formats like "600", "600+5", "40/7200:1800+30"
        base = 0
        for period in tc.split(":"):
            base_part = period.split("+")[0]
            sec_part = base_part.split("/")[-1]
            try:
                base += int(sec_part)
            except ValueError:
                pass
                
        if base == 0:
            return tc
            
        if base < 180:   return "Bullet"
        if base < 600:   return "Blitz"
        if base < 1800:  return "Rapid"
        return "Classical"
    except Exception:
        return tc
