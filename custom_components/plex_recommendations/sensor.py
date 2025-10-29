"""Sensor platform for Plex Recommendations."""
import asyncio
import logging
import random
import traceback
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

    @property
    def state(self) -> int:
        """Return the state of the sensor."""
        if self._sensor_type == "recommendations":
            return len(self._data.get(ATTR_RECOMMENDATIONS, []))
        return len(self._data.get(ATTR_RECENT, []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes with improved formatting."""
        try:
            attrs = {
                ATTR_USER_ID: self._user_id,
            }

            # Add generated_at if available
            if ATTR_GENERATED_AT in self._data:
                attrs[ATTR_GENERATED_AT] = self._data[ATTR_GENERATED_AT]

            # Add the full data list
            key = ATTR_RECOMMENDATIONS if self._sensor_type == "recommendations" else ATTR_RECENT
            items = self._data.get(key, [])
            attrs[key] = items

            # Add convenient summary attributes for easy display
            if items:
                # Create a simple list of titles for quick viewing
                attrs["titles"] = [item.get("title", "Unknown") for item in items[:10]]

                # Add first 3 items as separate attributes for easy card access
                for i, item in enumerate(items[:3], 1):
                    try:
                        prefix = f"item_{i}_"
                        attrs[f"{prefix}title"] = item.get("title")
                        attrs[f"{prefix}year"] = item.get("year")
                        attrs[f"{prefix}type"] = item.get("type")
                        attrs[f"{prefix}poster"] = item.get("poster_url")
                        attrs[f"{prefix}deep_link"] = item.get("deep_link")
                        attrs[f"{prefix}rating_key"] = item.get("plex_rating_key")
                        if "reason" in item:
                            attrs[f"{prefix}reason"] = item.get("reason")
                        if "score" in item:
                            attrs[f"{prefix}score"] = round(item.get("score", 0), 2)
                        # Add percent_complete for recent watches (resume functionality)
                        if "percent_complete" in item:
                            attrs[f"{prefix}percent_complete"] = item.get("percent_complete")
                    except Exception as item_err:
                        _LOGGER.warning("Error processing item %d for %s: %s", i, self._attr_name, item_err)
                        _LOGGER.debug("Problematic item data: %s", item)

            # Add error if present
            if "error" in self._data:
                attrs["error"] = self._data["error"]

            return attrs

        except Exception as err:
            _LOGGER.error("Error building attributes for %s: %s", self._attr_name, err)
            _LOGGER.error("Full traceback: %s", traceback.format_exc())
            _LOGGER.debug("Sensor data: %s", self._data)
            return {
                ATTR_USER_ID: self._user_id,
                "error": f"Error building attributes: {str(err)}"
            }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return True

    def _handle_coordinator_update(self) -> None:
        """Called whenever the coordinator refreshes."""
        self.hass.async_create_task(self._fetch_data())
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()

        # Stagger initial fetches to avoid overwhelming the API
        # Random delay between 0-5 seconds per sensor
        delay = random.uniform(0, 5)
        _LOGGER.debug("Sensor %s waiting %.1f seconds before initial fetch", self._attr_name, delay)
        await asyncio.sleep(delay)

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

        try:
            async with async_timeout.timeout(60):  # 60s timeout for initial Plex On Deck query (cached after first request)
                async with self.coordinator.session.get(url, headers=headers) as response:
                    if response.status == 200:
                        self._data = await response.json()
                    elif response.status == 404:
                        self._data = {
                            "error": "Endpoint not found",
                            ATTR_RECOMMENDATIONS if self._sensor_type == "recommendations" else ATTR_RECENT: []
                        }
                    else:
                        try:
                            error_data = await response.json()
                            error_msg = error_data.get("detail", f"HTTP {response.status}")
                        except:
                            error_msg = f"HTTP {response.status}"
                        
                        self._data = {
                            "error": error_msg,
                            ATTR_RECOMMENDATIONS if self._sensor_type == "recommendations" else ATTR_RECENT: []
                        }

        except aiohttp.ClientError as err:
            _LOGGER.error("Network error updating sensor %s: %s", self._attr_name, err)
            _LOGGER.error("Full traceback: %s", traceback.format_exc())
            self._data = {
                "error": f"Network error: {str(err)}",
                ATTR_RECOMMENDATIONS if self._sensor_type == "recommendations" else ATTR_RECENT: []
            }
        except Exception as err:
            _LOGGER.error("Unexpected error updating sensor %s: %s", self._attr_name, err)
            _LOGGER.error("Full traceback: %s", traceback.format_exc())
            self._data = {
                "error": f"Unexpected error: {str(err)}",
                ATTR_RECOMMENDATIONS if self._sensor_type == "recommendations" else ATTR_RECENT: []
            }

        self.async_write_ha_state()