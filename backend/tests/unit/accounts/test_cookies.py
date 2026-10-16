from fastapi import Response

from candlestack.accounts.cookies import SESSION, STATE, Cookies


def test_over_https_secure_and_host_prefixed() -> None:
    response = Response()

    Cookies("https://app.candlestack.tech").set(response, SESSION, "token", 60)

    assert response.headers["set-cookie"] == (
        "__Host-session=token; HttpOnly; Max-Age=60; Path=/; SameSite=lax; Secure"
    )


def test_over_http_plain() -> None:
    response = Response()

    Cookies("http://localhost:5173").set(response, STATE, "state", 600)

    assert response.headers["set-cookie"] == (
        "sign_in_state=state; HttpOnly; Max-Age=600; Path=/; SameSite=lax"
    )


def test_delete_expires_the_same_cookie() -> None:
    response = Response()

    Cookies("https://app.candlestack.tech").delete(response, SESSION)

    cookie = response.headers["set-cookie"]
    assert cookie.startswith('__Host-session=""; ')
    assert "Max-Age=0" in cookie
    assert "Path=/" in cookie
    assert "Secure" in cookie
