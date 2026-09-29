"""Content discovery service using TMDB API."""

import random
from dataclasses import dataclass

import requests
from rapidfuzz import fuzz
from tmdbv3api import TMDb, Search, TV, Season


@dataclass
class ContentResult:
    """Result from a TMDB content search."""

    tmdb_id: int
    title: str
    media_type: str  # 'movie' or 'tv'
    year: int | None


@dataclass
class Episode:
    """TV show episode information."""

    season: int
    number: int
    name: str
    overview: str | None


class ContentSearch:
    """Content discovery service using TMDB API with watch providers."""

    # Map TMDB provider IDs to our service names
    # Provider IDs from TMDB watch providers API
    PROVIDER_ID_MAP = {
        8: "netflix",  # Netflix
        337: "disney+",  # Disney Plus
        2: "apple_tv",  # Apple TV
        350: "apple_tv",  # Apple TV Plus
        9: "amazon",  # Amazon Prime Video
        15: "hulu",  # Hulu
        1899: "max",  # Max (formerly HBO Max)
        384: "max",  # HBO Max
        386: "peacock",  # Peacock
        531: "paramount+",  # Paramount Plus
        283: "crunchyroll",  # Crunchyroll
    }

    # Map provider names (fallback)
    PROVIDER_NAME_MAP = {
        "Netflix": "netflix",
        "Disney Plus": "disney+",
        "Apple TV": "apple_tv",
        "Apple TV+": "apple_tv",
        "Amazon Prime Video": "amazon",
        "Hulu": "hulu",
        "Max": "max",
        "HBO Max": "max",
        "Peacock": "peacock",
        "Peacock Premium": "peacock",
        "Paramount+": "paramount+",
        "Paramount Plus": "paramount+",
    }

    # Watchmode source IDs for streaming services
    WATCHMODE_SOURCE_IDS = {
        203: "netflix",  # Netflix
        372: "disney+",  # Disney Plus
        371: "apple_tv",  # Apple TV Plus
        26: "amazon",  # Amazon Prime Video
        157: "hulu",  # Hulu
        387: "max",  # Max (HBO Max)
        389: "peacock",  # Peacock
        444: "paramount+",  # Paramount Plus
    }

    def __init__(self, tmdb_api_key: str, watchmode_api_key: str | None = "") -> None:
        """Initialize TMDB and Watchmode clients.

        Args:
            tmdb_api_key: API key for TMDB
            watchmode_api_key: API key for Watchmode (optional, for Netflix deep links)
        """
        self.tmdb = TMDb()
        self.tmdb.api_key = tmdb_api_key
        self.watchmode_api_key = watchmode_api_key
        self.search_client = Search()
        self.tv_client = TV()

    def search(self, query: str, service: str | None = None) -> ContentResult | None:
        """Search TMDB for movie/show with title-similarity-aware ranking.

        Ranking priority:
        1. Title similarity to query (exact matches first)
        2. Released content (year <= current year)
        3. Streaming availability on requested service

        This ensures "Moana" returns "Moana" (2016) not "Moana 2" (2024).

        Args:
            query: Search query string
            service: Optional service name to filter by (e.g., "disney+", "netflix")

        Returns:
            ContentResult with tmdb_id, title, media_type, year, or None if not found
        """
        import datetime

        current_year = datetime.datetime.now().year

        try:
            # Search for multi (movies and TV shows)
            results = self.search_client.multi(query)

            if not results:
                return None

            # Collect candidates with TMDB rank (popularity order)
            candidates = []
            for tmdb_rank, result in enumerate(results):
                media_type = getattr(result, "media_type", None)

                if media_type == "movie":
                    title = getattr(result, "title", "") or ""
                    release_date = getattr(result, "release_date", None)
                    year = int(release_date[:4]) if release_date else None
                    candidates.append(
                        (
                            tmdb_rank,
                            ContentResult(
                                tmdb_id=result.id,
                                title=title,
                                media_type="movie",
                                year=year,
                            ),
                        )
                    )
                elif media_type == "tv":
                    title = getattr(result, "name", "") or ""
                    first_air_date = getattr(result, "first_air_date", None)
                    year = int(first_air_date[:4]) if first_air_date else None
                    candidates.append(
                        (
                            tmdb_rank,
                            ContentResult(
                                tmdb_id=result.id,
                                title=title,
                                media_type="tv",
                                year=year,
                            ),
                        )
                    )

            if not candidates:
                return None

            # Score by title similarity
            query_lower = query.lower()

            def strip_article(s: str) -> str:
                """Strip leading articles (the, a, an) from title."""
                for article in ["the ", "a ", "an "]:
                    if s.startswith(article):
                        return s[len(article) :]
                return s

            def title_score(candidate: ContentResult) -> float:
                """Score candidate by title similarity to query.

                Handles article prefixes so "Avengers" matches "The Avengers" well.
                Also penalizes sequel indicators (colons, numbers) in title.
                """
                if not candidate.title:
                    return 0
                title_lower = candidate.title.lower()
                query_stripped = strip_article(query_lower)
                title_stripped = strip_article(title_lower)

                # Exact match (with or without articles)
                if title_lower == query_lower or title_stripped == query_stripped:
                    return 1000

                # Title equals query + article (e.g., "The Avengers" for "Avengers")
                if title_stripped == query_lower or title_lower == query_stripped:
                    return 950

                # Title starts with query (e.g., "SpongeBob SquarePants" for "SpongeBob")
                if title_lower.startswith(query_lower) or title_stripped.startswith(
                    query_stripped
                ):
                    # Penalize if title has sequel indicators (colon, numbers after title)
                    # "Avengers: Infinity War" should score lower than "Avengers Assemble"
                    if ":" in candidate.title or candidate.title[-1].isdigit():
                        return 850
                    return 900

                # Query is contained in title
                if query_lower in title_lower:
                    return 800

                # Fuzzy match
                return fuzz.ratio(query_lower, title_lower)

            # Filter to released content
            # Sort by: title_score (desc), then TMDB rank (asc, preserves popularity)
            released = [
                (rank, c) for rank, c in candidates if c.year and c.year <= current_year
            ]
            released.sort(key=lambda rc: (title_score(rc[1]), -rc[0]), reverse=True)

            # Check streaming availability for top candidates (max 5 to limit API calls)
            for _rank, candidate in released[:5]:
                links = self.get_streaming_links(
                    candidate.tmdb_id, candidate.media_type
                )

                if not links:
                    continue

                # If service specified, check if content is on that service
                if service and service.lower() != "any":
                    if service.lower() in links:
                        return candidate
                    # Not on requested service, try next candidate
                    continue

                # No service filter, return first with streaming
                return candidate

            # Fall back to first released candidate if none have streaming links
            if released:
                return released[0][1]

            # Fall back to first result if nothing is released yet
            return candidates[0][1]
        except Exception:
            return None

    def get_all_episodes(self, tmdb_id: int) -> list[Episode]:
        """Get all episodes for a TV series.

        Args:
            tmdb_id: TMDB ID of the TV series

        Returns:
            List of Episode objects
        """
        episodes = []

        try:
            # Get TV show details to find number of seasons
            tv_details = self.tv_client.details(tmdb_id)
            num_seasons = getattr(tv_details, "number_of_seasons", 0)

            # Fetch each season's episodes
            season_client = Season()
            for season_num in range(1, num_seasons + 1):
                try:
                    season_details = season_client.details(tmdb_id, season_num)
                    season_episodes = getattr(season_details, "episodes", [])

                    for ep in season_episodes:
                        episodes.append(
                            Episode(
                                season=season_num,
                                number=getattr(ep, "episode_number", 0),
                                name=getattr(ep, "name", ""),
                                overview=getattr(ep, "overview", None) or None,
                            )
                        )
                except Exception:
                    # Skip seasons that fail to load
                    continue

        except Exception:
            return []

        return episodes

    def get_random_episode(self, tmdb_id: int) -> Episode | None:
        """Pick random episode from any season.

        Args:
            tmdb_id: TMDB ID of the TV series

        Returns:
            Random Episode, or None if no episodes found
        """
        episodes = self.get_all_episodes(tmdb_id)

        if not episodes:
            return None

        return random.choice(episodes)

    def search_episode_by_topic(self, tmdb_id: int, query: str) -> Episode | None:
        """Fuzzy search episodes by topic.

        Args:
            tmdb_id: TMDB ID of the TV series
            query: Search query to match against episode titles and overviews

        Returns:
            Best matching Episode if score >= 60, else None
        """
        episodes = self.get_all_episodes(tmdb_id)

        if not episodes:
            return None

        best_match = None
        best_score = 0.0

        for ep in episodes:
            searchable = f"{ep.name} {ep.overview or ''}"

            # Exact substring match gets perfect score
            if query.lower() in searchable.lower():
                score = 100.0
            else:
                score = fuzz.partial_ratio(query.lower(), searchable.lower())

            if score > best_score:
                best_score = score
                best_match = ep

        # Only return if score meets threshold
        if best_score >= 60:
            return best_match

        return None

    def get_watchmode_content_id(
        self, tmdb_id: int, media_type: str, service: str = "netflix"
    ) -> str | None:
        """Get streaming service content ID from Watchmode API.

        Args:
            tmdb_id: TMDB ID of the content
            media_type: 'movie' or 'tv'
            service: Service name to get content ID for (default: "netflix")

        Returns:
            Service-specific content ID, or None if not found
        """
        if not self.watchmode_api_key:
            return None

        try:
            # Watchmode uses format: movie-{id} or tv-{id}
            watchmode_type = "movie" if media_type == "movie" else "tv"
            watchmode_id = f"{watchmode_type}-{tmdb_id}"

            url = f"https://api.watchmode.com/v1/title/{watchmode_id}/details/"
            params = {"apiKey": self.watchmode_api_key, "append_to_response": "sources"}

            response = requests.get(url, params=params, timeout=10)

            if response.status_code != 200:
                return None

            data = response.json()
            sources = data.get("sources", [])

            # Find the requested service - try all matching sources until we get a valid ID
            for source in sources:
                source_id = source.get("source_id")
                source_name = self.WATCHMODE_SOURCE_IDS.get(source_id, "").lower()

                if source_name == service.lower():
                    # Extract content ID from web_url for deep linking
                    web_url = source.get("web_url", "")
                    content_id = self._extract_content_id_from_url(web_url, service)
                    if content_id:
                        return content_id
                    # URL parsing failed, try next source (may have different URL format)

            return None

        except Exception:
            return None

    def get_watchmode_episode_content_id(
        self, tmdb_id: int, season: int, episode: int, service: str
    ) -> str | None:
        """Get episode-specific content ID from Watchmode API.

        For episodes to auto-play on Roku, we need the episode-specific content ID,
        not the show-level ID.

        Note: Episode-level deep link URLs require a paid Watchmode plan.
        If unavailable, this returns None and caller falls back to show-level ID.

        Args:
            tmdb_id: TMDB ID of the TV series
            season: Season number
            episode: Episode number
            service: Service name (e.g., "netflix", "disney+")

        Returns:
            Episode-specific content ID, or None if not found
        """
        if not self.watchmode_api_key:
            return None

        try:
            # Use the /episodes/ endpoint which returns episodes with sources included
            watchmode_show_id = f"tv-{tmdb_id}"
            episodes_url = (
                f"https://api.watchmode.com/v1/title/{watchmode_show_id}/episodes/"
            )
            params = {"apiKey": self.watchmode_api_key}

            response = requests.get(episodes_url, params=params, timeout=10)
            if response.status_code != 200:
                return None

            episodes_data = response.json()

            # Find the matching episode
            for ep in episodes_data:
                if (
                    ep.get("season_number") == season
                    and ep.get("episode_number") == episode
                ):
                    # Episode found - check its sources
                    sources = ep.get("sources", [])
                    for source in sources:
                        source_id = source.get("source_id")
                        source_name = self.WATCHMODE_SOURCE_IDS.get(
                            source_id, ""
                        ).lower()

                        if source_name == service.lower():
                            web_url = source.get("web_url", "")
                            # Skip placeholder URLs from free tier
                            if "paid plans only" in web_url.lower():
                                return None
                            content_id = self._extract_content_id_from_url(
                                web_url, service
                            )
                            if content_id:
                                return content_id
                    return None

            return None

        except Exception:
            return None

    def _extract_content_id_from_url(self, url: str, service: str) -> str | None:
        """Extract service-specific content ID from a Watchmode web URL.

        Args:
            url: Web URL from Watchmode sources (e.g., https://www.netflix.com/title/81009946)
            service: Service name (e.g., "netflix", "disney+")

        Returns:
            Content ID string for Roku deep linking, or None if extraction fails
        """
        if not url:
            return None

        service_lower = service.lower()

        # Netflix: https://www.netflix.com/title/81009946
        if service_lower == "netflix" and "netflix.com" in url:
            if "/title/" in url:
                return url.split("/title/")[-1].split("?")[0].split("/")[0]

        # Disney+: Roku deep linking needs GUID format
        # From /browse/entity-{guid} or /play/{guid} URLs, extract the GUID
        # From /movies/name/{id} URLs, that ID doesn't work for Roku
        if service_lower == "disney+" and "disneyplus.com" in url:
            # Prefer entity URLs - extract GUID without "entity-" prefix
            if "/browse/entity-" in url:
                # URL like: https://www.disneyplus.com/browse/entity-e8896bfa-1052-41f7-ae2e-00255d77cf05
                entity_part = (
                    url.split("/browse/entity-")[-1].split("?")[0].split("/")[0]
                )
                return entity_part  # Returns just the GUID
            # Also check /play/ URLs which have GUIDs
            if "/play/" in url:
                # URL like: https://www.disneyplus.com/play/3c7d4077-3f03-4029-9c6c-e73a63a775d1
                play_id = url.split("/play/")[-1].split("?")[0].split("/")[0]
                # Verify it looks like a GUID (has dashes)
                if "-" in play_id:
                    return play_id
            # Fallback to /movies/ or /series/ format (may not work for Roku)
            if "/movies/" in url or "/series/" in url:
                parts = url.rstrip("/").split("/")
                if len(parts) >= 2:
                    return parts[-1].split("?")[0]
            return None

        # Hulu: https://www.hulu.com/series/name-uuid or /movie/name-uuid
        if service_lower == "hulu" and "hulu.com" in url:
            parts = url.rstrip("/").split("/")
            if len(parts) >= 2:
                return parts[-1].split("?")[0]

        # Max: https://play.max.com/show/uuid or /movie/uuid
        # Also handles legacy hbomax.com URLs
        if service_lower == "max" and ("max.com" in url or "hbomax.com" in url):
            parts = url.rstrip("/").split("/")
            if len(parts) >= 2:
                return parts[-1].split("?")[0]

        # Amazon Prime: https://www.amazon.com/gp/video/detail/B0ABCD123
        # or https://www.primevideo.com/detail/B0ABCD123
        # or https://watch.amazon.com/detail?gti=amzn1.dv.gti.UUID
        if service_lower == "amazon":
            if "/detail/" in url:
                return url.split("/detail/")[-1].split("?")[0].split("/")[0]
            if "/dp/" in url:
                return url.split("/dp/")[-1].split("?")[0].split("/")[0]
            if "?gti=" in url:
                return url.split("?gti=")[-1].split("&")[0]

        # Peacock: https://www.peacocktv.com/watch/asset/tv/show-name/uuid
        if service_lower == "peacock" and "peacocktv.com" in url:
            parts = url.rstrip("/").split("/")
            if len(parts) >= 2:
                return parts[-1].split("?")[0]

        # Paramount+: https://www.paramountplus.com/shows/video/uuid
        if service_lower == "paramount+" and "paramountplus.com" in url:
            parts = url.rstrip("/").split("/")
            if len(parts) >= 2:
                return parts[-1].split("?")[0]

        # Apple TV+: https://tv.apple.com/us/movie/name/umc.cmc.uuid
        if service_lower == "apple_tv" and "tv.apple.com" in url:
            parts = url.rstrip("/").split("/")
            if len(parts) >= 2:
                return parts[-1].split("?")[0]

        return None

    def get_streaming_links(self, tmdb_id: int, media_type: str) -> dict:
        """Get streaming availability from TMDB watch providers.

        Args:
            tmdb_id: TMDB ID of the content
            media_type: 'movie' or 'tv'

        Returns:
            Dict mapping service name to {content_id, url}
        """
        streaming_links = {}

        try:
            # Use TMDB's watch providers endpoint (powered by JustWatch)
            base_url = "https://api.themoviedb.org/3"
            url = f"{base_url}/{media_type}/{tmdb_id}/watch/providers?api_key={self.tmdb.api_key}"

            response = requests.get(url, timeout=10)

            if response.status_code != 200:
                return {}

            data = response.json()

            # Get US providers (or fallback to first available region)
            results = data.get("results", {})
            us_data = results.get("US", {})

            if not us_data:
                # Try first available region
                if results:
                    us_data = next(iter(results.values()), {})

            # Get the TMDB link for this content
            tmdb_link = us_data.get("link", "")

            # Extract flatrate (subscription) providers
            flatrate_providers = us_data.get("flatrate", [])

            for provider in flatrate_providers:
                provider_id = provider.get("provider_id")
                provider_name = provider.get("provider_name", "")

                # Map by ID first, then by name
                service_name = self.PROVIDER_ID_MAP.get(provider_id)
                if not service_name:
                    service_name = self.PROVIDER_NAME_MAP.get(provider_name)

                if service_name and service_name not in streaming_links:
                    # Default to TMDB ID as content reference
                    content_id = str(tmdb_id)

                    # Try to get actual content ID via Watchmode for proper deep linking
                    if self.watchmode_api_key:
                        service_content_id = self.get_watchmode_content_id(
                            tmdb_id, media_type, service_name
                        )
                        if service_content_id:
                            content_id = service_content_id

                    streaming_links[service_name] = {
                        "content_id": content_id,
                        "url": tmdb_link,
                        "provider_name": provider_name,
                    }

        except Exception:
            return {}

        return streaming_links
