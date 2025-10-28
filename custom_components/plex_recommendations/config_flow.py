"""Config flow for Plex Recommendations integration."""
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_API_URL,
    CONF_API_KEY,
    ENDPOINT_HEALTH,
)

_LOGGER = logging.getLogger(__name__)


async def validate_api(hass: HomeAssistant, api_url: str, api_key: str) -> dict[str, Any]:
    """Validate the API connection."""
    session = async_get_clientsession(hass)
    
    # Remove trailing slash from URL
    api_url = api_url.rstrip('/')
    
    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key
    
    try:
        async with session.get(
            f"{api_url}{ENDPOINT_HEALTH}",
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=10)
        ) as response:
            if response.status == 401:
                raise ValueError("Invalid API key")
            if response.status != 200:
                raise ValueError(f"API returned status {response.status}")
            
            data = await response.json()
            return {"title": "Plex Recommendations", "status": data.get("status")}
    
    except aiohttp.ClientError as err:
        _LOGGER.error("Error connecting to API: %s", err)
        raise ValueError("Cannot connect to API") from err


class PlexRecommendationsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Plex Recommendations."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                info = await validate_api(
                    self.hass,
                    user_input[CONF_API_URL],
                    user_input.get(CONF_API_KEY, "")
                )
                
                # Create unique ID based on API URL
                await self.async_set_unique_id(user_input[CONF_API_URL])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                )
            except ValueError as err:
                if "API key" in str(err):
                    errors["base"] = "invalid_auth"
                elif "connect" in str(err):
                    errors["base"] = "cannot_connect"
                else:
                    errors["base"] = "unknown"
                _LOGGER.exception("Unexpected exception: %s", err)
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception: %s", err)
                errors["base"] = "unknown"

        # Show the form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_URL, default="http://192.168.1.94:8000"): str,
                    vol.Optional(CONF_API_KEY): str,
                }
            ),
            errors=errors,
        )