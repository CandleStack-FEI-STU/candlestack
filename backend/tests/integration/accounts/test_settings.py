"""Settings over HTTP, against a real Postgres and Redis, with GitHub and Google mocked
(conftest.py): the display name, sign-in methods, preferences, signing out everywhere and
deleting the account."""

import json
import logging
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from candlestack.accounts import AfterDeletion, service, store

pytestmark = pytest.mark.integration

PROBLEMS = "https://candlestack.tech/problems/"
ORIGIN = {"Origin": "http://testserver"}
DEFAULT_BACKTEST = {
    "timeframe": "30m",
    "period_start": "2021-01-04",
    "period_end": "2024-12-31",
    "direction": "long",
    "threshold": 0.05,
    "stop_loss_pct": 7,
    "fees_pct": 0.1,
    "slippage_pct": 0.02,
    "benchmark": "bh",
}
DEFAULT_APPEARANCE = {
    "theme": "dark",
    "time_zone": "ny",
    "date_format": "dmy",
    "time_format": "24",
    "reduce_motion": False,
}
BACKTEST = {
    "timeframe": "1h",
    "period_start": "2022-03-01",
    "period_end": "2023-03-01",
    "direction": "both",
    "threshold": 0.12,
    "stop_loss_pct": 5,
    "fees_pct": 0.05,
    "slippage_pct": 0.01,
    "benchmark": "SPY",
}


def cookies_set(response) -> dict[str, str]:
    """The cookies a response sets or deletes, by name: the whole Set-Cookie line."""
    return {line.split("=", 1)[0]: line for line in response.headers.get_list("set-cookie")}


# --- Profile ---------------------------------------------------------------------------------


def test_rename(browser, sql) -> None:
    browser.sign_in("github")

    renamed = browser.patch("/api/v1/me", json={"display_name": "  Ada King  "}, headers=ORIGIN)

    assert renamed.status_code == 200
    assert renamed.headers["cache-control"] == "no-store"
    assert renamed.json()["display_name"] == "Ada King"
    assert browser.me().json()["display_name"] == "Ada King"
    assert sql("SELECT display_name FROM users") == [("Ada King",)]


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("PATCH", "/api/v1/me", {"display_name": "Ada King", "email": "eve@example.com"}),
        ("PUT", "/api/v1/me/preferences/backtest-defaults", {**BACKTEST, "stop_loss": 5}),
        ("PATCH", "/api/v1/me/preferences/appearance", {"theme": "light", "colour": "red"}),
    ],
)
def test_an_unknown_field_is_refused(browser, sql, method, path, body) -> None:
    """A field the API does not know is a client's mistake (a typo, an old name): saving the
    rest would look like success."""
    browser.sign_in("github")

    response = browser.request(method, path, json=body, headers=ORIGIN)

    assert response.status_code == 422
    assert response.json()["type"] == PROBLEMS + "validation"
    assert browser.me().json()["display_name"] == "Ada Lovelace"
    assert sql("SELECT user_id FROM user_preferences") == []


def test_a_blank_name_is_refused(browser) -> None:
    browser.sign_in("github")

    response = browser.patch("/api/v1/me", json={"display_name": " \t "}, headers=ORIGIN)

    assert response.status_code == 422
    assert response.json()["type"] == PROBLEMS + "validation"
    assert browser.me().json()["display_name"] == "Ada Lovelace"


# --- Preferences -----------------------------------------------------------------------------


def test_a_user_who_saved_nothing_gets_the_defaults(browser, sql) -> None:
    browser.sign_in("github")

    response = browser.get("/api/v1/me/preferences")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "backtest_defaults": DEFAULT_BACKTEST,
        "appearance": DEFAULT_APPEARANCE,
    }
    assert sql("SELECT user_id FROM user_preferences") == []


def test_save_backtest_defaults(browser, sql) -> None:
    browser.sign_in("github")

    saved = browser.put("/api/v1/me/preferences/backtest-defaults", json=BACKTEST, headers=ORIGIN)

    assert saved.status_code == 200
    assert saved.headers["cache-control"] == "no-store"
    assert saved.json() == BACKTEST
    assert browser.get("/api/v1/me/preferences").json() == {
        "backtest_defaults": BACKTEST,
        "appearance": DEFAULT_APPEARANCE,
    }
    [(stored, appearance)] = sql("SELECT backtest_defaults, appearance FROM user_preferences")
    assert stored == BACKTEST
    assert appearance == {}


