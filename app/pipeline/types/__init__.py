"""Media-type strategies. `strategy_for` is the only place that maps type -> behaviour."""

from __future__ import annotations

from app.models.media import MediaType
from app.pipeline.types.audiobook import AudiobookStrategy
from app.pipeline.types.base import MediaStrategy
from app.pipeline.types.ebook import EbookStrategy
from app.pipeline.types.music import MusicStrategy
from app.pipeline.types.video import VideoStrategy

_VIDEO = VideoStrategy()
_STRATEGIES: dict[MediaType, MediaStrategy] = {
    MediaType.music: MusicStrategy(),
    MediaType.movie: _VIDEO,
    MediaType.series: _VIDEO,
    MediaType.audiobook: AudiobookStrategy(),
    MediaType.ebook: EbookStrategy(),
}
_DEFAULT = MediaStrategy()


def strategy_for(media_type) -> MediaStrategy:
    return _STRATEGIES.get(MediaType(media_type), _DEFAULT)
