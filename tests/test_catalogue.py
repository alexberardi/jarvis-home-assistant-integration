import pytest
from jarvis_command_sdk import device_type

from ha_shared.catalogue import allowed_actions, catalogue_domain, to_service, to_state


def test_alarm_panel_is_a_security_system():
    assert catalogue_domain("alarm_control_panel.home") == "security_system"
    assert to_state("alarm_control_panel.home", "armed_away", {})["state"] == "away"
    assert to_service("alarm_control_panel.home", "off", None) == ("alarm_control_panel", "alarm_disarm", {})


def test_media_features_come_from_the_bitmask():
    # PAUSE | SEEK | PLAY_MEDIA | STOP | PLAY
    state = to_state("media_player.tv", "playing", {"supported_features": 1 | 2 | 512 | 4096 | 16384,
                                                    "media_position": 12.5, "media_duration": 300, "volume_level": 0.4})
    assert state["available_features"] == ["pause", "seek", "play_media", "stop", "play"]
    assert (state["position"], state["duration"], state["volume"]) == (12.5, 300.0, 40)


def test_media_actions_map_to_ha_services():
    assert to_service("media_player.tv", "play", None) == ("media_player", "media_play", {})
    assert to_service("media_player.tv", "seek", {"seconds": 30}) == ("media_player", "media_seek", {"seek_position": 30.0})
    assert to_service("media_player.tv", "play_media", {"url": "http://x/v.mp4"}) == (
        "media_player", "play_media", {"media_content_id": "http://x/v.mp4", "media_content_type": "video"})
    with pytest.raises(KeyError):
        to_service("media_player.tv", "play_media", {})


def test_light_and_climate_translate_units_and_names():
    light = to_state("light.desk", "on", {"brightness": 255, "supported_color_modes": ["color_temp", "hs"],
                                          "color_temp_kelvin": 3000})
    assert light["brightness"] == 100 and light["color_temp"] == 3000
    assert light["available_features"] == ["brightness", "color", "color_temp"]
    assert to_state("light.plug", "off", {"supported_color_modes": ["onoff"]})["available_features"] == []
    assert to_service("light.desk", "set_brightness", {"brightness": 40}) == ("light", "turn_on", {"brightness_pct": 40})
    climate = to_state("climate.hall", "heat", {"hvac_action": "idle", "temperature": 70, "hvac_modes": ["heat", "off"]})
    assert (climate["state"], climate["mode"], climate["target_temperature"]) == ("idle", "heat", 70)
    assert to_service("climate.hall", "set_mode", {"mode": "cool"}) == ("climate", "set_hvac_mode", {"hvac_mode": "cool"})


def test_only_real_actions_are_allowed():
    assert "pause" in allowed_actions("media_player", device_type("media_player"))
    assert "heat" not in allowed_actions("climate", device_type("climate"))  # a mode, not a service
    assert "away" in allowed_actions("security_system", device_type("security_system"))
    assert allowed_actions("todo", device_type("todo")) == []


def test_unavailable_is_offline():
    assert to_state("light.gone", "unavailable", {}) == {"state": "unavailable", "online": False, "available_features": []}
