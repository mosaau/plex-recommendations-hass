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

    def _handle_coordinator_update(self) -> None:
        """Called whenever the coordinator refreshes."""
        # Refresh this sensor's per-user data when the user list updates
        self.hass.async_create_task(self._fetch_data())
        super()._handle_coordinator_update()

    async def _fetch_data(self) -> None:
        """Fetch per-user data for this sensor and update state."""
        api_url = self.coordinator.api_url
        headers = {}
        if self.coordinator.api_key:
            headers["X-API-Key"] = self.coordinator.api_key

        endpoint = (
            ENDPOINT_RECOMMENDATIONS if self._sensor_type == "recommendations"
            else ENDPOINT_RECENT
        ).format(user_id=self._user_id)

        try:
            async with async_timeout.timeout(10):
                async with self.coordinator.session.get(
                    f"{api_url}{endpoint}", headers=headers
                ) as response:
                    if response.status != 200:
                        _LOGGER.warning(
                            "Error fetching %s for %s: %s",
                            self._sensor_type, self._user_id, response.status
                        )
                        return

                    ctype = response.headers.get("Content-Type", "")

                    # Handle JSON response
                    if "application/json" in ctype:
                        payload = await response.json()
                    else:
                        # Handle other formats (YAML, plain text)
                        raw_text = await response.text()
                        payload = None
                        try:
                            import yaml
                            payload = yaml.safe_load(raw_text)
                        except Exception:
                            payload = None

                        # Fallback: treat as newline list
                        if payload is None:
                            lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
                            payload = lines

                    # Normalize into expected structure
                    if isinstance(payload, dict):
                        data_dict = payload
                    elif isinstance(payload, list):
                        key = ATTR_RECOMMENDATIONS if self._sensor_type == "recommendations" else ATTR_RECENT
                        data_dict = {key: payload}
                    else:
                        key = ATTR_RECOMMENDATIONS if self._sensor_type == "recommendations" else ATTR_RECENT
                        data_dict = {key: [str(payload)]}

                    self._data = data_dict

        except aiohttp.ClientError as err:
            _LOGGER.error("Error updating sensor: %s", err)
        except Exception as err:
            _LOGGER.error("Unexpected error updating sensor: %s", err)

        # Write state after any attempt
        self.async_write_ha_state()