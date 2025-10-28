"""Sensor platform for Plex Recommendations."""
import logging
from typing import Any

import aiohttp
import async_timeout

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    ENDPOINT_RECOMMENDATIONS,
    ENDPOINT_RECENT,
    ATTR_USER_ID,
    ATTR_GENERATED_AT,
    ATTR_RECOMMENDATIONS,
    ATTR_RECENT,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Plex Recommendations sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Create sensors for each user
    entities = []
    if coordinator.data and "users" in coordinator.data:
        for user in coordinator.data["users"]:
            user_id = user.get("id")
            user_name = user.get("name", user_id)
            
            # Recommendations sensor
            entities.append(
                PlexRecommendationsSensor(
                    coordinator, user_id, user_name, "recommendations"
                )
            )
            
            # Recent sensor
            entities.append(
                PlexRecommendationsSensor(
                    coordinator, user_id, user_name, "recent"
                )
            )
    
    async_add_entities(entities)


class PlexRecommendationsSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Plex Recommendations sensor."""

    def __init__(self, coordinator, user_id: str, user_name: str, sensor_type: str):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._user_id = user_id
        self._user_name = user_name
        self._sensor_type = sensor_type
        self._attr_name = f"Plex {sensor_type.title()} {user_name}"
        self._attr_unique_id = f"plex_{sensor_type}_{user_id}"
        self._data = {}

    @property
    def state(self) -> int:
        """Return the state of the sensor."""
        if self._sensor_type == "recommendations":
            return len(self._data.get(ATTR_RECOMMENDATIONS, []))
        return len(self._data.get(ATTR_RECENT, []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            ATTR_USER_ID: self._user_id,
            **self._data
        }

    async def async_update(self) -> None:
        """Update the sensor."""
        api_url = self.coordinator.api_url
        headers = {}
        if self.coordinator.api_key:
            headers["X-API-Key"] = self.coordinator.api_key

        endpoint = (
            ENDPOINT_RECOMMENDATIONS if self._sensor_type == "recommendations"
            else ENDPOINT_RECENT
        )
        endpoint = endpoint.format(user_id=self._user_id)

        try:
            async with async_timeout.timeout(10):
                async with self.coordinator.session.get(
                    f"{api_url}{endpoint}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        self._data = await response.json()
                    else:
                        _LOGGER.warning(
                            "Error fetching %s for %s: %s",
                            self._sensor_type,
                            self._user_id,
                            response.status
                        )
        except aiohttp.ClientError as err:
            _LOGGER.error("Error updating sensor: %s", err)
