import pytest

from candlestack.accounts.service import is_connect_state, safe_next

BACKSLASH = chr(92)


@pytest.mark.parametrize(
    "path",
    ["/dashboard", "/instruments?market=crypto", "/settings#account", "/", "/apis", "/apiary"],
)
def test_a_page_of_the_app_is_kept(path: str) -> None:
    assert safe_next(path) == path


@pytest.mark.parametrize(
    "path",
    [
        None,
        "",
        "dashboard",
        "https://evil.example/",
        "//evil.example/dashboard",
        f"/{BACKSLASH}evil.example",
        f"/dash{BACKSLASH}board",
        "/dashboard\r\nSet-Cookie: x=1",
        "/dashboard\x00",
        "/api",
        "/api/v1/auth/sign-out",
        "/api?x=1",
        "/api#x",
        "/" + "a" * 2048,
    ],
)
def test_anything_else_opens_the_dashboard(path: str | None) -> None:
    assert safe_next(path) == "/dashboard"


def test_connect_falls_back_to_its_own_default() -> None:
    assert safe_next("//evil.example/", "/settings/sign-in") == "/settings/sign-in"
    assert safe_next("/settings/sign-in?from=banner", "/settings/sign-in") == (
        "/settings/sign-in?from=banner"
    )


@pytest.mark.parametrize(
    ("state", "connecting"),
    [("connect.abc", True), ("abc", False), ("", False), (None, False), ("xconnect.", False)],
)
def test_a_connect_is_known_by_its_state(state: str | None, connecting: bool) -> None:
    assert is_connect_state(state) is connecting
