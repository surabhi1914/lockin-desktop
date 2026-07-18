"""Future, provider-neutral now-playing extension point."""

from typing import Protocol


class NowPlayingService(Protocol):
    """Interface a future focus screen may use to display song and artist.

    Phase 0 provides no implementation, networking, credentials, persistence, or
    music-provider dependency.
    """

    def current_song_and_artist(self) -> tuple[str, str] | None:
        """Return current song and artist labels, or ``None`` when unavailable."""
        ...
