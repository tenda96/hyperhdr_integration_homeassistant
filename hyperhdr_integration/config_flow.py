"""Config flow for HyperHDR Simple."""
import logging
import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_NAME, CONF_TOKEN

from .const import DOMAIN, DEFAULT_PORT, DEFAULT_NAME

_LOGGER = logging.getLogger(__name__)

def get_schema(defaults=None):
    """Generate the form schema with optional default values."""
    defaults = defaults or {}
    return vol.Schema({
        vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
        vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): int,
        vol.Optional(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)): str,
        vol.Optional(CONF_TOKEN, default=defaults.get(CONF_TOKEN, "")): str,
    })

async def validate_input(hass, data):
    """Verify the connection settings."""
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    token = data.get(CONF_TOKEN)
    url = f"http://{host}:{port}/json-rpc"
    
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"

    try:
        async with aiohttp.ClientSession() as session:
            with async_timeout.timeout(5):
                payload = {"command": "serverinfo"}
                async with session.post(url, json=payload, headers=headers) as response:
                    # We accept 200 (OK), 401/403 (Auth error but connected)
                    if response.status not in (200, 401, 403):
                        raise Exception("HTTP Error")
                    
                    # Verify token if status is 200
                    if response.status == 200:
                        resp_json = await response.json()
                        if not resp_json.get("success", True):
                             raise ValueError("invalid_auth")

    except ValueError as e:
        raise e
    except Exception:
        raise ValueError("cannot_connect")

class HyperHDRConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup flow."""
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Activate the options flow."""
        return HyperHDROptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the user step."""
        errors = {}
        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
            except ValueError as err:
                errors["base"] = str(err)
            except Exception:
                errors["base"] = "unknown"

        return self.async_show_form(step_id="user", data_schema=get_schema(), errors=errors)

class HyperHDROptionsFlow(config_entries.OptionsFlow):
    """Handle the modification of parameters."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        # FIX: We use self._config_entry as self.config_entry is protected
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle the initialization step."""
        errors = {}
        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
                # Update the entry data
                self.hass.config_entries.async_update_entry(
                    self._config_entry, data=user_input
                )
                return self.async_create_entry(title="", data={})
            except ValueError as err:
                errors["base"] = str(err)

        # Pre-populate the form with current data
        return self.async_show_form(
            step_id="init",
            data_schema=get_schema(self._config_entry.data),
            errors=errors
        )
