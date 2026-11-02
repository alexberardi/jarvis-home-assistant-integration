"""Home Assistant device manager — lists devices from a Home Assistant instance.

Wraps HomeAssistantService.get_context_data() and maps each HA entity
to a normalized DeviceManagerDevice.
"""

try:
    from jarvis_log_client import JarvisLogger
except ImportError:
    import logging
    class JarvisLogger:  # noqa: E303
        def __init__(self, **kw: str) -> None:
            self._log = logging.getLogger(kw.get("service", __name__))
        def info(self, msg: str, **kw: object) -> None: self._log.info(msg)
        def warning(self, msg: str, **kw: object) -> None: self._log.warning(msg)
        def error(self, msg: str, **kw: object) -> None: self._log.error(msg)
        def debug(self, msg: str, **kw: object) -> None: self._log.debug(msg)

from jarvis_command_sdk import (
    AuthenticationConfig,
    DeviceControlResult,
    DeviceManagerDevice,
    IJarvisDeviceManager,
    IJarvisSecret,
    JarvisSecret,
)

logger = JarvisLogger(service="jarvis-node")


class HomeAssistantDeviceManager(IJarvisDeviceManager):
    """Lists devices from a Home Assistant instance via WebSocket API."""

    @property
    def name(self) -> str:
        return "home_assistant"

    @property
    def friendly_name(self) -> str:
        return "Home Assistant"

    @property
    def description(self) -> str:
        return "Devices managed by your Home Assistant instance"

    @property
    def can_edit_devices(self) -> bool:
        return False

    @property
    def required_secrets(self) -> list[IJarvisSecret]:
        return [
            JarvisSecret(
                "HOME_ASSISTANT_REST_URL",
                "Home Assistant REST API URL (e.g., http://192.168.1.100:8123)",
                "integration",
                "string",
                is_sensitive=False,
                friendly_name="REST URL",
            ),
            JarvisSecret(
                "HOME_ASSISTANT_API_KEY",
                "Home Assistant long-lived access token",
                "integration",
                "string",
                friendly_name="API Key",
            ),
        ]

    @property
    def authentication(self) -> AuthenticationConfig:
        return AuthenticationConfig(
            type="oauth",
            provider="home_assistant",
            friendly_name="Home Assistant",
            client_id="http://jarvis-node-mobile",
            keys=["access_token"],
            authorize_path="/auth/authorize",
            exchange_path="/auth/token",
            discovery_port=8123,
            discovery_probe_path="/api/",
            send_redirect_uri_in_exchange=False,
        )

    async def collect_devices(self) -> list[DeviceManagerDevice]:
        """Fetch devices from HA via WebSocket and map to DeviceManagerDevice."""
        from ha_shared.catalogue import catalogue_domain
        from ha_shared.home_assistant_service import HomeAssistantService

        service = HomeAssistantService()
        try:
            await service.refresh_if_stale(max_age_seconds=0)
        except Exception as e:
            logger.error("Failed to connect to Home Assistant", error=str(e))
            raise

        context = service.get_context_data()
        devices: list[DeviceManagerDevice] = []

        for ha_device in context.get("devices", []):
            area_name: str | None = ha_device.get("area")
            manufacturer: str | None = ha_device.get("manufacturer")
            model: str | None = ha_device.get("model")
            device_name: str = ha_device.get("name") or "Unknown"

            for entity in ha_device.get("entities", []):
                entity_id: str = entity.get("entity_id", "")
                if not entity_id:
                    continue

                domain = catalogue_domain(entity_id)

                devices.append(DeviceManagerDevice(
                    name=entity.get("name") or device_name,
                    domain=domain,
                    entity_id=entity_id,
                    is_controllable=True,
                    manufacturer=manufacturer,
                    model=model,
                    protocol="home_assistant",
                    source="home_assistant",
                    area=area_name,
                    state=entity.get("state"),
                ))

        logger.info("Home Assistant device list complete", device_count=len(devices))
        return devices

    async def get_state(self, device: DeviceManagerDevice) -> dict | None:
        """The entity's state in catalogue fields (ha_shared.catalogue.to_state)."""
        from ha_shared.catalogue import to_state
        from ha_shared.home_assistant_service import HomeAssistantService

        service = HomeAssistantService()
        result = await service.get_state(device.entity_id)
        if not result.success:
            return {"state": "unknown", "error": result.error}
        state = to_state(device.entity_id, result.state, result.attributes or {})
        if device.domain == "climate":
            unit = await service.temperature_unit()
            if unit:
                state["unit"] = unit
        return state

    async def control(self, device: DeviceManagerDevice, action: str, data: dict | None = None) -> DeviceControlResult:
        """Run a catalogue action as the matching HA service call."""
        from ha_shared.catalogue import allowed_actions, catalogue_domain, to_service
        from ha_shared.home_assistant_service import HomeAssistantService
        from jarvis_command_sdk import device_type

        domain = catalogue_domain(device.entity_id)
        if action not in allowed_actions(domain, device_type(domain)):
            return DeviceControlResult(False, device.entity_id, action, error=f"Unsupported action {action!r} for {domain}")
        if action in device_type(domain)["features"] and domain in ("media_player", "security_system"):
            state = await self.get_state(device)
            if action not in (state or {}).get("available_features", [action]):
                return DeviceControlResult(False, device.entity_id, action, error=f"{device.name} doesn't support {action}")
        try:
            service_domain, service, payload = to_service(device.entity_id, action, data)
        except (KeyError, TypeError, ValueError) as e:
            return DeviceControlResult(False, device.entity_id, action, error=f"Invalid data for {action}: {e}")
        result = await HomeAssistantService().call_service(service_domain, service, device.entity_id, payload)
        return DeviceControlResult(result.success, device.entity_id, action, error=result.error)
