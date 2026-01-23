# HyperHDR Integration for Home Assistant

A robust, native Home Assistant integration for **HyperHDR** (the open-source ambient lighting software). 

Unlike other integrations that act as simple switches, this component creates a fully featured **Light Entity** that manages **Priorities** intelligently. It allows you to seamlessly switch between your TV Input (USB Grabber) and Home Assistant colors/effects without conflicts, while providing **detailed entity attributes** (server version, active priority, ports) for full monitoring.

<img src="hyperhdr_integration/logo.png" width="150" alt="HyperHDR Logo">

## ✨ Features

* **Priority Management (The "Smart" Part):**
    * **Light OFF:** HyperHDR runs in *Video Mode* (USB Grabber has priority). The LEDs follow your TV screen.
    * **Light ON:** Home Assistant takes control (Priority 50). The LEDs display the color or effect selected in HA.
    * **Automatic Fallback:** Turning off the light in HA immediately clears the priority, instantly returning control to the USB Grabber.
* **Full RGB Support:** Includes brightness and color control via the standard HA UI.
* **Effect Support:** Automatically fetches the list of effects from your HyperHDR instance.
* **Rich Entity Attributes:** Exposes useful info like Server Version, Active Priority ID, and Connection Status directly in the entity.
* **Config Flow:** Setup entirely via the UI (no YAML required).
* **Authentication:** Supports HyperHDR API Tokens for secure connections.

## ⚙️ Installation

1.  Download the latest release or clone this repository.
2.  Copy the `hyperhdr_integration` folder into your Home Assistant's `config/custom_components/` directory.
3.  Restart Home Assistant.

## 🚀 Configuration

1.  Go to **Settings** > **Devices & Services**.
2.  Click **Add Integration** and search for **HyperHDR**.
3.  Enter your details:
    * **Host:** IP address of your HyperHDR instance (e.g., `192.168.1.x`).
    * **Port:** The JSON-RPC port (Default is `8090` or `12000` depending on your Docker setup. Do **not** use the flatbuffer port).
    * **Token:** (Optional) API Token if you have authentication enabled in HyperHDR.
    * **Name:** Give your device a name (e.g., "Ambilight").

### How to get an API Token
If you have "API Authentication" enabled in HyperHDR:
1.  Open HyperHDR WebUI.
2.  Go to **Settings** > **Network Services**.
3.  Under **API Authentication**, create a new token (e.g., named "HomeAssistant").
4.  Copy the token immediately and paste it into the integration configuration.

## 💡 Usage

This integration creates a `light` entity (e.g., `light.ambilight`).

| State | HyperHDR Behavior | Priority Used |
| :--- | :--- | :--- |
| **OFF** | **Video Mode:** LEDs act as Ambilight (controlled by USB Grabber/Platform Capture). | Grabber (Default: 240) |
| **ON (Color)** | **Static Color:** LEDs show the specific color chosen in HA. | Home Assistant (50) |
| **ON (Effect)** | **Effect Mode:** LEDs play the selected effect (e.g., Rainbow, Knight Rider). | Home Assistant (50) |

### Brightness & WLED Warning
If you experience flickering or the light dimming unexpectedly when re-enabling it, check your **WLED** settings. Ensure that the **Maximum Current** limiter in WLED (LED Preferences) is disabled or set high enough. HyperHDR respects the physical limits of WLED, and double-dimming (HA dimming + WLED limiter) can cause issues.

## 🔧 Troubleshooting

**Entity is Unavailable:**
Check the logs in Home Assistant. If you see "Token non valido" or "HyperHDR Auth failed", verify your API Token.

**Icons/Logo not showing:**
Clear your browser cache (CTRL+F5) or restart the Home Assistant app.

## ❤️ Credits & Disclaimer

This is a **personal project** created because I couldn't find an existing integration that offered full Light control with proper Priority Management.

I am **not affiliated** with the official HyperHDR project in any way.
A huge thank you to the **HyperHDR team** for their incredible work on the software itself—it's an amazing piece of engineering that makes this integration possible!

## 📜 License
MIT License
