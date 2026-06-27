"""Package registry providers."""

from solocrawl.core.packages.providers import crates as crates  # noqa: F401
from solocrawl.core.packages.providers import golang as golang  # noqa: F401
from solocrawl.core.packages.providers import maven as maven  # noqa: F401
from solocrawl.core.packages.providers import npm as npm  # noqa: F401
from solocrawl.core.packages.providers import nuget as nuget  # noqa: F401
from solocrawl.core.packages.providers import packagist as packagist  # noqa: F401
from solocrawl.core.packages.providers import pub as pub  # noqa: F401
from solocrawl.core.packages.providers import pypi as pypi  # noqa: F401
from solocrawl.core.packages.providers import rubygems as rubygems  # noqa: F401
from solocrawl.core.packages.providers import swift as swift  # noqa: F401

__all__ = [
    "crates",
    "golang",
    "maven",
    "npm",
    "nuget",
    "packagist",
    "pub",
    "pypi",
    "rubygems",
    "swift",
]
