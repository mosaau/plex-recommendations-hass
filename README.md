# Plex Recommendations - Home Assistant Integration

Custom Home Assistant integration for the Plex Recommendations Engine.

## Features

- 🎬 Auto-discovers all Plex users
- 📊 Creates sensors for recommendations and recently watched content
- 🔄 Updates hourly automatically
- 🔐 Supports API key authentication
- 🎨 Easy dashboard card creation

## Installation

### Via HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/YOUR_USERNAME/plex-recommendations-hass`
6. Category: Integration
7. Click "Add"
8. Click "Install" on the Plex Recommendations card
9. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/plex_recommendations` folder to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to Settings → Devices & Services
2. Click "+ Add Integration"
3. Search for "Plex Recommendations"
4. Enter your API URL (e.g., `http://192.168.1.94:8000`)
5. Enter your API key (optional but recommended)
6. Click Submit

## Sensors Created

For each user, two sensors are created:

- `sensor.plex_recommendations_[username]` - Current recommendations
- `sensor.plex_recent_[username]` - Recently watched content

## Dashboard Example
```yaml
type: grid
columns: 4
cards:
  - type: picture
    image: "{{ state_attr('sensor.plex_recommendations_daniel', 'recommendations')[0].poster_url }}"
    tap_action:
      action: call-service
      service: script.play_on_apple_tv
      data:
        device: media_player.living_room_apple_tv
        plex_rating_key: "{{ state_attr('sensor.plex_recommendations_daniel', 'recommendations')[0].plex_rating_key }}"
```

## Requirements

- Home Assistant 2023.1 or newer
- Plex Recommendations Engine running and accessible
- API key configured (recommended)

## Support

For issues and feature requests, please open an issue on GitHub.