# Home Assistant Integration for Jarvis

Full Home Assistant integration — voice-controlled device management with background state caching.

## Components

| Type | Name | Description |
|------|------|-------------|
| Command | `control_device` | "Turn off the lights", "Lock the front door", "Set thermostat to 72" |
| Command | `get_device_status` | "Is the garage door open?", "What's the temperature?" |
| Agent | `home_assistant` | Background agent that caches HA entity states for fast voice responses |
| Device Manager | `home_assistant` | Collects devices from HA for the device registry |

## Install

```bash
jarvis pantry install --url https://github.com/alexberardi/jarvis-home-assistant-integration
```

Or from a local checkout:

```bash
jarvis pantry install --local /path/to/jarvis-home-assistant-integration
```

## Secrets

| Key | Description |
|-----|-------------|
| `HA_URL` | Home Assistant URL (e.g., `http://homeassistant.local:8123`) |
| `HA_TOKEN` | Long-lived access token from HA |

## Structure

```
jarvis_package.yaml
ha_shared/
  home_assistant_service.py    # HA WebSocket + REST client
  entity_resolver.py           # Fuzzy entity ID matching
commands/
  control_device/command.py    # IJarvisCommand — device control
  get_device_status/command.py # IJarvisCommand — device status
agents/
  home_assistant/agent.py      # IJarvisAgent — background state cache
device_managers/
  home_assistant/manager.py    # IJarvisDeviceManager — device listing
```

## License

MIT
