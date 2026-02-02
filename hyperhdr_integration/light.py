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
            self._server_version = info.get("hyperhdr", {}).get("version", "Unknown")

            if not self._effect_list:
                raw_effects = info.get("effects", [])
                self._effect_list = sorted([fx["name"] for fx in raw_effects])

            # Analisi Priorità
            priorities = info.get("priorities", [])
            ha_is_controlling = False
            active_prio_val = "Idle"

            # Cerchiamo la priorità attiva più bassa (quella che comanda)
            visible_priority = None
            for prio in priorities:
                if prio.get("visible", False):
                    visible_priority = prio
                    break
            
            if visible_priority:
                active_prio_val = visible_priority.get("priority")
                
                # Se siamo noi a comandare (Priority 50)
                if active_prio_val == HA_PRIORITY:
                    ha_is_controlling = True
                    # Recuperiamo l'effetto attivo se c'è
                    if visible_priority.get("componentId") == "EFFECT":
                        self._effect = visible_priority.get("owner")
                    else:
                        self._effect = None
                
            self._active_component_prio = active_prio_val
            self._is_on = ha_is_controlling

        else:
            self._available = False

    async def async_turn_on(self, **kwargs):
        """Attiva Override HA (Priority 50)."""
        
        # 1. Assicuriamo che il componente LEDDEVICE sia SEMPRE attivo.
        #    Così WLED riceve sempre dati e non va in timeout.
        await self._send_command({
            "command": "componentstate",
            "componentstate": {"component": "LEDDEVICE", "state": True}
        })

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
        rgb = kwargs.get(ATTR_RGB_COLOR, self._rgb_color)
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._brightness)
        
        self._rgb_color = rgb
        self._brightness = brightness

        if brightness == 0:
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
        """Disattiva Override HA (Torna al Grabber)."""
        
        # NON spegniamo più il LEDDEVICE.
        # Facciamo solo "clear" della nostra priorità (50).
        # HyperHDR scenderà automaticamente alla priorità successiva (es. 240 Grabber).
        
        await self._send_command({
            "command": "clear",
            "priority": HA_PRIORITY
        })
        
        # Assicuriamoci che il LEDDEVICE sia ON (nel caso fosse stato spento manualmente)
        # così il Grabber può mandare il video (o il nero) a WLED.
        await self._send_command({
            "command": "componentstate",
            "componentstate": {"component": "LEDDEVICE", "state": True}
        })

        self._is_on = False
        self._effect = None
