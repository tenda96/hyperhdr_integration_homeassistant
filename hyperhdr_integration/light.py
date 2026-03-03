"""Light platform to manage HyperHDR via Priority (Pipeline Flush Fix)."""
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

# Priority used by Home Assistant
HA_PRIORITY = 50

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up the HyperHDR light platform."""
    config = entry.data
    async_add_entities([HyperHDRLight(
        config[CONF_HOST], 
        config[CONF_PORT], 
        config[CONF_NAME], 
        config.get(CONF_TOKEN), 
        entry.entry_id
    )])

class HyperHDRLight(LightEntity):
    """Representation of HyperHDR as an RGB Light with Unified Brightness."""

    def __init__(self, host, port, name, token, entry_id):
        self._host = host
        self._port = port
        self._name = name
        self._token = token
        self._entry_id = entry_id
        
        self._is_on = False
        self._available = False
        
        # Internal HA State (Absolute Truth for Brightness)
        self._rgb_color = (255, 255, 255)
        self._brightness = 255
        self._effect = None
        self._effect_list = []
        
        # Extra attributes
        self._active_component_prio = None
        self._server_version = "Unknown"
        
        self._base_url = f"http://{host}:{port}/json-rpc"

    @property
    def unique_id(self): return f"hyperhdr_{self._entry_id}_light"
    @property
    def name(self): return self._name
    @property
    def icon(self): return "mdi:led-strip-variant" if self._is_on else "mdi:television-ambient-light"
    @property
    def is_on(self): return self._is_on
    @property
    def available(self): return self._available
    @property
    def brightness(self): return self._brightness
    @property
    def rgb_color(self): return self._rgb_color
    @property
    def supported_features(self): return LightEntityFeature.EFFECT
    @property
    def supported_color_modes(self): return {ColorMode.RGB}
    @property
    def color_mode(self): return ColorMode.RGB
    @property
    def effect_list(self): return self._effect_list
    @property
    def effect(self): return self._effect

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
        """Send API command to HyperHDR."""
        headers = {"Authorization": f"token {self._token}"} if self._token else {}
        try:
            async with aiohttp.ClientSession() as session:
                with async_timeout.timeout(5):
                    async with session.post(self._base_url, json=payload, headers=headers) as response:
                        if response.status == 200:
                            return await response.json()
                        elif response.status == 401:
                            _LOGGER.warning("Invalid HyperHDR Token")
                            self._available = False
        except Exception:
            self._available = False
        return None

    async def async_update(self):
        """Update state from server."""
        payload = {"command": "serverinfo"}
        data = await self._send_command(payload)
        
        if data and "info" in data:
            self._available = True
            info = data["info"]
            self._server_version = info.get("hyperhdr", {}).get("version", "Unknown")

            if not self._effect_list:
                self._effect_list = sorted([fx["name"] for fx in info.get("effects", [])])

            priorities = info.get("priorities", [])
            ha_is_controlling = False
            active_prio_val = "Idle"

            visible_priority = next((p for p in priorities if p.get("visible", False)), None)
            
            if visible_priority:
                active_prio_val = visible_priority.get("priority")
                if active_prio_val == HA_PRIORITY:
                    ha_is_controlling = True
                    self._effect = visible_priority.get("owner") if visible_priority.get("componentId") == "EFFECT" else None
                
            self._active_component_prio = active_prio_val
            self._is_on = ha_is_controlling

            adjustments = info.get("adjustment", [])
            if adjustments and isinstance(adjustments, list):
                current_gain = adjustments[0].get("luminanceGain", 1.0)
                if not ha_is_controlling or self._effect:
                    self._brightness = int(current_gain * 255.0)

        else:
            self._available = False

    async def async_turn_on(self, **kwargs):
        """Activate HA Override (Unified Brightness handling with Pipeline Flush)."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._brightness)
        if brightness == 0:
             await self.async_turn_off()
             return

        self._brightness = brightness
        target_effect = kwargs.get(ATTR_EFFECT, self._effect)
        
        if ATTR_RGB_COLOR in kwargs:
            self._rgb_color = kwargs[ATTR_RGB_COLOR]
            target_effect = None 
            self._effect = None

        if ATTR_EFFECT in kwargs:
            target_effect = kwargs[ATTR_EFFECT]
            self._effect = target_effect

        await self._send_command({
            "command": "componentstate",
            "componentstate": {"component": "LEDDEVICE", "state": True}
        })

        if target_effect:
            # --- EFFECT MODE (Reverse Order Trick) ---
            gain = round(brightness / 255.0, 4)
            
            # 1. Apply global gain FIRST
            await self._send_command({
                "command": "adjustment",
                "adjustment": {"luminanceGain": gain}
            })
            
            # 2. CLEAR HA priority to force pipeline rebuild and apply the new gain immediately
            await self._send_command({
                "command": "clear",
                "priority": HA_PRIORITY
            })
            
            # 3. Launch effect fresh (it will instantiate with the new gain already applied)
            await self._send_command({
                "command": "effect",
                "effect": {"name": target_effect},
                "priority": HA_PRIORITY,
                "origin": "Home Assistant"
            })

        else:
            # --- SOLID COLOR MODE ---
            scale = brightness / 255.0
            final_rgb = [int(c * scale) for c in self._rgb_color]
            
            # 1. Send mathematical color first to overwrite active effects seamlessly
            await self._send_command({
                "command": "color",
                "color": final_rgb,
                "priority": HA_PRIORITY,
                "origin": "Home Assistant"
            })
            
            # 2. Force global gain to 1.0. We do this without a 'clear' command here
            # because solid colors don't suffer from the instance-caching bug of effects.
            await self._send_command({
                "command": "adjustment",
                "adjustment": {"luminanceGain": 1.0}
            })

        self._is_on = True

    async def async_turn_off(self, **kwargs):
        """Deactivate HA Override (Pass exact slider brightness to Grabber)."""
        gain = round(self._brightness / 255.0, 4)
        
        # Apply current HA brightness to Grabber BEFORE giving back control
        await self._send_command({
            "command": "adjustment",
            "adjustment": {"luminanceGain": gain}
        })
        
        # Clear HA priority 50
        await self._send_command({
            "command": "clear",
            "priority": HA_PRIORITY
        })
        
        # Ensure LEDs remain active for video passthrough
        await self._send_command({
            "command": "componentstate",
            "componentstate": {"component": "LEDDEVICE", "state": True}
        })

        self._is_on = False
        self._effect = None
