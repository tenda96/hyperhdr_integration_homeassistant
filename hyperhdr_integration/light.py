"""Piattaforma Light per gestire HyperHDR tramite Priorità (Always On)."""
import logging
import aiohttp
import async_timeout

from homeassistant.components.light import (
    LightEntity,
    LightEntityFeature,
    ColorMode,
    ATTR_RGB_COLOR,
    ATTR_EFFECT,
    ATTR_BRIGHTNESS,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_HOST, CONF_PORT, CONF_NAME, CONF_TOKEN

_LOGGER = logging.getLogger(__name__)

# Priorità usata da Home Assistant
HA_PRIORITY = 50

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Configura la luce HyperHDR."""
    config = entry.data
    async_add_entities([HyperHDRLight(
        config[CONF_HOST], 
        config[CONF_PORT], 
        config[CONF_NAME], 
        config.get(CONF_TOKEN), 
        entry.entry_id
    )])

class HyperHDRLight(LightEntity):
    """Rappresentazione di HyperHDR come Overlay (Sempre Connesso)."""

    def __init__(self, host, port, name, token, entry_id):
        self._host = host
        self._port = port
        self._name = name
        self._token = token
        self._entry_id = entry_id
        
        self._is_on = False
        self._available = False
        
        # Stato interno
        self._rgb_color = (255, 255, 255)
        self._brightness = 255
        self._effect = None
        self._effect_list = []
        
        # Attributi extra
        self._active_component_prio = None
        self._server_version = "Unknown"
        
        self._base_url = f"http://{host}:{port}/json-rpc"

    @property
    def unique_id(self):
        return f"hyperhdr_{self._entry_id}_light"

    @property
    def name(self):
        return self._name

    @property
    def icon(self):
        # Icona diversa se stiamo comandando noi o se è in video mode
        return "mdi:led-strip-variant" if self._is_on else "mdi:television-ambient-light"

    @property
    def is_on(self):
        # Per HA, la luce è "ON" solo se stiamo forzando un colore/effetto (Priority 50).
        # Se siamo in Video Mode (Priority 240), per HA risulta "OFF" (così puoi riaccenderla).
        return self._is_on

    @property
    def available(self):
        return self._available

    @property
    def brightness(self):
        return self._brightness

    @property
    def rgb_color(self):
        return self._rgb_color

    @property
    def supported_features(self):
        return LightEntityFeature.EFFECT

    @property
    def supported_color_modes(self):
        return {ColorMode.RGB}

    @property
    def color_mode(self):
        return ColorMode.RGB

    @property
    def effect_list(self):
        return self._effect_list

    @property
    def effect(self):
        return self._effect

    @property
    def extra_state_attributes(self):
        return {
            "hyperhdr_host": self._host,
            "hyperhdr_port": self._port,
            "server_version": self._server_version,
            "active_priority": self._active_component_prio,
            "connection_status": "Connected" if self._available else "Disconnected",
            "mode": "Home Assistant Override" if self._is_on else "Video Grabber / Idle"
        }

    async def
