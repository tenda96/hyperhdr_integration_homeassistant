"""Light platform for HyperHDR with priority management."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_NAME, DOMAIN
from .coordinator import HyperHDRCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the HyperHDR light platform."""
    coordinator: HyperHDRCoordinator = hass.data[DOMAIN][entry.entry_id]
    name = entry.data.get(CONF_NAME, "HyperHDR")
    async_add_entities([HyperHDRLight(coordinator, name, entry.entry_id)])


class HyperHDRLight(CoordinatorEntity, LightEntity):
    """Represent HyperHDR as an RGB light with effect support.

    Brightness handling note:
    -------------------------
    HyperHDR 22 uses ``adjustment.scaleOutput`` for effect brightness. Static
    colors on that release need their RGB values scaled as well: changing the
    adjustment alone does not visibly dim a static color. Older releases use
    ``adjustment.brightness`` for both modes.
    """

    def __init__(self, coordinator: HyperHDRCoordinator, name: str, entry_id: str) -> None:
        """Initialize the light entity."""
        super().__init__(coordinator)
        self.coordinator: HyperHDRCoordinator = coordinator
        self.coordinator.light_entity = self

        self._entry_id = entry_id
        self._attr_name = name
        self._attr_unique_id = f"hyperhdr_{entry_id}_light"

        self._rgb_color: tuple[int, int, int] = (255, 255, 255)
        self._brightness = 255
        self._effect: str | None = None
        self._effect_list: list[str] = []

        # Local requested mode is kept as HA intent. HyperHDR may be showing a
        # different lower priority source, for example the video grabber.
        self._requested_mode: str | None = None
        self._last_hyperhdr_brightness: int | None = None
        self._last_hyperhdr_luminance_gain: float | None = None
        self._last_hyperhdr_scale_output: float | None = None
        self._last_command_path: str | None = None
        self._last_sent_priority = int(self.coordinator.priority)
        self._last_priority_migration: str | None = None
        self._active_component_prio: int | str | None = None
        self._active_component: str | None = None
        self._active_owner: str | None = None
        self._server_version = "Unknown"

    @property
    def icon(self) -> str:
        """Return the icon for the light."""
        return "mdi:led-strip-variant" if self.is_on else "mdi:television-ambient-light"

    @property
    def available(self) -> bool:
        """Return True if the entity is available."""
        return self.coordinator.last_update_success

    @property
    def current_priority(self) -> int:
        """Return the configured Home Assistant priority."""
        return int(self.coordinator.priority)

    @property
    def is_on(self) -> bool:
        """Return True if HyperHDR is currently showing our configured priority."""
        return self.coordinator.is_priority_visible(self.current_priority)

    @property
    def brightness(self) -> int:
        """Return the Home Assistant brightness value between 1 and 255."""
        scale_output = self._current_hyperhdr_scale_output()
        if scale_output is not None:
            self._brightness = max(1, min(255, round(scale_output * 255)))
            return self._brightness
        hyperhdr_brightness = self._current_hyperhdr_brightness()
        if hyperhdr_brightness is not None:
            self._brightness = self._ha_brightness_from_hyperhdr_brightness(hyperhdr_brightness)
        return self._brightness

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        """Return the selected RGB color, before any brightness scaling."""
        return self._rgb_color

    @property
    def supported_features(self) -> LightEntityFeature:
        """Return supported light features."""
        return LightEntityFeature.EFFECT

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Return supported color modes."""
        return {ColorMode.RGB}

    @property
    def color_mode(self) -> ColorMode:
        """Return current color mode."""
        return ColorMode.RGB

    @property
    def effect_list(self) -> list[str]:
        """Return supported HyperHDR effects."""
        if self.coordinator.data:
            effects = self.coordinator.data.get("effects", [])
            self._effect_list = sorted(
                effect["name"] for effect in effects if isinstance(effect, dict) and "name" in effect
            )
        return self._effect_list

    @property
    def effect(self) -> str | None:
        """Return the current/requested effect.

        Home Assistant keeps the selected effect in the UI until this property
        returns ``None``. When the user switches from an effect to a static
        color, our local requested mode must therefore win over possibly stale
        coordinator data from the previous serverinfo poll; otherwise selecting
        the same effect again may not send a new command.
        """
        if self._requested_mode == "color":
            return None

        visible_priority = self.coordinator.visible_priority()
        if (
            visible_priority
            and visible_priority.get("priority") == self.current_priority
            and visible_priority.get("componentId") == "EFFECT"
        ):
            self._effect = visible_priority.get("owner")
            self._requested_mode = "effect"
            return self._effect

        if self._requested_mode == "effect":
            return self._effect

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return useful HyperHDR state attributes."""
        if self.coordinator.data:
            self._server_version = self.coordinator.data.get("hyperhdr", {}).get("version", "Unknown")
            visible_priority = self.coordinator.visible_priority()
            if visible_priority:
                self._active_component_prio = visible_priority.get("priority")
                self._active_component = visible_priority.get("componentId")
                self._active_owner = visible_priority.get("owner")
            else:
                self._active_component_prio = "Idle"
                self._active_component = None
                self._active_owner = None

            self._last_hyperhdr_brightness = self._current_hyperhdr_brightness()
            self._last_hyperhdr_luminance_gain = self._current_hyperhdr_luminance_gain()
            self._last_hyperhdr_scale_output = self._current_hyperhdr_scale_output()

        return {
            "hyperhdr_host": self.coordinator.host,
            "hyperhdr_port": self.coordinator.port,
            "server_version": self._server_version,
            "active_priority": self._active_component_prio,
            "active_component": self._active_component,
            "active_owner": self._active_owner,
            "configured_priority": self.current_priority,
            "requested_mode": self._requested_mode,
            "requested_effect": self._effect,
            "ha_brightness": self._brightness,
            "hyperhdr_brightness": self._last_hyperhdr_brightness,
            "hyperhdr_luminance_gain": self._last_hyperhdr_luminance_gain,
            "hyperhdr_scale_output": self._last_hyperhdr_scale_output,
            "last_command_path": self._last_command_path,
            "last_sent_priority": self._last_sent_priority,
            "last_priority_migration": self._last_priority_migration,
            "connection_status": "Connected" if self.available else "Disconnected",
            "mode": "Home Assistant Override" if self.is_on else "Video Grabber / Idle",
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Activate Home Assistant control in HyperHDR."""
        explicit_color = ATTR_RGB_COLOR in kwargs
        explicit_effect = ATTR_EFFECT in kwargs and kwargs.get(ATTR_EFFECT) is not None
        brightness_only = ATTR_BRIGHTNESS in kwargs and not explicit_color and not explicit_effect

        brightness = self._sanitize_brightness(kwargs.get(ATTR_BRIGHTNESS, self._brightness))
        if brightness <= 0:
            await self.async_turn_off()
            return

        self._brightness = brightness
        priority = self.current_priority

        if explicit_color:
            self._rgb_color = tuple(int(value) for value in kwargs[ATTR_RGB_COLOR])
            self._effect = None
            self._requested_mode = "color"
            await self._activate_color(priority)

        elif explicit_effect:
            self._effect = kwargs[ATTR_EFFECT]
            self._requested_mode = "effect"
            await self._activate_effect(self._effect, priority)

        elif brightness_only:
            await self._handle_brightness_only(priority)

        else:
            # Generic turn_on with no specific color/effect: restore the last
            # requested mode if possible, otherwise show the stored color.
            if self._requested_mode == "effect" and self._effect:
                await self._activate_effect(self._effect, priority)
            else:
                self._requested_mode = "color"
                self._effect = None
                await self._activate_color(priority)

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Clear Home Assistant priorities and return control to HyperHDR/grabber."""
        priorities_to_clear = {self.current_priority, self._last_sent_priority}

        payloads: list[dict[str, Any]] = [
            {"command": "clear", "priority": int(priority)}
            for priority in sorted(priorities_to_clear)
            if priority is not None
        ]
        payloads.append(
            {
                "command": "componentstate",
                "componentstate": {"component": "LEDDEVICE", "state": True},
            }
        )

        await self.coordinator.async_send_commands(payloads)

        self._effect = None
        self._requested_mode = None
        self._last_command_path = "turn_off_clear_known_ha_priorities"
        self._last_priority_migration = None
        self.async_write_ha_state()

    async def async_migrate_priority(self, old_priority: int, new_priority: int) -> None:
        """Move or clear the current HA override when the priority slider changes.

        HyperHDR does not move an existing source when the numeric priority is
        changed in Home Assistant. If a color/effect was previously sent at
        priority 50, that priority keeps existing until it is explicitly
        cleared. This method recreates the current HA output at the new
        priority when appropriate, then clears the old priority so stale HA
        sources cannot keep winning over the video grabber.
        """
        if old_priority == new_priority:
            return

        # Make the decision using the freshest serverinfo we can get.
        await self.coordinator.async_request_refresh()

        old_item = self.coordinator.priority_item(old_priority)
        old_is_active = bool(old_item and old_item.get("active", False))
        old_is_visible = self.coordinator.is_priority_visible(old_priority)
        should_recreate = old_is_active or old_is_visible or self._requested_mode in ("color", "effect")

        if should_recreate:
            active_effect = None
            if old_item and old_item.get("componentId") == "EFFECT":
                active_effect = old_item.get("owner")
            elif self._requested_mode == "effect" and self._effect:
                active_effect = self._effect

            if active_effect:
                self._effect = str(active_effect)
                self._requested_mode = "effect"
                await self._activate_effect(self._effect, new_priority, refresh=False)
            else:
                self._requested_mode = "color"
                self._effect = None
                await self._activate_color(new_priority, refresh=False)

        # Always clear the old priority after a change. This is the important
        # part for video-priority mode: otherwise an old priority 50 source can
        # remain active and keep beating the grabber at priority 240.
        await self.coordinator.async_send_command(
            {"command": "clear", "priority": int(old_priority)},
            refresh=True,
        )

        self._last_sent_priority = int(new_priority) if should_recreate else self._last_sent_priority
        self._last_priority_migration = f"{old_priority}->{new_priority}, recreated={should_recreate}"
        self.async_write_ha_state()

    async def _handle_brightness_only(self, priority: int) -> None:
        """Apply a brightness-only update without changing color/effect mode."""
        # If the last user action was a static color, keep it as a color even if
        # the coordinator still contains stale EFFECT data from the previous
        # poll. This keeps HA's effect selector cleared and makes re-selecting
        # the same effect work correctly.
        if self._requested_mode == "color":
            await self._activate_color(priority)
            return

        visible_priority = self.coordinator.visible_priority()
        if (
            visible_priority
            and visible_priority.get("priority") == priority
            and visible_priority.get("componentId") == "COLOR"
        ):
            value = visible_priority.get("value")
            rgb = value.get("RGB") if isinstance(value, dict) else None
            if isinstance(rgb, list) and len(rgb) == 3:
                self._rgb_color = tuple(int(channel) for channel in rgb)
            self._requested_mode = "color"
            self._effect = None
            await self._activate_color(priority)
            return

        # If HA already controls HyperHDR, changing only the adjustment brightness
        # is enough for both colors and effects. This avoids clear/restart flashes.
        if self.is_on or self._requested_mode == "effect":
            visible_effect = self._visible_effect_for_current_priority()
            if visible_effect:
                self._effect = visible_effect
                self._requested_mode = "effect"
            await self._apply_shared_brightness(priority)
            return

        # If HA is currently off and receives a brightness-only turn_on, use the
        # last requested mode when available, otherwise default to stored color.
        if self._requested_mode == "effect" and self._effect:
            await self._activate_effect(self._effect, priority)
        else:
            self._requested_mode = "color"
            self._effect = None
            await self._activate_color(priority)

    async def _activate_effect(
        self,
        effect_name: str,
        priority: int,
        *,
        refresh: bool = True,
    ) -> None:
        """Start an effect using the shared HyperHDR brightness adjustment."""
        brightness_adjustment = self._brightness_adjustment()
        self._last_sent_priority = int(priority)
        self._last_command_path = "activate_effect_brightness_no_clear"

        await self.coordinator.async_send_commands(
            [
                {
                    "command": "componentstate",
                    "componentstate": {"component": "LEDDEVICE", "state": True},
                },
                {
                    "command": "adjustment",
                    "adjustment": brightness_adjustment,
                },
                {
                    "command": "effect",
                    "effect": {"name": effect_name},
                    "priority": priority,
                    "origin": "Home Assistant",
                },
            ],
            refresh=refresh,
        )

    async def _activate_color(self, priority: int, *, refresh: bool = True) -> None:
        """Show a static color and apply the server's brightness behavior."""
        brightness_adjustment = self._brightness_adjustment()
        adjustment = self._current_adjustment()
        if adjustment is not None and "scaleOutput" in adjustment:
            ratio = self._brightness / 255.0
            color = [max(0, min(255, round(channel * ratio))) for channel in self._rgb_color]
            self._last_command_path = "activate_color_scaled_rgb"
        else:
            color = [int(channel) for channel in self._rgb_color]
            self._last_command_path = "activate_color_brightness_unscaled_rgb"
        self._last_sent_priority = int(priority)

        await self.coordinator.async_send_commands(
            [
                {
                    "command": "componentstate",
                    "componentstate": {"component": "LEDDEVICE", "state": True},
                },
                {
                    "command": "adjustment",
                    "adjustment": brightness_adjustment,
                },
                {
                    "command": "color",
                    "color": color,
                    "priority": priority,
                    "origin": "Home Assistant",
                },
            ],
            refresh=refresh,
        )

    async def _apply_shared_brightness(self, priority: int, *, refresh: bool = True) -> None:
        """Apply only shared brightness, keeping the current HyperHDR source."""
        brightness_adjustment = self._brightness_adjustment()
        self._last_command_path = "apply_shared_brightness_only"

        await self.coordinator.async_send_commands(
            [
                {
                    "command": "componentstate",
                    "componentstate": {"component": "LEDDEVICE", "state": True},
                },
                {
                    "command": "adjustment",
                    "adjustment": brightness_adjustment,
                },
            ],
            refresh=refresh,
        )

    def _visible_effect_for_current_priority(self) -> str | None:
        """Return the visible effect name for the configured priority, if any."""
        visible_priority = self.coordinator.visible_priority()
        if (
            visible_priority
            and visible_priority.get("priority") == self.current_priority
            and visible_priority.get("componentId") == "EFFECT"
        ):
            owner = visible_priority.get("owner")
            return str(owner) if owner else None
        return None

    def _current_hyperhdr_brightness(self) -> int | None:
        """Return the server's shared brightness as a percentage, if available."""
        adjustment = self._current_adjustment()
        if adjustment is None:
            return None
        try:
            if "scaleOutput" in adjustment:
                return max(0, min(100, round(float(adjustment["scaleOutput"]) * 100)))
            if "brightness" in adjustment:
                return max(0, min(100, round(float(adjustment["brightness"]))))
        except (TypeError, ValueError):
            pass
        return None

    def _current_hyperhdr_scale_output(self) -> float | None:
        """Return the raw HyperHDR 22 output scale for diagnostics."""
        adjustment = self._current_adjustment()
        if adjustment is None or "scaleOutput" not in adjustment:
            return None
        try:
            return float(adjustment["scaleOutput"])
        except (TypeError, ValueError):
            return None

    def _current_adjustment(self) -> dict[str, Any] | None:
        """Return the first adjustment reported by serverinfo."""
        if not self.coordinator.data:
            return None
        adjustments = self.coordinator.data.get("adjustment")
        if isinstance(adjustments, list) and adjustments and isinstance(adjustments[0], dict):
            return adjustments[0]
        return None

    def _brightness_adjustment(self) -> dict[str, float | int]:
        """Build the brightness command for the server's adjustment format."""
        percentage = self._hyperhdr_brightness_from_ha_brightness(self._brightness)
        self._last_hyperhdr_brightness = percentage
        adjustment = self._current_adjustment()
        if adjustment is not None and "scaleOutput" in adjustment:
            scale_output = self._brightness / 255.0
            self._last_hyperhdr_scale_output = scale_output
            return {"scaleOutput": scale_output}
        self._last_hyperhdr_scale_output = None
        return {"brightness": percentage}

    def _current_hyperhdr_luminance_gain(self) -> float | None:
        """Return HyperHDR luminanceGain for debugging only."""
        adjustment = self._current_adjustment()
        if adjustment is None:
            return None
        try:
            if "luminanceGain" in adjustment:
                return float(adjustment["luminanceGain"])
        except (TypeError, ValueError):
            pass
        return None

    @staticmethod
    def _hyperhdr_brightness_from_ha_brightness(value: int) -> int:
        """Convert Home Assistant brightness 0..255 to HyperHDR brightness 0..100."""
        return max(1, min(100, int(round((int(value) / 255.0) * 100))))

    @staticmethod
    def _ha_brightness_from_hyperhdr_brightness(value: int) -> int:
        """Convert HyperHDR brightness 0..100 to Home Assistant brightness 1..255."""
        return max(1, min(255, int(round((int(value) / 100.0) * 255))))

    @staticmethod
    def _sanitize_brightness(value: Any) -> int:
        """Clamp Home Assistant brightness to the valid range."""
        try:
            return max(0, min(255, int(value)))
        except (TypeError, ValueError):
            return 255
