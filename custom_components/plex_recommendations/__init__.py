"""The Plex Recommendations integration."""
import logging
from datetime import timedelta
from homeassistant.const import Platform

import aiohttp
import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import const

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Plex Recommendations from a config entry."""
    api_url = entry.data[const.CONF_API_URL].rstrip('/')
    api_key = entry.data.get(const.CONF_API_KEY)
    
    coordinator = PlexRecommendationsDataUpdateCoordinator(
        hass, api_url, api_key
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(const.DOMAIN, {})
    hass.data[const.DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[const.DOMAIN].pop(entry.entry_id)

    return unload_ok


class PlexRecommendationsDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Plex Recommendations data."""

    def __init__(self, hass: HomeAssistant, api_url: str, api_key: str | None):
        """Initialize."""
        self.api_url = api_url
        self.api_key = api_key
        self.session = async_get_clientsession(hass)

        super().__init__(
            hass,
            _LOGGER,
            name=const.DOMAIN,
            update_interval=timedelta(seconds=const.DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self):
        """Fetch data from API."""
        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        try:
            async with async_timeout.timeout(10):
                # Fetch list of users
                async with self.session.get(
                    f"{self.api_url}{const.ENDPOINT_USERS}",
                    headers=headers
                ) as response:
                    if response.status != 200:
                        raise UpdateFailed(f"Error fetching users: {response.status}")
                    users = await response.json()

            return {"users": users}

        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err