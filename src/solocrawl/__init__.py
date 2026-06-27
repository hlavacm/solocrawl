"""SoloCrawl: self-hosted web search, scraping, and package-version lookup."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("solocrawl")
except PackageNotFoundError:
    __version__ = "1.0.0"
