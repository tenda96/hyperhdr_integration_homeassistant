![Views](https://img.shields.io/endpoint?url=https%3A%2F%2Fhits.dwyl.com%2Ftenda96%2Fhyperhdr_integration_homeassistant.json%3Fcolor%3Dblue&style=for-the-badge)
![Stars](https://img.shields.io/github/stars/tenda96/hyperhdr_integration_homeassistant?style=for-the-badge&color=yellow)
![Forks](https://img.shields.io/github/forks/tenda96/hyperhdr_integration_homeassistant?style=for-the-badge&color=lightgrey)

# HyperHDR Integration for Home Assistant

[![version](https://img.shields.io/github/manifest-json/v/tenda96/hyperhdr_integration_homeassistant?filename=custom_components%2Fhyperhdr_integration%2Fmanifest.json)](https://github.com/tenda96/hyperhdr_integration_homeassistant)

A robust, native Home Assistant integration for **HyperHDR**.

Unlike simple switch-based integrations, this component creates a fully featured **Light Entity** for HyperHDR, with support for static colors, effects, brightness control, API authentication and configurable priority management.

It is especially useful for setups where HyperHDR normally follows a TV/HDMI/USB grabber signal, but Home Assistant can temporarily take control to show colors or effects.

<img src="custom_components/hyperhdr_integration/logo.png" width="150" alt="HyperHDR Logo">

## ✨ Features

* **Full Light Entity Support**
    * Control HyperHDR as a native Home Assistant light.
    * Supports ON/OFF, RGB color, brightness and effects.

* **Static Color & Effect Modes**
    * Use Home Assistant to show a fixed RGB color.
    * Select and run HyperHDR effects directly from the HA UI.
    * Effects are fetched automatically from the HyperHDR instance.

* **Shared Brightness**
    * Brightness is now consistent between static colors and effects.
    * The integration uses HyperHDR `adjustment.brightness`, which works properly with HyperHDR + WLED setups.
    * Switching from color to effect, or from effect to color, keeps the same brightness level.

* **Configurable Priority**
    * A dedicated priority slider lets you choose which HyperHDR priority Home Assistant should use.
    * Lower priority numbers win in HyperHDR.
    * Use a low value, such as `50`, if you want Home Assistant to override the video signal.
    * Use a higher value, such as `250` or `255`, if you want the video grabber/TV signal to win when active.

* **Automatic Fallback to Video Mode**
    * Turning off the Home Assistant light clears the HA priority.
    * HyperHDR can immediately return to the active video source/grabber.

* **Effect Reselect Fix**
    * Switching `effect → static color → same effect again` now works correctly.
    * Home Assistant no longer gets stuck thinking the previous effect is still active.

* **Rich Entity Attributes**
    * Exposes useful information such as host, port, server version, active priority, configured priority and connection status.

* **Config Flow**
    * Setup entirely via the Home Assistant UI.
    * No YAML required.

* **Authentication**
    * Supports HyperHDR API tokens.

## ⚙️ Installation

1. Download the latest release or clone this repository.
2. Copy the `hyperhdr_integration` folder into your Home Assistant `config/custom_components/` directory.
3. Restart Home Assistant.

Final path:

```text
config/custom_components/hyperhdr_integration/
```

## 🚀 Configuration

1. Go to **Settings** > **Devices & Services**.
2. Click **Add Integration** and search for **HyperHDR**.
3. Enter your details:
    * **Host:** IP address or hostname of your HyperHDR instance.
    * **Port:** HyperHDR JSON-RPC HTTP port.
    * **Token:** API token if authentication is enabled.
    * **Name:** Friendly name for the device.

### Docker Port Note

If HyperHDR runs in Docker, use the published host port.

Example:

```text
0.0.0.0:12000->8090/tcp
```

In this case, use:

```text
Port: 12000
```

not `8090`, unless Home Assistant is in the same Docker network and can reach the container directly.

### How to Get an API Token

If API authentication is enabled in HyperHDR:

1. Open the HyperHDR Web UI.
2. Go to **Settings** > **Network Services**.
3. Create a new API token.
4. Copy it and paste it into the integration configuration.

## 💡 Usage

This integration creates:

* a `light` entity, for color/effect/brightness control;
* a `number` entity, for HyperHDR priority control.

Example:

```text
light.ambilight
number.ambilight_priority
```

| State | HyperHDR Behavior |
| :--- | :--- |
| **OFF** | HA priority is cleared and HyperHDR returns to video/grabber mode. |
| **ON (Color)** | LEDs show the selected static RGB color. |
| **ON (Effect)** | LEDs play the selected HyperHDR effect. |

## 🔧 Troubleshooting

**Entity is unavailable:**
Check that HyperHDR is running, the host/port are correct, and the API token is valid.

**API says `No Authorization`:**
HyperHDR authentication is enabled. Create or update the API token in the integration configuration.

**Video does not win over Home Assistant:**
Check the priority values. If the video grabber uses priority `240`, set Home Assistant priority higher, such as `250` or `255`.

**Effect brightness does not change:**
Make sure you are using the latest version. The integration now uses `adjustment.brightness`, not `luminanceGain`.

**WLED brightness/current limits:**
If you use WLED, check the WLED maximum current limiter and brightness settings. Double-dimming between WLED and HyperHDR can cause unexpected behavior.

## 🧩 About `hacs.json`

The `hacs.json` file is used by HACS to display and install the repository correctly.

Example:

```json
{
  "name": "HyperHDR Integration",
  "render_readme": true
}
```

* `name`: name shown in HACS.
* `render_readme`: tells HACS to render this README in the integration page.

This file does not affect the runtime behavior of the Home Assistant integration.

## 📝 Changelog

### v2.1.7

* Fixed effect reselect behavior.
* Selecting the same effect again after switching to a static color now works correctly.
* Prevented stale effect state from keeping Home Assistant stuck on the previous effect.

### v2.1.6

* Reworked brightness handling.
* Static colors and effects now share the same brightness.
* Replaced `luminanceGain` dimming with HyperHDR `adjustment.brightness`.
* Fixed brightness changes on active effects.
* Improved behavior for HyperHDR + WLED setups.
* Removed unnecessary effect restarts for brightness changes.

### v2.1.0

* Added shared coordinator.
* Added configurable priority slider.
* Improved light/effect state handling.
* Added priority attributes and better connection state reporting.

### v2.0.0

* Improved solid color and effect switching.
* Added better brightness handling.
* Refactored the integration into a more complete Home Assistant light platform.

### v1.0.1

* Fixed issues where changing brightness could interrupt the active effect.
* Fixed loading issues for new installations.

### v1.0.0

* Initial release.
* Added basic HyperHDR light control with priority management and effect support.

## ❤️ Credits & Disclaimer

This is a **personal project** created because I couldn't find an existing integration that offered full Light control with proper Priority Management.

I am **not affiliated** with the official HyperHDR project in any way.

A huge thank you to the **HyperHDR team** for their incredible work on the software itself.

## 📜 License

MIT License
