"""Coverage for NuGet registration-page loading and metadata extraction."""

from __future__ import annotations

import httpx

from solocrawl.config import Config
from solocrawl.core.fetch.client import set_client_for_testing
from solocrawl.core.packages.providers.nuget import NuGetProvider

_INDEX = {"versions": ["1.0.0", "2.0.0"]}
_REGISTRATION = {
    "items": [
        # A page WITHOUT inline items but WITH an @id -> provider fetches it.
        {"@id": "https://api.nuget.org/v3/registration5-gz-semver2/pkg/page/1.json"}
    ]
}
_PAGE = {
    "items": [
        {
            "catalogEntry": {
                "version": "1.0.0",
                "listed": True,
                "projectUrl": "https://proj.example",
            }
        },
        {"catalogEntry": {"version": "2.0.0", "listed": False}},
    ]
}


async def test_nuget_loads_registration_pages() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "flatcontainer" in url:
            return httpx.Response(200, json=_INDEX, request=request)
        if "/page/1.json" in url:
            return httpx.Response(200, json=_PAGE, request=request)
        if "registration" in url:
            return httpx.Response(200, json=_REGISTRATION, request=request)
        return httpx.Response(404, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)
    try:
        info = await NuGetProvider(config=Config()).get_package("Pkg")
        # 2.0.0 is unlisted (yanked) -> latest stable is 1.0.0, repo from its catalogEntry.
        assert info.latest == "1.0.0"
        assert info.repository == "https://proj.example"
    finally:
        await client.aclose()
