"""Regression tests for HyperHDR brightness commands without a HA installation."""

import asyncio
import importlib
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _module(name, **attributes):
    module = types.ModuleType(name)
    module.__dict__.update(attributes)
    sys.modules[name] = module
    return module


class _CoordinatorEntity:
    def __init__(self, coordinator):
        self.coordinator = coordinator

    def async_write_ha_state(self):
        pass


_module("homeassistant")
_module("homeassistant.components")
_module(
    "homeassistant.components.light",
    ATTR_BRIGHTNESS="brightness",
    ATTR_EFFECT="effect",
    ATTR_RGB_COLOR="rgb_color",
    ColorMode=types.SimpleNamespace(RGB="rgb"),
    LightEntity=type("LightEntity", (), {}),
    LightEntityFeature=types.SimpleNamespace(EFFECT=4),
)
_module("homeassistant.config_entries", ConfigEntry=object)
_module("homeassistant.core", HomeAssistant=object)
_module("homeassistant.helpers")
_module("homeassistant.helpers.entity_platform", AddEntitiesCallback=object)
_module("homeassistant.helpers.update_coordinator", CoordinatorEntity=_CoordinatorEntity)
_module("custom_components", __path__=[str(ROOT / "custom_components")])
_module(
    "custom_components.hyperhdr_integration",
    __path__=[str(ROOT / "custom_components" / "hyperhdr_integration")],
)
_module("custom_components.hyperhdr_integration.coordinator", HyperHDRCoordinator=object)

HyperHDRLight = importlib.import_module("custom_components.hyperhdr_integration.light").HyperHDRLight


class _FakeCoordinator:
    def __init__(self, adjustment, component="EFFECT"):
        self.data = {
            "adjustment": [adjustment],
            "priorities": [
                {
                    "priority": 53,
                    "visible": True,
                    "componentId": component,
                    "owner": "Double swirl",
                    "value": {"RGB": [20, 40, 60]},
                }
            ],
        }
        self.priority = 53
        self.last_update_success = True
        self.commands = []
        self.host = "localhost"
        self.port = 8090

    def visible_priority(self):
        return self.data["priorities"][0]

    def is_priority_visible(self, priority):
        return priority == 53

    async def async_send_commands(self, commands, *, refresh=True):
        self.commands.extend(commands)
        for command in commands:
            if command["command"] == "adjustment":
                self.data["adjustment"][0].update(command["adjustment"])


class BrightnessTests(unittest.TestCase):
    def test_v22_effect_brightness_uses_scale_output_without_restarting_effect(self):
        coordinator = _FakeCoordinator({"scaleOutput": 1.0})
        light = HyperHDRLight(coordinator, "HyperHDR", "test")
        light._requested_mode = "effect"
        light._effect = "Double swirl"

        asyncio.run(light.async_turn_on(brightness=128))

        self.assertEqual([item["command"] for item in coordinator.commands], ["componentstate", "adjustment"])
        self.assertEqual(coordinator.commands[1]["adjustment"], {"scaleOutput": 128 / 255})
        self.assertEqual(light.brightness, 128)

    def test_v22_color_activation_uses_scale_output(self):
        coordinator = _FakeCoordinator({"scaleOutput": 1.0}, component="COLOR")
        light = HyperHDRLight(coordinator, "HyperHDR", "test")

        asyncio.run(light.async_turn_on(brightness=128, rgb_color=(20, 40, 60)))

        self.assertEqual(coordinator.commands[1]["adjustment"], {"scaleOutput": 128 / 255})
        self.assertEqual(coordinator.commands[2]["color"], [10, 20, 30])
        self.assertEqual(light.rgb_color, (20, 40, 60))

    def test_v22_color_brightness_change_resends_scaled_rgb(self):
        coordinator = _FakeCoordinator({"scaleOutput": 1.0}, component="COLOR")
        light = HyperHDRLight(coordinator, "HyperHDR", "test")
        asyncio.run(light.async_turn_on(brightness=255, rgb_color=(200, 100, 50)))
        coordinator.commands.clear()

        asyncio.run(light.async_turn_on(brightness=128))

        self.assertEqual([item["command"] for item in coordinator.commands], ["componentstate", "adjustment", "color"])
        self.assertEqual(coordinator.commands[2]["color"], [100, 50, 25])
        self.assertEqual(light.rgb_color, (200, 100, 50))

    def test_v22_visible_color_is_preserved_after_entity_restart(self):
        coordinator = _FakeCoordinator({"scaleOutput": 1.0}, component="COLOR")
        light = HyperHDRLight(coordinator, "HyperHDR", "test")

        asyncio.run(light.async_turn_on(brightness=128))

        self.assertEqual(coordinator.commands[2]["color"], [10, 20, 30])
        self.assertEqual(light.rgb_color, (20, 40, 60))

    def test_v22_low_brightness_keeps_home_assistant_precision(self):
        coordinator = _FakeCoordinator({"scaleOutput": 1.0})
        light = HyperHDRLight(coordinator, "HyperHDR", "test")

        asyncio.run(light.async_turn_on(brightness=1))

        self.assertEqual(coordinator.commands[1]["adjustment"], {"scaleOutput": 1 / 255})
        self.assertEqual(light.brightness, 1)

    def test_legacy_server_keeps_brightness_field(self):
        coordinator = _FakeCoordinator({"brightness": 100})
        light = HyperHDRLight(coordinator, "HyperHDR", "test")

        asyncio.run(light.async_turn_on(brightness=128, effect="Double swirl"))

        self.assertEqual(coordinator.commands[1]["adjustment"], {"brightness": 50})
        self.assertEqual(coordinator.commands[2]["command"], "effect")

    def test_legacy_color_still_sends_unscaled_rgb(self):
        coordinator = _FakeCoordinator({"brightness": 100}, component="COLOR")
        light = HyperHDRLight(coordinator, "HyperHDR", "test")

        asyncio.run(light.async_turn_on(brightness=128, rgb_color=(20, 40, 60)))

        self.assertEqual(coordinator.commands[1]["adjustment"], {"brightness": 50})
        self.assertEqual(coordinator.commands[2]["color"], [20, 40, 60])

    def test_absent_brightness_field_does_not_claim_full_brightness(self):
        coordinator = _FakeCoordinator({"luminanceGain": 1.0})
        light = HyperHDRLight(coordinator, "HyperHDR", "test")

        self.assertIsNone(light._current_hyperhdr_brightness())


if __name__ == "__main__":
    unittest.main()
