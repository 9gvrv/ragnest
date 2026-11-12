import pytest

from app.modules.auth.deps import get_google_client
from app.modules.auth.google import GoogleProfile


class FakeGoogleClient:
    """Stands in for Google: returns a profile, or raises what a test sets."""

    def __init__(self) -> None:
        self.profile = GoogleProfile(sub="google-sub-1", email="person@example.com")
        self.error: Exception | None = None
        self.calls: list[dict[str, str]] = []

    async def exchange_code(
        self,
        *,
        code: str,
        code_verifier: str,
        redirect_uri: str,
    ) -> GoogleProfile:
        self.calls.append(
            {"code": code, "code_verifier": code_verifier, "redirect_uri": redirect_uri}
        )
        if self.error is not None:
            raise self.error
        return self.profile


@pytest.fixture
def fake_google() -> FakeGoogleClient:
    return FakeGoogleClient()


@pytest.fixture(autouse=True)
def _override_google_client(app, fake_google):
    app.dependency_overrides[get_google_client] = lambda: fake_google
    yield
    app.dependency_overrides.pop(get_google_client, None)
