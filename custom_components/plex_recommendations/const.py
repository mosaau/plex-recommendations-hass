"""Constants for Plex Recommendations integration."""

DOMAIN = "plex_recommendations"
CONF_API_URL = "api_url"
CONF_API_KEY = "api_key"

# Default values
DEFAULT_SCAN_INTERVAL = 3600  # 1 hour in seconds
DEFAULT_NAME = "Plex Recommendations"

# API endpoints
ENDPOINT_USERS = "/api/users"
ENDPOINT_RECOMMENDATIONS = "/api/recommendations/{user_id}"
ENDPOINT_RECENT = "/api/recent/{user_id}"
ENDPOINT_HEALTH = "/health"

# Sensor attributes
ATTR_USER_ID = "user_id"
ATTR_GENERATED_AT = "generated_at"
ATTR_RECOMMENDATIONS = "recommendations"
ATTR_RECENT = "recent"