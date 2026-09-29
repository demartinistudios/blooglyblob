"""Roku device controller using External Control Protocol (ECP)."""

from typing import Any

import logging
import time

import requests
from roku import Roku

logger = logging.getLogger(__name__)

# Map common service names to Roku app display names
SERVICE_TO_APP_NAME = {
    "netflix": "Netflix",
    "disney+": "Disney Plus",
    "apple_tv": "Apple TV",
    "hulu": "Hulu",
    "youtube": "YouTube",
    "amazon": "Prime Video",
    "hbo_max": "Max",
    "max": "Max",
    "peacock": "Peacock TV",
    "paramount+": "Paramount+",
}


class _BoundedRoku(Roku):
    """Bound SDK requests so an offline TV cannot hold up the backend."""

    def _call(self, method, path, *args, **kwargs):
        kwargs["timeout"] = 5.0
        return super()._call(method, path, *args, **kwargs)


class RokuController:
    """Controller for Roku devices via ECP (External Control Protocol)."""

    def __init__(self, roku_ip: str):
        """Initialize with Roku IP address.

        Args:
            roku_ip: IP address of the Roku device
        """
        self.roku_ip = roku_ip
        self.roku = _BoundedRoku(roku_ip)
        self.channel_ids: dict[str, object] = {}
        self._build_channel_ids()

    def _build_channel_ids(self) -> None:
        """Query installed apps and build channel_ids mapping."""
        try:
            apps = self.roku.apps
            for app in apps:
                # Store app object keyed by lowercase service name
                app_name_lower = app.name.lower()
                self.channel_ids[app_name_lower] = app

                # Also map service aliases to apps
                for service, app_display_name in SERVICE_TO_APP_NAME.items():
                    if app_display_name.lower() == app_name_lower:
                        self.channel_ids[service] = app
            logger.info(f"Found {len(apps)} installed Roku apps")
        except Exception as e:
            logger.error(f"Failed to query Roku apps: {type(e).__name__}")

    def _get_app(self, service: str) -> Any:
        """Get app object by service name.

        Args:
            service: Service name (e.g., "netflix", "hulu")

        Returns:
            App object or None if not found
        """
        service_lower = service.lower()

        # Direct lookup
        if service_lower in self.channel_ids:
            return self.channel_ids[service_lower]

        # Try mapped name
        if service_lower in SERVICE_TO_APP_NAME:
            mapped_name = SERVICE_TO_APP_NAME[service_lower].lower()
            if mapped_name in self.channel_ids:
                return self.channel_ids[mapped_name]

        logger.warning("Requested Roku app not found")
        return None

    def launch_with_content(
        self, service: str, content_id: str, media_type: str
    ) -> bool:
        """Launch app with deep link to specific content.

        Uses Roku ECP API directly to pass deep link parameters.

        Args:
            service: Service name (e.g., "netflix", "hulu")
            content_id: Content identifier for deep linking
            media_type: Type of media (e.g., "movie", "tv", "show")

        Returns:
            True on success, False on failure
        """
        try:
            app = self._get_app(service)
            if app is None:
                return False

            # Use Roku ECP API directly for deep linking
            # POST /launch/<app_id>?contentId=<id>&mediaType=<type>
            app_id = app.id
            url = f"http://{self.roku_ip}:8060/launch/{app_id}"

            # Determine Roku mediaType parameter
            # - "episode" triggers auto-play for specific episodes
            # - "movie" triggers auto-play for movies
            # - "show"/"series" opens the show page (user picks episode)
            roku_media_type = media_type
            if media_type == "episode":
                roku_media_type = "episode"  # Auto-play episode
            elif service.lower() == "netflix":
                if media_type == "tv":
                    roku_media_type = "show"  # Netflix uses "show" for series
                # "movie" stays as "movie" for Netflix

            # Disney+ requires PascalCase parameters, others use camelCase
            if service.lower() == "disney+":
                params = {
                    "ContentID": content_id,
                    "MediaType": roku_media_type,
                }
            else:
                params = {
                    "contentId": content_id,
                    "mediaType": roku_media_type,
                }

            response = requests.post(url, params=params, timeout=10)
            if response.status_code == 200:
                logger.info("Launched Roku content")

                # Netflix doesn't auto-play via deep link - send Select after loading
                if service.lower() == "netflix":
                    time.sleep(5)  # Wait for Netflix to load content page
                    self.select()
                    logger.info("Sent Select keypress to start Netflix playback")

                return True
            else:
                logger.warning(f"Roku returned status {response.status_code}")
                return False
        except Exception as e:
            logger.error("Failed to launch Roku content (%s)", type(e).__name__)
            return False

    def launch_app(self, service: str) -> bool:
        """Launch an app without deep linking.

        Args:
            service: Service name (e.g., "netflix", "hulu")

        Returns:
            True on success, False on failure
        """
        try:
            app = self._get_app(service)
            if app is None:
                return False

            app.launch()
            logger.info("Launched Roku app")
            return True
        except Exception as e:
            logger.error("Failed to launch Roku app (%s)", type(e).__name__)
            return False

    def search_and_navigate(self, query: str, launch: bool = False) -> bool:
        """Search for content using Roku ECP search API.

        Args:
            query: Search query string (title of movie/show)
            launch: If True, automatically launch the first result

        Returns:
            True on success, False on failure
        """
        try:
            # Use Roku ECP search API directly for more control
            # GET /search/browse?keyword=<query>&launch=true
            url = f"http://{self.roku_ip}:8060/search/browse"
            params = {
                "keyword": query,
            }
            if launch:
                params["launch"] = "true"

            response = requests.post(url, params=params, timeout=10)
            if response.status_code == 200:
                logger.info("Roku search completed")
                return True
            else:
                logger.warning(f"Search returned status {response.status_code}")
                # Fallback to python-roku search
                self.roku.search(query)
                return True
        except Exception as e:
            logger.error("Roku search failed (%s)", type(e).__name__)
            return False

    def power(self) -> bool:
        """Toggle power state.

        Returns:
            True on success, False on failure
        """
        try:
            self.roku.power()
            logger.debug("Toggled power")
            return True
        except Exception as e:
            logger.error(f"Failed to toggle power: {type(e).__name__}")
            return False

    def volume_up(self) -> bool:
        """Increase volume.

        Returns:
            True on success, False on failure
        """
        try:
            self.roku.volume_up()
            logger.debug("Volume up")
            return True
        except Exception as e:
            logger.error(f"Failed to increase volume: {type(e).__name__}")
            return False

    def volume_down(self) -> bool:
        """Decrease volume.

        Returns:
            True on success, False on failure
        """
        try:
            self.roku.volume_down()
            logger.debug("Volume down")
            return True
        except Exception as e:
            logger.error(f"Failed to decrease volume: {type(e).__name__}")
            return False

    def mute(self) -> bool:
        """Toggle mute.

        Returns:
            True on success, False on failure
        """
        try:
            self.roku.mute()
            logger.debug("Toggled mute")
            return True
        except Exception as e:
            logger.error(f"Failed to toggle mute: {type(e).__name__}")
            return False

    def play_pause(self) -> bool:
        """Toggle play/pause.

        Returns:
            True on success, False on failure
        """
        try:
            self.roku.play()
            logger.debug("Toggled play/pause")
            return True
        except Exception as e:
            logger.error(f"Failed to toggle play/pause: {type(e).__name__}")
            return False

    def home(self) -> bool:
        """Go to home screen.

        Returns:
            True on success, False on failure
        """
        try:
            self.roku.home()
            logger.debug("Pressed home")
            return True
        except Exception as e:
            logger.error(f"Failed to go home: {type(e).__name__}")
            return False

    def back(self) -> bool:
        """Go back.

        Returns:
            True on success, False on failure
        """
        try:
            self.roku.back()
            logger.debug("Pressed back")
            return True
        except Exception as e:
            logger.error(f"Failed to go back: {type(e).__name__}")
            return False

    def select(self) -> bool:
        """Press select/OK.

        Returns:
            True on success, False on failure
        """
        try:
            self.roku.select()
            logger.debug("Pressed select")
            return True
        except Exception as e:
            logger.error(f"Failed to press select: {type(e).__name__}")
            return False

    def up(self) -> bool:
        """Navigate up.

        Returns:
            True on success, False on failure
        """
        try:
            self.roku.up()
            logger.debug("Pressed up")
            return True
        except Exception as e:
            logger.error(f"Failed to navigate up: {type(e).__name__}")
            return False

    def down(self) -> bool:
        """Navigate down.

        Returns:
            True on success, False on failure
        """
        try:
            self.roku.down()
            logger.debug("Pressed down")
            return True
        except Exception as e:
            logger.error(f"Failed to navigate down: {type(e).__name__}")
            return False

    def left(self) -> bool:
        """Navigate left.

        Returns:
            True on success, False on failure
        """
        try:
            self.roku.left()
            logger.debug("Pressed left")
            return True
        except Exception as e:
            logger.error(f"Failed to navigate left: {type(e).__name__}")
            return False

    def right(self) -> bool:
        """Navigate right.

        Returns:
            True on success, False on failure
        """
        try:
            self.roku.right()
            logger.debug("Pressed right")
            return True
        except Exception as e:
            logger.error(f"Failed to navigate right: {type(e).__name__}")
            return False

    def get_active_app(self) -> str | None:
        """Get the name of the currently active app.

        Returns:
            App name string or None if unable to determine
        """
        try:
            active = self.roku.active_app
            if active:
                logger.debug("Retrieved active Roku app")
                return active.name
            return None
        except Exception as e:
            logger.error(f"Failed to get active app: {type(e).__name__}")
            return None
