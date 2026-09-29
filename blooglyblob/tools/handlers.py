"""Tool handlers for network integrations and timers.

These handlers execute retained network integrations and timers.
Content lookup and Roku calls use the injected integration owners.
"""

import json
import time
from typing import Callable

from blooglyblob.tools.content_search import ContentSearch
from blooglyblob.tools.roku_controller import RokuController
from blooglyblob.tools.timer_manager import TimerManager


# Preferred streaming services in order
PREFERRED_SERVICES = [
    "netflix",
    "disney+",
    "max",
    "hulu",
    "apple_tv",
    "amazon",
    "peacock",
    "paramount+",
]


def create_stream_content_handler(
    content_search: ContentSearch | None,
    roku_controller: RokuController | None,
) -> Callable[[dict], str]:
    """Create a stream content handler with injected dependencies."""

    def stream_content_handler(parameters: dict) -> str:
        """Tool handler for streaming content."""
        print("[TOOL CALLED] streamContent")

        if content_search is None or roku_controller is None:
            return "Error: Streaming not configured. Run 'make dev-setup-roku' first."

        title = parameters.get("title")
        service = parameters.get("service", "any")
        random_episode = parameters.get("random_episode", False)
        episode_query = parameters.get("episode_query")

        if not title:
            return "Error: No title provided"

        # 1. Search TMDB for the show/movie (streaming-aware: finds version with streaming links)
        result = content_search.search(
            title, service=service if service != "any" else None
        )
        if not result:
            if service and service != "any":
                return f"Couldn't find '{title}' available for streaming on {service}"
            return f"Couldn't find '{title}' available for streaming"

        # 2. Episode selection (for TV shows)
        episode = None
        episode_info = ""

        if result.media_type == "tv":
            if episode_query:
                episode = content_search.search_episode_by_topic(
                    result.tmdb_id, episode_query
                )
                if episode:
                    episode_info = f" - Season {episode.season}, Episode {episode.number}: '{episode.name}'"
                else:
                    return f"Couldn't find a {result.title} episode about '{episode_query}'"
            elif random_episode:
                episode = content_search.get_random_episode(result.tmdb_id)
                if episode:
                    episode_info = f" - Random pick: S{episode.season}E{episode.number} '{episode.name}'"

        # 3. Get streaming availability
        links = content_search.get_streaming_links(result.tmdb_id, result.media_type)

        # 4. Pick service
        if service == "any":
            for preferred in PREFERRED_SERVICES:
                if preferred in links:
                    service = preferred
                    break

        if not links:
            return f"Couldn't find streaming info for '{title}'"

        if service == "any":
            # Use first available service
            service = next(iter(links.keys()))
        elif service not in links:
            available = ", ".join(links.keys())
            return f"'{title}' isn't on {service}. Available on: {available}"

        # 5. Launch on Roku
        deep_link = links.get(service, {})
        content_id = deep_link.get("content_id")
        launch_media_type = result.media_type  # Default: "tv" or "movie"

        # For episodes, try to get episode-specific content ID for auto-play
        if episode and content_search.watchmode_api_key:
            ep_content_id = content_search.get_watchmode_episode_content_id(
                result.tmdb_id, episode.season, episode.number, service
            )
            if ep_content_id:
                content_id = ep_content_id
                launch_media_type = "episode"  # Roku auto-plays episodes
                print("[STREAM] Using episode-specific content")

        if content_id:
            if roku_controller.launch_with_content(
                service, content_id, launch_media_type
            ):
                return f"Playing {result.title}{episode_info} on {service}"
            else:
                roku_controller.launch_app(service)
                return f"Opened {service}. Search for {result.title}{episode_info}"
        else:
            roku_controller.launch_app(service)
            return f"Opened {service}. Search for {result.title}{episode_info}"

    return stream_content_handler


def create_roku_control_handler(
    roku_controller: RokuController | None,
) -> Callable[[dict], str]:
    """Create a Roku control handler with injected dependency."""

    def roku_control_handler(parameters: dict) -> str:
        """Tool handler for Roku remote control."""
        print("[TOOL CALLED] rokuControl")

        if roku_controller is None:
            return "Error: Roku not configured. Run 'make dev-setup-roku' first."

        action = parameters.get("action", "")
        app = parameters.get("app")

        action_map = {
            "power": roku_controller.power,
            "volume_up": roku_controller.volume_up,
            "volume_down": roku_controller.volume_down,
            "mute": roku_controller.mute,
            "play_pause": roku_controller.play_pause,
            "home": roku_controller.home,
            "back": roku_controller.back,
            "up": roku_controller.up,
            "down": roku_controller.down,
            "left": roku_controller.left,
            "right": roku_controller.right,
            "select": roku_controller.select,
        }

        if action == "launch_app":
            if not app:
                return "Error: No app specified"
            if roku_controller.launch_app(app):
                return f"Launched {app}"
            else:
                return f"Couldn't launch {app}"
        elif action in action_map:
            if action_map[action]():
                return f"Done: {action.replace('_', ' ')}"
            else:
                return f"Failed: {action}"
        else:
            return f"Unknown action: {action}"

    return roku_control_handler


