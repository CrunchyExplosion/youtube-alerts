"""Errors raised by the scraping layer."""


class ScraperError(Exception):
    """Base class for all scraper failures."""


class InvalidChannelUrlError(ScraperError):
    """The supplied URL is not a recognisable YouTube channel URL."""


class ChannelFetchError(ScraperError):
    """The channel page or feed could not be downloaded."""


class NoVideosFoundError(ScraperError):
    """The channel page loaded but no video could be extracted from it."""