def test_backtest_defaults_are_replaced_as_a_whole(browser) -> None:
    browser.sign_in("github")
    browser.put("/api/v1/me/preferences/backtest-defaults", json=BACKTEST, headers=ORIGIN)

    saved = browser.put(
        "/api/v1/me/preferences/backtest-defaults",
        json={**DEFAULT_BACKTEST, "timeframe": "5m"},
        headers=ORIGIN,
    )

    assert saved.json() == {**DEFAULT_BACKTEST, "timeframe": "5m"}
    assert browser.get("/api/v1/me/preferences").json()["backtest_defaults"] == saved.json()


def test_backtest_defaults_without_every_field_are_refused(browser) -> None:
    """A field left out is not reset to its default: the client sends all of them."""
    browser.sign_in("github")
    browser.put("/api/v1/me/preferences/backtest-defaults", json=BACKTEST, headers=ORIGIN)

    response = browser.put(
        "/api/v1/me/preferences/backtest-defaults", json={"timeframe": "5m"}, headers=ORIGIN
    )

    assert response.status_code == 422
    assert response.json()["type"] == PROBLEMS + "validation"
    assert browser.get("/api/v1/me/preferences").json()["backtest_defaults"] == BACKTEST


def test_a_period_that_ends_before_it_starts_is_refused(browser, sql) -> None:
    browser.sign_in("github")

    response = browser.put(
        "/api/v1/me/preferences/backtest-defaults",
        json={**BACKTEST, "period_start": "2023-03-01", "period_end": "2023-03-01"},
        headers=ORIGIN,
    )

    assert response.status_code == 422
    assert response.json()["type"] == PROBLEMS + "validation"
    assert "period_start must be before period_end" in response.json()["detail"]
    assert sql("SELECT user_id FROM user_preferences") == []


def test_appearance_changes_only_what_is_given(browser, sql) -> None:
    browser.sign_in("github")

    first = browser.patch(
        "/api/v1/me/preferences/appearance", json={"theme": "light"}, headers=ORIGIN
    )
    second = browser.patch(
        "/api/v1/me/preferences/appearance",
        json={"reduce_motion": True, "theme": None},
        headers=ORIGIN,
    )

    assert first.status_code == 200
    assert first.headers["cache-control"] == "no-store"
    assert first.json() == {**DEFAULT_APPEARANCE, "theme": "light"}
    assert second.json() == {**DEFAULT_APPEARANCE, "theme": "light", "reduce_motion": True}
    # Only what was saved is stored: the defaults of the rest can still change.
    assert sql("SELECT appearance FROM user_preferences") == [
        ({"theme": "light", "reduce_motion": True},)
    ]
    assert browser.get("/api/v1/me/preferences").json()["appearance"] == second.json()


def test_the_sections_are_saved_apart(browser) -> None:
    browser.sign_in("github")
    browser.patch("/api/v1/me/preferences/appearance", json={"time_format": "12"}, headers=ORIGIN)

    browser.put("/api/v1/me/preferences/backtest-defaults", json=BACKTEST, headers=ORIGIN)
    browser.patch("/api/v1/me/preferences/appearance", json={"date_format": "iso"}, headers=ORIGIN)

    assert browser.get("/api/v1/me/preferences").json() == {
        "backtest_defaults": BACKTEST,
        "appearance": {**DEFAULT_APPEARANCE, "time_format": "12", "date_format": "iso"},
    }


def test_a_setting_missing_from_a_saved_document_has_its_default(browser, sql) -> None:
    """A setting added after the user saved reads as its default, without a data migration;
    one the model does not know is ignored."""
    browser.sign_in("github")
    user_id = browser.me().json()["id"]
    saved = json.dumps({"timeframe": "1d", "retired_setting": 1})
    sql(
        "INSERT INTO user_preferences (user_id, backtest_defaults, updated_at) "
        f"VALUES ('{user_id}', '{saved}', now())"
    )

    preferences = browser.get("/api/v1/me/preferences").json()

    assert preferences["backtest_defaults"] == {**DEFAULT_BACKTEST, "timeframe": "1d"}
    assert preferences["appearance"] == DEFAULT_APPEARANCE


def test_users_have_their_own_preferences(browser, other_browser) -> None:
    browser.sign_in("github")
    other_browser.post("/api/v1/auth/dev", headers=ORIGIN)

    browser.patch("/api/v1/me/preferences/appearance", json={"theme": "light"}, headers=ORIGIN)

    assert other_browser.get("/api/v1/me/preferences").json()["appearance"]["theme"] == "dark"


