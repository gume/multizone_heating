import asyncio
from datetime import timedelta
import logging
import voluptuous as vol


from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Config, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_NAME, CONF_UNIQUE_ID, CONF_ENTITY_ID
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.util import slugify

from homeassistant.helpers import device_registry as dr

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)


from .const import (
    DOMAIN,
    STARTUP_MESSAGE,
    CONF_ZONES, CONF_SUBZONES, CONF_PUMPS,
    CONF_SENSOR, CONF_SWITCH,
    CONF_TRVS, CONF_CONTROL,
    CONF_TARGET_TEMP, CONF_AWAY_TEMP, CONF_VACATION_TEMP, CONF_NIGHT_TEMP,
    CONF_KEEP_ALIVE, CONF_KEEP_ACTIVE,
    MANUFACTURER, NAME, VERSION
)

_LOGGER: logging.Logger = logging.getLogger(__package__)


CONFIG_TRVS = vol.Schema({
    vol.Required(CONF_SWITCH): cv.entity_id,
})

CONFIG_SUBZONE = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_UNIQUE_ID): cv.string,
    vol.Optional(CONF_SENSOR): cv.entity_id,
    vol.Optional(CONF_TRVS): vol.All([CONFIG_TRVS]),
    vol.Optional(CONF_TARGET_TEMP): vol.Coerce(float),
    vol.Optional(CONF_AWAY_TEMP): vol.Coerce(float),
    vol.Optional(CONF_VACATION_TEMP): vol.Coerce(float),
    vol.Optional(CONF_NIGHT_TEMP): vol.Coerce(float),
    vol.Optional(CONF_CONTROL): cv.entity_id,
})

CONFIG_TARGET_SWITCH = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_domain([SWITCH_DOMAIN]),
    vol.Optional(CONF_KEEP_ALIVE, default=None): vol.Any(None, cv.positive_time_period, cv.positive_timedelta),
    vol.Optional(CONF_KEEP_ACTIVE, default=None): vol.Any(None, cv.positive_time_period, cv.positive_timedelta),
})

CONFIG_ZONE = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_UNIQUE_ID): cv.string,
    vol.Optional(CONF_TARGET_TEMP): vol.Coerce(float),
    vol.Optional(CONF_AWAY_TEMP): vol.Coerce(float),
    vol.Optional(CONF_VACATION_TEMP): vol.Coerce(float),
    vol.Optional(CONF_NIGHT_TEMP): vol.Coerce(float),
    vol.Required(CONF_PUMPS): vol.All([CONFIG_TARGET_SWITCH]),
    vol.Required(CONF_SUBZONES): vol.All([CONFIG_SUBZONE]),
})

CONFIG_SCHEMA = vol.Schema({
        DOMAIN: vol.Schema({
            vol.Required(CONF_ZONES): vol.All([CONFIG_ZONE]),
        })
    },
    extra = vol.ALLOW_EXTRA,
)

async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    hass.states.async_set("multizone_heating.world", "TEST")
    _LOGGER.info(config[DOMAIN])
    for zone in config[DOMAIN].get(CONF_ZONES):
        _LOGGER.info(zone)
        hass.states.async_set("multizone_heating." + slugify(zone[CONF_NAME]), "ok")
    
    ces = hass.config_entries.async_entries()
    for ce in ces:
        _LOGGER.info(str(ce) + ", " + ce.domain + ", " + ce.entry_id)
    
    entry = ConfigEntry(
        version=1,
        domain=DOMAIN,
        source='user',
        title='Add zones',
        data='{}',
        entry_id = "eeb6ea8ffb3ef6fcf362aafc95ca2b7f",
    )
    #entry.entry_id = NAME
    hass.config_entries.async_add(entry)
    _LOGGER.info(entry.entry_id)

    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})
        _LOGGER.info(STARTUP_MESSAGE)

    coordinator = MZHCoordinator(hass)
    await coordinator.async_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    entry.unique_id = "valami_switch"
    coordinator.platforms.append("switch")
    hass.async_add_job(
        hass.config_entries.async_forward_entry_setup(entry, "switch")
    )

    return True


class MZHCoordinator(DataUpdateCoordinator):

    def __init__(self, hass):
        """Initialize my coordinator."""
        self.platforms = []
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name=DOMAIN,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=30),
        )

    async def _async_update_data(self):
        pass