def create_timer_handlers(
    timer_manager: TimerManager | None,
) -> tuple[Callable[[dict], str], Callable[[dict], str], Callable[[dict], str]]:
    """Create timer handlers with injected TimerManager.

    Returns:
        Tuple of (set_timer_handler, cancel_timer_handler, find_timers_handler)
    """

    def set_timer_handler(parameters: dict) -> str:
        """Tool handler for setting countdown timers."""
        print("[TOOL CALLED] setTimer")

        if timer_manager is None:
            return "Error: Timer system not initialized"

        duration_seconds = parameters.get("duration_seconds")
        if not duration_seconds or duration_seconds <= 0:
            return "Error: Invalid duration"

        label = parameters.get("label", "")
        timer_manager.add_timer(duration_seconds, label)

        # Format duration for response
        if duration_seconds >= 3600:
            hours = duration_seconds // 3600
            mins = (duration_seconds % 3600) // 60
            if mins > 0:
                duration_str = f"{hours} hour{'s' if hours > 1 else ''} and {mins} minute{'s' if mins > 1 else ''}"
            else:
                duration_str = f"{hours} hour{'s' if hours > 1 else ''}"
        elif duration_seconds >= 60:
            mins = duration_seconds // 60
            secs = duration_seconds % 60
            if secs > 0:
                duration_str = f"{mins} minute{'s' if mins > 1 else ''} and {secs} second{'s' if secs > 1 else ''}"
            else:
                duration_str = f"{mins} minute{'s' if mins > 1 else ''}"
        else:
            duration_str = (
                f"{duration_seconds} second{'s' if duration_seconds > 1 else ''}"
            )

        if label:
            return f"Timer set for {duration_str} ({label})"
        else:
            return f"Timer set for {duration_str}"

    def cancel_timer_handler(parameters: dict) -> str:
        """Tool handler for canceling timers."""
        print("[TOOL CALLED] cancelTimer")

        if timer_manager is None:
            return "Error: Timer system not initialized"

        timer_id = parameters.get("timer_id", "")

        if timer_id.lower() == "all":
            count = timer_manager.cancel_all()
            if count > 0:
                return f"Cancelled {count} timer{'s' if count > 1 else ''}"
            else:
                return "No active timers to cancel"
        else:
            if timer_manager.cancel_timer(timer_id):
                return "Timer cancelled"
            else:
                return "Timer not found"

    def find_timers_handler(parameters: dict) -> str:
        """Tool handler for searching timers."""
        queries = parameters.get("queries", [])
        queries_lower = [q.lower() for q in queries if q]
        print("[TOOL CALLED] findTimers")

        if timer_manager is None:
            return "Error: Timer system not initialized"

        timers = timer_manager.get_active_timers()

        # Filter by queries if provided (match ANY term)
        if queries_lower:
            timers = [
                t for t in timers if any(q in t.label.lower() for q in queries_lower)
            ]

        if not timers:
            if queries_lower:
                return f"No timers matching: {', '.join(queries_lower)}"
            return "No active timers"

        now = time.time()
        result = []
        for t in timers:
            remaining_secs = int(t.fire_at - now)
            if remaining_secs < 60:
                remaining = f"{remaining_secs}s"
            elif remaining_secs < 3600:
                remaining = f"{remaining_secs // 60}m {remaining_secs % 60}s"
            else:
                hours = remaining_secs // 3600
                mins = (remaining_secs % 3600) // 60
                remaining = f"{hours}h {mins}m"

            result.append(
                {
                    "id": t.id,
                    "label": t.label,
                    "type": t.timer_type,
                    "remaining": remaining,
                }
            )

        return json.dumps(result)

    return set_timer_handler, cancel_timer_handler, find_timers_handler


class ToolHandlers:
    """Container for content, Roku, and timer tool handlers.

    Initialize with optional dependencies (content_search, roku_controller, timer_manager).
    Missing dependencies result in graceful error messages from handlers.
    """

    def __init__(
        self,
        content_search: ContentSearch | None = None,
        roku_controller: RokuController | None = None,
        timer_manager: TimerManager | None = None,
    ):
        """Initialize tool handlers with dependencies.

        Args:
            content_search: ContentSearch instance for TMDB/Watchmode
            roku_controller: RokuController instance for Roku ECP
            timer_manager: TimerManager instance for countdown timers
        """
        self.content_search = content_search
        self.roku_controller = roku_controller
        self.timer_manager = timer_manager

        # Create handlers with injected dependencies
        self.stream_content = create_stream_content_handler(
            content_search, roku_controller
        )
        self.roku_control = create_roku_control_handler(roku_controller)

        set_timer, cancel_timer, find_timers = create_timer_handlers(timer_manager)
        self.set_timer = set_timer
        self.cancel_timer = cancel_timer
        self.find_timers = find_timers

    def get_handler(self, tool_name: str) -> Callable[[dict], str] | None:
        """Get handler function by tool name.

        Args:
            tool_name: Name of the tool (e.g., "setTimer", "streamContent")

        Returns:
            Handler function, or None if not found
        """
        handler_map = {
            "streamContent": self.stream_content,
            "rokuControl": self.roku_control,
            "setTimer": self.set_timer,
            "cancelTimer": self.cancel_timer,
            "findTimers": self.find_timers,
        }
        return handler_map.get(tool_name)

    def handle(self, tool_name: str, parameters: dict) -> str:
        """Execute a tool by name with given parameters.

        Args:
            tool_name: Name of the tool
            parameters: Tool parameters dict

        Returns:
            Tool result string
        """
        handler = self.get_handler(tool_name)
        if handler is None:
            return f"Error: Unknown tool '{tool_name}'"
        return handler(parameters)
