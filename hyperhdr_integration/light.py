"""Piattaforma Light per gestire HyperHDR con Fix Luminosità e Attributi."""
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
    """Rappresentazione di HyperHDR come luce RGB Avanzata."""

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
        
        # Attributi extra per il debug/info
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
        return "mdi:led-strip-variant" if self._is_on else "mdi:television"

    @property
    def is_on(self):
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
        """Restituisce informazioni aggiuntive sull'entità."""
        return {
            "hyperhdr_host": self._host,
            "hyperhdr_port": self._port,
            "server_version": self._server_version,
            "active_priority": self._active_component_prio,
            "ha_priority_slot": HA_PRIORITY,
            "connection_status": "Connected" if self._available else "Disconnected",
        }

    async def _send_command(self, payload):
        """Invia comando API."""
        headers = {}
        if self._token:
            headers["Authorization"] = f"token {self._token}"
            
        try:
            async with aiohttp.ClientSession() as session:
                with async_timeout.timeout(5):
                    async with session.post(self._base_url, json=payload, headers=headers) as response:
                        if response.status == 200:
                            return await response.json()
                        elif response.status == 401:
                            _LOGGER.warning("Token HyperHDR non valido")
                            self._available = False
        except Exception:
            self._available = False
        return None

    async def async_update(self):
        """Aggiorna lo stato."""
        payload = {"command": "serverinfo"}
        data = await self._send_command(payload)
        
        if data and "info" in data:
            self._available = True
            info = data["info"]
            
            # Info server
            self._server_version = info.get("hyperhdr", {}).get("version", "Unknown")

            # Lista effetti
            if not self._effect_list:
                raw_effects = info.get("effects", [])
                self._effect_list = sorted([fx["name"] for fx in raw_effects])

            # Analisi Priorità
            priorities = info.get("priorities", [])
            
            ha_is_controlling = False
            active_prio_val = "Idle"

            # Cerchiamo chi sta comandando (la priorità visibile più bassa)
            visible_priority = None
            for prio in priorities:
                if prio.get("visible", False):
                    visible_priority = prio
                    break
            
            if visible_priority:
                active_prio_val = visible_priority.get("priority")
                
                # Se la priorità attiva è la nostra (50)
                if active_prio_val == HA_PRIORITY:
                    ha_is_controlling = True
                    # FIX LUMINOSITÀ: NON aggiorniamo _rgb_color o _brightness dal server
                    # perché il server contiene il valore già dimmerato.
                    # Ci fidiamo dello stato interno di HA.
                    
                    # Aggiorniamo solo l'effetto se presente
                    if visible_priority.get("componentId") == "EFFECT":
                        self._effect = visible_priority.get("owner")
                    else:
                        self._effect = None
                
            self._active_component_prio = active_prio_val
            self._is_on = ha_is_controlling

        else:
            self._available = False

    async def async_turn_on(self, **kwargs):
        """Accende la luce."""
        
        # Gestione Effetti
        if ATTR_EFFECT in kwargs:
            effect_name = kwargs[ATTR_EFFECT]
            await self._send_command({
                "command": "effect",
                "effect": {"name": effect_name},
                "priority": HA_PRIORITY,
                "origin": "Home Assistant"
            })
            self._effect = effect_name
            self._is_on = True
            return

        # Gestione Colore / Luminosità
        # Se l'utente cambia solo la luminosità, usiamo il colore che avevamo in memoria
        rgb = kwargs.get(ATTR_RGB_COLOR, self._rgb_color)
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._brightness)
        
        # Salviamo lo stato "puro" (non dimmerato) in HA
        self._rgb_color = rgb
        self._brightness = brightness

        # Calcoliamo il colore da mandare a HyperHDR (Dimmerato)
        if brightness == 0:
             # Caso limite, spegniamo la priorità
             await self.async_turn_off()
             return

        scale = brightness / 255.0
        final_rgb = [int(c * scale) for c in rgb]

        await self._send_command({
            "command": "color",
            "color": final_rgb,
            "priority": HA_PRIORITY,
            "origin": "Home Assistant"
        })
        
        self._effect = None
        self._is_on = True

    async def async_turn_off(self, **kwargs):
        """Spegne la luce (Pulisce Priorità 50)."""
        await self._send_command({
            "command": "clear",
            "priority": HA_PRIORITY
        })
        self._is_on = False
        self._effect = None