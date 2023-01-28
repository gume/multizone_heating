"""Constants for multizone_keating."""
# Base component constants
NAME = " Multizone for heating"
DOMAIN = "multizone_heating"
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "0.0.1"
ATTRIBUTION = "Data provided by ..."
ISSUE_URL = "https://github.com/.../issues"
MANUFACTURER = "Gume"

# Icons
ICON = "mdi:format-quote-close"

# Device classes
BINARY_SENSOR_DEVICE_CLASS = "connectivity"
SWITCH = "switch"

# Configuration and options
CONF_ZONES = "zones"
CONF_SUBZONES = "subzones"
CONF_SENSOR = "sensor"
CONF_SWITCH = "switch"
CONF_TRVS = "trvs"
CONF_TARGET_TEMP = "target_temp"
CONF_AWAY_TEMP = "away_temp"
CONF_VACATION_TEMP = "vacation_temp"
CONF_NIGHT_TEMP = "night_temp"
CONF_CONTROL = "control"
CONF_KEEP_ALIVE = "keep_alive"
CONF_KEEP_ACTIVE = "keep_active"
CONF_PUMPS = "pumps"

# Defaults
DEFAULT_NAME = DOMAIN


STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{NAME}
Version: {VERSION}
This is a custom integration!
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""
