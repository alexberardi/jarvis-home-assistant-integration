"""Home Assistant ↔ the SDK device-type catalogue (jarvis_command_sdk device_types.json).

HA's entity domains, attributes, supported_features bitmasks and service names stay in
this module. The manager hands Jarvis catalogue-shaped state and accepts catalogue
action names, so displays and apps never see HA's vocabulary.
"""

from typing import Any, Dict, List, Optional, Tuple

# HA domain → catalogue domain where the names differ.
DOMAIN_ALIASES: Dict[str, str] = {"alarm_control_panel": "security_system"}

# MediaPlayerEntityFeature bits → catalogue media features.
MEDIA_FEATURE_BITS: Dict[str, int] = {
    "pause": 1, "seek": 2, "volume": 4, "turn_on": 128, "turn_off": 256,
    "play_media": 512, "stop": 4096, "play": 16384,
}

_COLOR_MODES = {"hs", "xy", "rgb", "rgbw", "rgbww"}
_ALARM_STATES = {"armed_away": "away", "armed_home": "home", "disarmed": "off"}
_ALARM_SERVICES = {"away": "alarm_arm_away", "home": "alarm_arm_home", "off": "alarm_disarm"}

# (catalogue domain, catalogue action) → HA service, when they differ.
_SERVICES: Dict[Tuple[str, str], str] = {
    ("media_player", "play"): "media_play",
    ("media_player", "pause"): "media_pause",
    ("media_player", "stop"): "media_stop",
    ("media_player", "seek"): "media_seek",
    ("media_player", "volume"): "volume_set",
    ("climate", "set_mode"): "set_hvac_mode",
    ("cover", "set_position"): "set_cover_position",
    ("light", "set_brightness"): "turn_on",
    ("light", "set_color"): "turn_on",
}


def catalogue_domain(entity_id: str) -> str:
    """The catalogue domain for an HA entity id."""
    ha_domain = entity_id.split(".", 1)[0] if "." in entity_id else "unknown"
    return DOMAIN_ALIASES.get(ha_domain, ha_domain)


def _num(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_state(entity_id: str, state: Optional[str], attrs: Dict[str, Any]) -> Dict[str, Any]:
    """An HA state + attributes as catalogue state fields for the entity's domain."""
    domain = catalogue_domain(entity_id)
    out: Dict[str, Any] = {"state": (state or "unknown").lower()}
    if out["state"] == "unavailable":
        out["online"] = False

    if domain == "light":
        modes = set(attrs.get("supported_color_modes") or [])
        out["available_features"] = [f for f, ok in (
            ("brightness", bool(modes - {"onoff"})),
            ("color", bool(modes & _COLOR_MODES)),
            ("color_temp", "color_temp" in modes),
        ) if ok]
        if attrs.get("brightness") is not None:
            out["brightness"] = round(float(attrs["brightness"]) / 255 * 100)
        if attrs.get("rgb_color"):
            out["rgb"] = [int(c) for c in attrs["rgb_color"]]
        if attrs.get("hs_color"):
            out["hue"], out["saturation"] = (round(float(v)) for v in attrs["hs_color"])
        if attrs.get("color_temp_kelvin") is not None:
            out["color_temp"] = int(attrs["color_temp_kelvin"])
    elif domain == "climate":
        out["state"] = str(attrs.get("hvac_action") or state or "unknown").lower()
        out["mode"] = (state or "off").lower()
        out["available_features"] = [str(m) for m in attrs.get("hvac_modes") or []]
        for ours, theirs in (("current_temperature", "current_temperature"), ("target_temperature", "temperature"),
                             ("humidity", "current_humidity")):
            if _num(attrs.get(theirs)) is not None:
                out[ours] = round(float(attrs[theirs]))
    elif domain == "cover":
        if _num(attrs.get("current_position")) is not None:
            out["position"] = round(float(attrs["current_position"]))
    elif domain == "lock":
        out["is_locked"] = out["state"] == "locked"
    elif domain == "security_system":
        out["state"] = _ALARM_STATES.get(out["state"], out["state"])
    elif domain == "media_player":
        bits = int(attrs.get("supported_features") or 0)
        out["available_features"] = [f for f, bit in MEDIA_FEATURE_BITS.items() if bits & bit]
        if _num(attrs.get("volume_level")) is not None:
            out["volume"] = round(float(attrs["volume_level"]) * 100)
        for ours, theirs in (("position", "media_position"), ("duration", "media_duration")):
            if _num(attrs.get(theirs)) is not None:
                out[ours] = float(attrs[theirs])
        for key in ("media_title", "media_artist", "source"):
            if attrs.get(key):
                out[key] = attrs[key]
    return out


def to_service(entity_id: str, action: str, data: Optional[Dict[str, Any]]) -> Tuple[str, str, Dict[str, Any]]:
    """A catalogue action on an HA entity as (HA service domain, service, service data)."""
    ha_domain = entity_id.split(".", 1)[0]
    domain = catalogue_domain(entity_id)
    data = data or {}
    if domain == "security_system":
        if action not in _ALARM_SERVICES:
            raise ValueError(f"Unsupported action {action!r} for {domain}")
        return ha_domain, _ALARM_SERVICES[action], {}
    service = _SERVICES.get((domain, action), action)
    payload: Dict[str, Any] = {}
    if domain == "media_player":
        if action == "play_media":
            payload = {"media_content_id": data["url"], "media_content_type": data.get("content_type", "video")}
        elif action == "seek":
            payload = {"seek_position": float(data["seconds"])}
        elif action == "volume":
            payload = {"volume_level": float(data["volume"]) / 100}
    elif domain == "climate":
        if action == "set_mode":
            payload = {"hvac_mode": data["mode"]}
        elif action == "set_temperature":
            payload = {"temperature": data["temperature"]}
    elif domain == "cover" and action == "set_position":
        payload = {"position": int(data["position"])}
    elif domain == "light":
        if "brightness" in data:
            payload["brightness_pct"] = int(data["brightness"])
        if "rgb" in data:
            payload["rgb_color"] = list(data["rgb"])
        if "color_temp" in data:
            payload["color_temp_kelvin"] = int(data["color_temp"])
    return ha_domain, service, payload


def allowed_actions(domain: str, catalogue_type: Dict[str, Any]) -> List[str]:
    """Catalogue actions a device of this type accepts: its buttons, plus features that are actions."""
    extra = {"light": ["set_brightness", "set_color"], "cover": ["set_position"]}.get(domain, [])
    if domain in ("media_player", "security_system"):  # elsewhere features are modes, not actions
        extra = list(catalogue_type["features"])
    return [a["action"] for a in catalogue_type["actions"]] + extra