# --- Connecting a sign-in method -------------------------------------------------------------


def test_connect_adds_a_sign_in_method(browser, providers, sql) -> None:
    browser.sign_in("github")
    session = browser.cookie("session")
    # Another email than the user's, and not on the beta list: neither matters to a connect.
    providers.google_account(subject="2001", email="ada.work@example.org")

    callback = browser.connect("google")

    assert callback.status_code == 302
    assert callback.headers["location"] == "/settings/sign-in"
    assert "session" not in cookies_set(callback)
    assert cookies_set(callback)["sign_in_state"].startswith('sign_in_state=""')
    assert browser.cookie("session") == session
    me = browser.me().json()
    assert (me["email"], me["providers"]) == ("ada@example.com", ["github", "google"])
    assert sql("SELECT email FROM identities WHERE provider = 'google'") == [
        ("ada.work@example.org",)
    ]
    # The connected account signs in as the user from now on.
    browser.sign_out()
    browser.sign_in("google")
    assert browser.me().json()["id"] == me["id"]


def test_me_names_the_account_of_each_sign_in_method(browser, providers) -> None:
    """A connected account may have another email than the user's: Settings shows each."""
    browser.sign_in("github")
    providers.google_account(subject="2001", email="ada.work@example.org")
    browser.connect("google")

    me = browser.me().json()

    assert me["email"] == "ada@example.com"
    assert me["providers"] == ["github", "google"]
    assert me["sign_in_methods"] == [
        {"provider": "github", "email": "ada@example.com", "login": "ada"},
        {"provider": "google", "email": "ada.work@example.org", "login": None},
    ]


def test_a_connected_account_leaves_with_its_user(app, settings, browser, providers) -> None:
    """The beta list admits users: once the user's email leaves it, no method signs in."""
    browser.sign_in("github")
    providers.google_account(subject="2001", email="ada.work@example.org")
    browser.connect("google")
    browser.sign_out()
    app.state.settings = settings.model_copy(update={"beta_allowlist": frozenset()})

    callback = browser.sign_in("google")

    assert callback.headers["location"] == "/signin?error=denied"
    assert browser.get("/api/v1/auth/denied").json()["email"] == "ada.work@example.org"


def test_connect_returns_to_next(browser) -> None:
    browser.sign_in("github")

    callback = browser.connect("google", next_path="/settings/sign-in?from=banner")

    assert callback.headers["location"] == "/settings/sign-in?from=banner"


def test_connect_to_the_dev_user(browser) -> None:
    browser.post("/api/v1/auth/dev", headers=ORIGIN)

    assert browser.connect("github").headers["location"] == "/settings/sign-in"
    assert browser.me().json()["providers"] == ["github"]


def test_connect_an_account_of_another_user(browser, other_browser, sql, caplog) -> None:
    browser.sign_in("github")
    other_browser.post("/api/v1/auth/dev", headers=ORIGIN)

    with caplog.at_level(logging.WARNING):
        callback = other_browser.connect("github")

    assert callback.headers["location"] == "/settings/sign-in?error=taken"
    assert "the account signs in to another user" in caplog.text
    assert other_browser.me().json()["providers"] == []
    assert len(sql("SELECT subject FROM identities")) == 1


def test_connect_an_account_the_user_has_already(browser, sql) -> None:
    browser.sign_in("github")

    callback = browser.connect("github")

    assert callback.headers["location"] == "/settings/sign-in"
    assert browser.me().json()["providers"] == ["github"]
    assert len(sql("SELECT subject FROM identities")) == 1


def test_connect_a_second_account_of_a_provider(browser, providers) -> None:
    browser.sign_in("github")
    providers.github_account(subject=43, login="ada-alt")

    callback = browser.connect("github")

    assert callback.headers["location"] == "/settings/sign-in?error=failed"
    assert browser.me().json()["providers"] == ["github"]


def test_a_connect_cancelled_at_the_provider(browser) -> None:
    browser.sign_in("github")
    start = browser.start("google", intent="connect")

    callback = browser.callback("google", error="access_denied", state=browser.state_of(start))

    assert callback.headers["location"] == "/settings/sign-in?error=failed"
    assert browser.me().json()["providers"] == ["github"]


