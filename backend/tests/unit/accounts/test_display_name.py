from candlestack.accounts.oauth import ProviderAccount
from candlestack.accounts.schemas import DISPLAY_NAME_MAX, MeUpdate, Provider
from candlestack.accounts.service import provider_display_name


def account(*, name: str | None, login: str | None = None) -> ProviderAccount:
    return ProviderAccount(
        provider=Provider.google,
        subject="1077",
        email="ada@example.com",
        name=name,
        login=login,
    )


def test_the_providers_name() -> None:
    assert provider_display_name(account(name="  Ada Lovelace ")) == "Ada Lovelace"


def test_a_long_name_is_cut_to_what_the_user_may_save() -> None:
    name = provider_display_name(account(name="Ada " + "L" * 200))

    assert len(name) == DISPLAY_NAME_MAX
    assert MeUpdate(display_name=name).display_name == name


def test_a_cut_does_not_end_in_whitespace() -> None:
    name = provider_display_name(account(name="A" * (DISPLAY_NAME_MAX - 1) + " Lovelace"))

    assert name == "A" * (DISPLAY_NAME_MAX - 1)


def test_without_a_name_the_login() -> None:
    assert provider_display_name(account(name=" ", login="ada")) == "ada"


def test_without_a_name_or_login_the_emails_local_part() -> None:
    assert provider_display_name(account(name=None)) == "ada"
