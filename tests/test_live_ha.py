"""Against a real Home Assistant: HOME_ASSISTANT_REST_URL and HOME_ASSISTANT_API_KEY set, else skipped.

Point it at a throwaway HA with the demo integration; the control tests drive demo entities.
"""
import asyncio
import os

import httpx
import pytest
from jarvis_command_sdk import DeviceManagerDevice, device_type

pytestmark = pytest.mark.skipif(not os.environ.get("HOME_ASSISTANT_API_KEY"), reason="no live Home Assistant")
EXTRA_FIELDS = {"available_features", "online", "error"}


def _manager():
    from device_managers.home_assistant.manager import HomeAssistantDeviceManager
    return HomeAssistantDeviceManager()


def _device(entity_id):
    from ha_shared.catalogue import catalogue_domain
    return DeviceManagerDevice(name=entity_id, domain=catalogue_domain(entity_id), entity_id=entity_id,
                               source="home_assistant")


def _entities():
    r = httpx.get(os.environ["HOME_ASSISTANT_REST_URL"] + "/api/states",
                  headers={"Authorization": "Bearer " + os.environ["HOME_ASSISTANT_API_KEY"]}, timeout=10)
    return [e["entity_id"] for e in r.json()]


def test_every_entity_maps_into_catalogue_fields():
    mgr = _manager()
    for entity_id in _entities():
        dev = _device(entity_id)
        t = device_type(dev.domain)
        state = asyncio.run(mgr.get_state(dev))
        assert set(state) <= set(t["state_fields"]) | EXTRA_FIELDS, entity_id
        assert set(state.get("available_features", [])) <= set(t["features"]), entity_id


def _demo(entity_id):
    if entity_id not in _entities():
        pytest.skip(f"{entity_id} not on this HA (not the demo integration)")
    return _device(entity_id)


def test_media_pause_play_and_seek_follow_the_destination():
    mgr, dev = _manager(), _demo("media_player.walkman")
    assert asyncio.run(mgr.control(dev, "pause")).success
    assert asyncio.run(mgr.get_state(dev))["state"] == "paused"
    assert asyncio.run(mgr.control(dev, "play")).success
    assert asyncio.run(mgr.get_state(dev))["state"] == "playing"
    assert "seek" not in asyncio.run(mgr.get_state(dev))["available_features"]
    refused = asyncio.run(mgr.control(dev, "seek", {"seconds": 42}))
    assert not refused.success and "doesn't support seek" in refused.error
    # The demo YouTube player advertises seek but doesn't implement it; volume is a supported pass-through.
    tv = _demo("media_player.living_room")
    assert asyncio.run(mgr.control(tv, "volume", {"volume": 30})).success
    assert asyncio.run(mgr.get_state(tv))["volume"] == 30


def test_unsupported_and_unknown_actions_fail_cleanly():
    mgr = _manager()
    assert not asyncio.run(mgr.control(_demo("media_player.walkman"), "explode")).success
    assert not asyncio.run(mgr.control(_demo("media_player.walkman"), "play_media", {})).success


def test_thermostat_mode():
    mgr, dev = _manager(), _demo("climate.hvac")
    before = asyncio.run(mgr.get_state(dev))["mode"]
    assert asyncio.run(mgr.control(dev, "set_mode", {"mode": "heat"})).success
    assert asyncio.run(mgr.get_state(dev))["mode"] == "heat"
    asyncio.run(mgr.control(dev, "set_mode", {"mode": before}))