def test_a_connect_whose_code_the_provider_refuses(browser, providers) -> None:
    browser.sign_in("github")
    start = browser.start("google", intent="connect")
    providers.challenge = "another"  # the token request fails the PKCE check

    callback = browser.callback("google", code="the-code", state=browser.state_of(start))

    assert callback.headers["location"] == "/settings/sign-in?error=failed"


def test_an_expired_connect_returns_to_settings(browser, forget_pending) -> None:
    browser.sign_in("github")
    start = browser.start("google", intent="connect")
    forget_pending()

    callback = browser.callback("google", code="the-code", state=browser.state_of(start))

    assert callback.headers["location"] == "/settings/sign-in?error=failed"


def _connect_after(browser, provider: str, meanwhile) -> object:
    """Starts connecting `provider`, runs `meanwhile` while the browser is at the provider, then
    finishes the connect; the callback's response."""
    start = browser.start(provider, intent="connect")
    meanwhile()
    return browser.callback(provider, code="the-code", state=browser.state_of(start))


def _session_ended(callback, caplog) -> None:
    assert callback.headers["location"] == "/settings/sign-in?error=failed"
    assert "session" not in cookies_set(callback)
    assert "the session that started the connect ended" in caplog.text


def test_a_connect_after_signing_out(browser, sql, caplog) -> None:
    browser.sign_in("github")

    with caplog.at_level(logging.WARNING):
        callback = _connect_after(browser, "google", browser.sign_out)

    _session_ended(callback, caplog)
    assert sql("SELECT provider FROM identities") == [("github",)]


def test_a_connect_of_a_stolen_session_after_signing_out_everywhere(
    browser, other_browser, providers, sql, caplog
) -> None:
    """Signing out everywhere also stops a connect that a stolen session started: the thief
    cannot keep a way to sign in."""
    browser.sign_in("github")
    other_browser.set_cookie("session", browser.cookie("session"))
    providers.google_account(subject="666", email="thief@example.org")

    def sign_out_everywhere() -> None:
        browser.post("/api/v1/auth/sign-out-everywhere", headers=ORIGIN)

    with caplog.at_level(logging.WARNING):
        callback = _connect_after(other_browser, "google", sign_out_everywhere)

    _session_ended(callback, caplog)
    assert sql("SELECT provider FROM identities") == [("github",)]


def test_a_connect_after_signing_in_as_another_user(browser, sql, caplog) -> None:
    browser.sign_in("github")

    def sign_in_as_the_dev_user() -> None:
        browser.sign_out()
        browser.post("/api/v1/auth/dev", headers=ORIGIN)

    with caplog.at_level(logging.WARNING):
        callback = _connect_after(browser, "google", sign_in_as_the_dev_user)

    _session_ended(callback, caplog)
    assert browser.me().json()["providers"] == []
    assert sql("SELECT provider FROM identities") == [("github",)]


def test_a_connect_of_a_deleted_user(browser, sql, caplog) -> None:
    browser.sign_in("github")

    def delete_the_account() -> None:
        browser.delete("/api/v1/me", headers=ORIGIN)

    with caplog.at_level(logging.WARNING):
        callback = _connect_after(browser, "google", delete_the_account)

    _session_ended(callback, caplog)
    assert sql("SELECT provider FROM identities") == []


def test_a_connect_with_another_session_of_the_user(browser, other_browser, caplog) -> None:
    """Only the session that started a connect finishes it."""
    browser.sign_in("github")
    other_browser.sign_in("github")
    start = browser.start("google", intent="connect")
    other_browser.set_cookie("sign_in_state", browser.cookie("sign_in_state"))

    with caplog.at_level(logging.WARNING):
        callback = other_browser.callback("google", code="the-code", state=browser.state_of(start))

    _session_ended(callback, caplog)
    assert other_browser.me().json()["providers"] == ["github"]


def test_a_connect_slides_the_session_on_at_the_callback(browser, monkeypatch) -> None:
    browser.sign_in("github")
    start = browser.start("google", intent="connect")
    moved = datetime.now(UTC) + timedelta(days=2)
    monkeypatch.setattr(service, "_now", lambda: moved)

    callback = browser.callback("google", code="the-code", state=browser.state_of(start))

    assert callback.headers["location"] == "/settings/sign-in"
    assert "Max-Age=2592000" in cookies_set(callback)["session"]
    assert browser.me().json()["providers"] == ["github", "google"]


