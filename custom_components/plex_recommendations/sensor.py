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
        _LOGGER.info("Found %d users in coordinator data", len(coordinator.data["users"]))
        for user in coordinator.data["users"]:
            user_id = user.get("id")
            user_name = user.get("name", user_id)
            
            _LOGGER.info("Creating sensors for user: %s (ID: %s)", user_name, user_id)
            
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
    else:
        _LOGGER.warning("No users found in coordinator data: %s", coordinator.data)
    
    async_add_entities(entities, update_before_add=True)


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
        
        _LOGGER.info(
            "Initialized sensor: %s (ID: %s, Type: %s)",
            self._attr_name,
            self._attr_unique_id,
            sensor_type
        )

    @property
    def state(self) -> int:
        """Return the state of the sensor."""
        if self._sensor_type == "recommendations":
            count = len(self._data.get(ATTR_RECOMMENDATIONS, []))
        else:
            count = len(self._data.get(ATTR_RECENT, []))
        
        _LOGGER.debug("Sensor %s state: %d items", self._attr_name, count)
        return count

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        attrs = {
            ATTR_USER_ID: self._user_id,
            **self._data
        }
        _LOGGER.debug("Sensor %s attributes keys: %s", self._attr_name, list(attrs.keys()))
        return attrs

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Sensor is available even if API returns an error (we'll show 0 items)
        return True

    def _handle_coordinator_update(self) -> None:
        """Called whenever the coordinator refreshes."""
        _LOGGER.debug("Coordinator update triggered for %s", self._attr_name)
        # Refresh this sensor's per-user data when the user list updates
        self.hass.async_create_task(self._fetch_data())
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Fetch data immediately when sensor is added
        _LOGGER.info("Sensor %s added to hass, fetching initial data", self._attr_name)
        await self._fetch_data()

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

        url = f"{api_url}{endpoint}"
        _LOGGER.info("Fetching data for %s from %s", self._attr_name, url)

        try:
            async with async_timeout.timeout(10):
                async with self.coordinator.session.get(url, headers=headers) as response:
                    _LOGGER.debug("Response status for %s: %d", self._attr_name, response.status)
                    
                    if response.status == 200:
                        ctype = response.headers.get("Content-Type", "")
                        _LOGGER.debug("Content-Type: %s", ctype)

                        # Handle JSON response
                        if "application/json" in ctype:
                            payload = await response.json()
                            _LOGGER.info(
                                "Received JSON data for %s: %d items",
                                self._attr_name,
                                len(payload.get(ATTR_RECOMMENDATIONS if self._sensor_type == "recommendations" else ATTR_RECENT, []))
                            )
                        else:
                            # Handle other formats
                            raw_text = await response.text()
                            _LOGGER.debug("Received non-JSON response: %s", raw_text[:200])
                            payload = None
                            try:
                                import yaml
                                payload = yaml.safe_load(raw_text)
                            except Exception:
                                payload = None

                            if payload is None:
                                lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
                                payload = lines

                        # Normalize into expected structure
                        if isinstance(payload, dict):
                            self._data = payload
                        elif isinstance(payload, list):
                            key = ATTR_RECOMMENDATIONS if self._sensor_type == "recommendations" else ATTR_RECENT
                            self._data = {key: payload}
                        else:
                            key = ATTR_RECOMMENDATIONS if self._sensor_type == "recommendations" else ATTR_RECENT
                            self._data = {key: [str(payload)]}
                        
                        _LOGGER.info("Data successfully stored for %s", self._attr_name)
                    
                    elif response.status == 404:
                        _LOGGER.warning("Endpoint not found for %s: %s", self._attr_name, url)
                        self._data = {
                            "error": "Endpoint not found",
                            ATTR_RECOMMENDATIONS if self._sensor_type == "recommendations" else ATTR_RECENT: []
                        }
                    
                    else:
                        # Try to get error message from response
                        try:
                            error_data = await response.json()
                            error_msg = error_data.get("detail", f"HTTP {response.status}")
                        except:
                            error_msg = f"HTTP {response.status}"
                        
                        _LOGGER.warning(
                            "Error fetching %s for %s: %s",
                            self._sensor_type,
                            self._user_id,
                            error_msg
                        )
                        
                        # Store error in data so user can see it
                        self._data = {
                            "error": error_msg,
                            ATTR_RECOMMENDATIONS if self._sensor_type == "recommendations" else ATTR_RECENT: []
                        }

        except aiohttp.ClientError as err:
            _LOGGER.error("Network error updating sensor %s: %s", self._attr_name, err)
            self._data = {
                "error": f"Network error: {str(err)}",
                ATTR_RECOMMENDATIONS if self._sensor_type == "recommendations" else ATTR_RECENT: []
            }
        except Exception as err:
            _LOGGER.error("Unexpected error updating sensor %s: %s", self._attr_name, err, exc_info=True)
            self._data = {
                "error": f"Unexpected error: {str(err)}",
                ATTR_RECOMMENDATIONS if self._sensor_type == "recommendations" else ATTR_RECENT: []
            }

        # Write state after any attempt
        self.async_write_ha_state()
        _LOGGER.debug("State written for %s", self._attr_name)