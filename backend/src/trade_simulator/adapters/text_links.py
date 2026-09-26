"""Keeps agent-written text plain: links belong in `sources`, not in the sentence (D31).

Models sometimes write Markdown links or a trailing "Sources: ..." into a summary. This moves every
URL out of the text and returns it separately, so the UI can show clean prose with clickable sources.
"""

import re

_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_BARE_URL = re.compile(r"\(?\bhttps?://[^\s)]+\)?")
_SOURCES_TAIL = re.compile(r"\s*\bSources?:.*$", re.IGNORECASE | re.DOTALL)
_SPACE_BEFORE_PUNCTUATION = re.compile(r"\s+([.,;:!?])")


def split_links(text: str) -> tuple[str, list[str]]:
    urls: list[str] = []

    def keep_label(match: re.Match) -> str:
        urls.append(match.group(2))
        return match.group(1)

    def drop_url(match: re.Match) -> str:
        urls.append(match.group(0).strip("()"))
        return ""

    text = _MARKDOWN_LINK.sub(keep_label, text)
    text = _BARE_URL.sub(drop_url, text)
    text = _SOURCES_TAIL.sub("", text)
    text = _SPACE_BEFORE_PUNCTUATION.sub(r"\1", text)
    text = re.sub(r"\s{2,}", " ", text).strip().rstrip(",;:")
    return text, list(dict.fromkeys(urls))


def merge_sources(*groups) -> tuple[str, ...]:
    """Combine source lists, keeping the first occurrence of each URL."""
    return tuple(dict.fromkeys(url for group in groups for url in group if url))