def test_a_connect_that_loses_a_race_fails(browser, other_browser, monkeypatch, caplog) -> None:
    browser.sign_in("github")
    other_browser.post("/api/v1/auth/dev", headers=ORIGIN)

    # The GitHub account was connected to the user who signed in with it after the dev user's
    # connect looked for it.
    async def no_identity(_store, _provider: str, _subject: str) -> None:
        return None

    monkeypatch.setattr(store.AccountStore, "identity", no_identity)
    with caplog.at_level(logging.ERROR):
        callback = other_browser.connect("github")

    assert callback.headers["location"] == "/settings/sign-in?error=failed"
    assert "Postgres failed (IntegrityError)" in caplog.text


def test_connect_without_a_session_signs_in_first(browser) -> None:
    start = browser.start("google", intent="connect")

    assert start.status_code == 302
    assert start.headers["location"] == "/signin?next=/settings/sign-in"
    assert "set-cookie" not in start.headers


def test_connect_with_a_session_that_ended(browser) -> None:
    browser.set_cookie("session", "made-up-token")

    start = browser.start("google", "/settings/sign-in?from=banner", intent="connect")

    assert start.headers["location"] == "/signin?next=/settings/sign-in%3Ffrom%3Dbanner"


def test_connect_without_postgres_fails(browser_without_postgres, caplog) -> None:
    browser_without_postgres.set_cookie("session", "some-token")

    with caplog.at_level(logging.ERROR):
        start = browser_without_postgres.start("google", intent="connect")

    assert start.headers["location"] == "/settings/sign-in?error=failed"
    assert "Sign-in with google failed: Postgres failed" in caplog.text


def test_connect_slides_the_session_on(browser, monkeypatch) -> None:
    browser.sign_in("github")
    moved = datetime.now(UTC) + timedelta(days=20)
    monkeypatch.setattr(service, "_now", lambda: moved)

    start = browser.start("google", intent="connect")

    assert urlsplit(start.headers["location"]).netloc == "accounts.google.com"
    assert "Max-Age=2592000" in cookies_set(start)["session"]


# --- Removing a sign-in method ---------------------------------------------------------------


def test_disconnect(browser) -> None:
    browser.sign_in("github")
    browser.connect("google")

    response = browser.delete("/api/v1/me/sign-in-methods/github", headers=ORIGIN)

    assert response.status_code == 204
    assert browser.me().json()["providers"] == ["google"]


def test_a_removed_sign_in_method_comes_back_with_the_users_email(browser, sql) -> None:
    """Removing a method deletes its identity only: the email links a user's providers, so
    signing in with it again adds it again (the decided behaviour, as in sign-in)."""
    browser.sign_in("github")
    me = browser.me().json()
    browser.connect("google")
    browser.delete("/api/v1/me/sign-in-methods/github", headers=ORIGIN)
    assert sql("SELECT provider FROM identities") == [("google",)]
    browser.sign_out()

    callback = browser.sign_in("github")

    assert callback.headers["location"] == "/dashboard"
    assert browser.me().json()["id"] == me["id"]
    assert browser.me().json()["providers"] == ["github", "google"]
    assert len(sql("SELECT id FROM users")) == 1


def test_a_removed_sign_in_method_with_another_email_signs_in_as_a_new_user(
    browser, providers, sql
) -> None:
    """A connected account whose email is not the user's has nothing to link it once removed."""
    browser.sign_in("github")
    me = browser.me().json()
    providers.google_account(subject="2001", email="ada.work@example.org")
    browser.connect("google")
    browser.delete("/api/v1/me/sign-in-methods/google", headers=ORIGIN)
    browser.sign_out()

    callback = browser.sign_in("google")

    # A new user, whom the beta list turns away like any other new account.
    assert callback.headers["location"] == "/signin?error=denied"
    assert sql(f"SELECT provider FROM identities WHERE user_id = '{me['id']}'") == [("github",)]
    assert len(sql("SELECT id FROM users")) == 1


def test_the_last_sign_in_method_stays(browser) -> None:
    browser.sign_in("github")

    response = browser.delete("/api/v1/me/sign-in-methods/github", headers=ORIGIN)

    assert response.status_code == 409
    assert response.json()["type"] == PROBLEMS + "last-sign-in-method"
    assert response.json()["detail"].startswith("GitHub is the only way to sign in")
    assert browser.me().json()["providers"] == ["github"]


def test_disconnect_a_method_the_user_does_not_have(browser) -> None:
    browser.sign_in("github")

    response = browser.delete("/api/v1/me/sign-in-methods/google", headers=ORIGIN)

    assert response.status_code == 404
    assert response.json()["type"] == PROBLEMS + "not-found"
    assert response.json()["detail"] == "Your account does not sign in with Google."


def test_disconnect_needs_the_apps_origin(browser) -> None:
    browser.sign_in("github")
    browser.connect("google")

    response = browser.delete(
        "/api/v1/me/sign-in-methods/github", headers={"Origin": "https://evil.example"}
    )

    assert response.status_code == 403
    assert browser.me().json()["providers"] == ["github", "google"]


# --- Signing out everywhere ------------------------------------------------------------------


def test_sign_out_everywhere(browser, other_browser, third_browser, sql) -> None:
    browser.sign_in("github")
    other_browser.sign_in("github")
    third_browser.post("/api/v1/auth/dev", headers=ORIGIN)

    response = browser.post("/api/v1/auth/sign-out-everywhere", headers=ORIGIN)

    assert response.status_code == 204
    assert cookies_set(response)["session"].startswith('session=""')
    assert browser.me().status_code == 401
    assert other_browser.me().status_code == 401
    # Another user's sessions stay.
    assert third_browser.me().status_code == 200
    assert len(sql("SELECT token_hash FROM sessions")) == 1


# --- Deleting the account --------------------------------------------------------------------


def test_delete_account(app, browser, other_browser, third_browser, sql) -> None:
    deleted: list[tuple[str, str, int]] = []

    async def users(db: AsyncSession, user_id: str) -> int:
        return await db.scalar(text("SELECT count(*) FROM users WHERE id = :id"), {"id": user_id})

    async def hook(user_id: str, db: AsyncSession) -> AfterDeletion:
        # In the deletion's transaction, before the user's row goes.
        deleted.append(("rows", user_id, await users(db, user_id)))

        async def after() -> None:  # once the deletion is committed
            deleted.append(("files", user_id, await users(db, user_id)))

        return after

    app.state.account_deletion_hooks = (hook,)
    browser.sign_in("github")
    browser.connect("google")
    other_browser.sign_in("github")
    browser.patch("/api/v1/me/preferences/appearance", json={"theme": "light"}, headers=ORIGIN)
    third_browser.post("/api/v1/auth/dev", headers=ORIGIN)
    user_id = browser.me().json()["id"]

    response = browser.delete("/api/v1/me", headers=ORIGIN)

    assert response.status_code == 204
    assert cookies_set(response)["session"].startswith('session=""')
    assert deleted == [("rows", user_id, 1), ("files", user_id, 0)]
    assert sql(f"SELECT id FROM users WHERE id = '{user_id}'") == []
    assert sql("SELECT provider FROM identities") == []
    assert sql("SELECT user_id FROM user_preferences") == []
    assert other_browser.me().status_code == 401
    # Another user stays.
    assert third_browser.me().status_code == 200
    assert len(sql("SELECT token_hash FROM sessions")) == 1


def test_a_failing_deletion_hook_deletes_nothing(app, browser, sql) -> None:
    async def hook(_user_id: str, _db: AsyncSession) -> None:
        raise RuntimeError("the model files could not be removed")

    app.state.account_deletion_hooks = (hook,)
    browser.sign_in("github")

    response = browser.delete("/api/v1/me", headers=ORIGIN)

    assert response.status_code == 500
    assert response.json()["type"] == PROBLEMS + "internal-error"
    assert browser.me().status_code == 200
    assert len(sql("SELECT id FROM users")) == 1


def test_a_failure_after_the_deletion_still_deletes_the_account(app, browser, sql, caplog) -> None:
    async def hook(_user_id: str, _db: AsyncSession) -> AfterDeletion:
        async def after() -> None:
            raise OSError("the model files could not be removed")

        return after

    app.state.account_deletion_hooks = (hook,)
    browser.sign_in("github")

    with caplog.at_level(logging.ERROR):
        response = browser.delete("/api/v1/me", headers=ORIGIN)

    assert response.status_code == 204
    assert "Deleting an account's data after the commit failed (OSError)" in caplog.text
    assert browser.me().status_code == 401
    assert sql("SELECT id FROM users") == []


def test_a_deleted_account_signs_in_as_a_new_user(browser) -> None:
    browser.sign_in("github")
    first = browser.me().json()["id"]
    browser.delete("/api/v1/me", headers=ORIGIN)

    browser.sign_in("github")

    assert browser.me().json()["id"] != first
