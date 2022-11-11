from re import compile
from urllib.parse import quote
from json import loads
from http.cookies import SimpleCookie

from aiohttp import ClientSession
from yarl import URL

from .guard import SteamGuardMixin
from .confirmation import ConfirmationMixin
from .login import LoginMixin
from .trade import TradeMixin
from .inventory import InventoryMixin
from .market import MarketMixin

from .models import STEAM_URL, Currency, Notifications
from .exceptions import ApiError
from .utils import get_cookie_value_from_session

__all__ = ("SteamClient",)

API_KEY_RE = compile(r"<p>Key: (?P<api_key>[0-9A-F]+)</p>")
WALLET_INFO_RE = compile(r"g_rgWalletInfo = (?P<info>.+);")
TRADE_TOKEN_RE = compile(r"\d+&token=(?P<token>.+)\" readonly")

API_KEY_CHECK_STR = "<h2>Access Denied</h2>"
API_KEY_CHECK_STR1 = "You must have a validated email address to create a Steam Web API key"
STEAM_LANG_COOKIE = "Steam_Language"
DEF_LANG = "english"


# TODO find a better way to type mixins, and separate methods.
class SteamClient(SteamGuardMixin, ConfirmationMixin, LoginMixin, InventoryMixin, MarketMixin):
    """
    Base class in hierarchy ...
    """

    __slots__ = (
        "_is_logged",
        "session",
        "username",
        "steam_id",
        "_password",
        "_shared_secret",
        "_identity_secret",
        "_api_key",
        "trade_token",
        "_device_id",
        "_listings_confs_ident",
        "_listings_confs",
        "_trades_confs",
        "_steam_fee",
        "_publisher_fee",
    )

    def __init__(
        self,
        username: str,
        password: str,
        steam_id: int,
        *,
        shared_secret: str,
        identity_secret: str,
        api_key: str = None,
        trade_token: str = None,
        steam_fee=0.05,
        publisher_fee=0.1,
        lang=DEF_LANG,
        tz_offset=0.0,
        session: ClientSession = None,
    ):

        self.session = session or ClientSession(raise_for_status=True)
        # admit about raise for status and strange behaviour if opposite in docs.
        self.username = username
        self.steam_id = steam_id  # steam id64
        self.trade_token = trade_token

        self._password = password
        self._shared_secret = shared_secret
        self._identity_secret = identity_secret
        self._api_key = api_key
        self._steam_fee = steam_fee
        self._publisher_fee = publisher_fee

        super().__init__()

        self._set_init_cookies(lang, tz_offset)

    @property
    def steam_id32(self) -> int:
        return self.steam_id & 0xFFFFFFFF

    @property
    def trade_url(self) -> URL | None:
        if self.trade_token:
            return (STEAM_URL.COMMUNITY / "tradeoffer/new/").with_query(
                {"partner": self.steam_id32, "token": self.trade_token}
            )

    @property
    def profile_url(self) -> URL:
        return STEAM_URL.COMMUNITY / f"profiles/{self.steam_id}"

    @property
    def language(self) -> str:
        return get_cookie_value_from_session(self.session, STEAM_URL.STORE, STEAM_LANG_COOKIE) or DEF_LANG

    def _set_init_cookies(self, lang: str, tz_offset: float):
        urls = (STEAM_URL.COMMUNITY, STEAM_URL.STORE, STEAM_URL.HELP)
        for url in urls:
            c = SimpleCookie()
            c[STEAM_LANG_COOKIE] = lang
            c[STEAM_LANG_COOKIE]["path"] = "/"
            c[STEAM_LANG_COOKIE]["domain"] = url.host
            c[STEAM_LANG_COOKIE]["secure"] = True

            self.session.cookie_jar.update_cookies(cookies=c, response_url=url)

        c_key = "timezoneOffset"
        for url in urls:
            c = SimpleCookie()
            c[c_key] = str(tz_offset).replace(".", ",")
            c[c_key]["path"] = "/"
            c[c_key]["domain"] = url.host
            c[c_key]["SameSite"] = True

            self.session.cookie_jar.update_cookies(cookies=c, response_url=url)

    async def _init_data(self):
        if not self._api_key:
            self._api_key = await self._fetch_api_key()
            not self._api_key and await self.register_new_api_key()

        if not self.trade_token:
            self.trade_token = await self._fetch_trade_token()
            not self.trade_token and await self.register_new_trade_url()

        if not self._steam_fee or not self._publisher_fee:
            wallet_info = await self._fetch_wallet_info()
            if not self._steam_fee:
                self._steam_fee = float(wallet_info["wallet_fee_percent"])
            if not self._publisher_fee:
                self._publisher_fee = float(wallet_info["wallet_publisher_fee_percent_default"])

    async def _fetch_wallet_info(self) -> dict[str, str | int]:
        r = await self.session.get(self.profile_url / "inventory", headers={"Referer": self.profile_url.human_repr()})
        rt = await r.text()
        info: dict = loads(WALLET_INFO_RE.search(rt)["info"])
        if not info.get("success"):
            raise ApiError("Failed to fetch wallet info", info)
        return info

    async def get_wallet_balance(self) -> tuple[float, Currency]:
        """
        Fetch wallet balance and currency.

        :return: tuple of balance and `Currency`
        """

        r = await self.session.get(STEAM_URL.STORE / "api/getfundwalletinfo")
        rj = await r.json()
        if not rj.get("success"):
            raise ApiError("Failed to fetch wallet info", rj)

        return int(rj["user_wallet"]["amount"]) / 100, Currency.by_name(rj["user_wallet"]["currency"])

    async def register_new_trade_url(self) -> URL:
        """
        Register new trade url. Cache token.

        :return: trade url
        """

        r = await self.session.post(
            self.profile_url / "tradeoffers/newtradeurl",
            data={"sessionid": self.session_id},
        )
        token: str = await r.json()

        self.trade_token = quote(token, safe="~()*!.'")  # https://stackoverflow.com/a/72449666/19419998
        return self.trade_url

    async def _fetch_trade_token(self) -> str | None:
        r = await self.session.get(self.profile_url / "tradeoffers/privacy")
        rt = await r.text()

        search = TRADE_TOKEN_RE.search(rt)
        return search["token"] if search else None

    async def _fetch_api_key(self) -> str | None:
        r = await self.session.get(STEAM_URL.COMMUNITY / "dev/apikey")
        rt = await r.text()
        if API_KEY_CHECK_STR in rt or API_KEY_CHECK_STR1 in rt:
            raise ApiError(API_KEY_CHECK_STR1)

        search = API_KEY_RE.search(rt)
        return search["api_key"] if search else None

    async def register_new_api_key(self, domain=STEAM_URL.COMMUNITY.human_repr()) -> str:
        """
        Register new api key, cache it and return.

        :param domain: On which domain api key will be registered. Default - `steamcommunity`
        :return: api key
        """

        data = {
            "domain": domain,
            "agreeToTerms": "agreed",
            "sessionid": self.session_id,
            "Submit": "Register",
        }
        r = await self.session.post(STEAM_URL.COMMUNITY / "dev/registerkey", data=data)
        rt = await r.text()

        self._api_key = API_KEY_RE.search(rt)["api_key"]
        return self._api_key

    async def get_notifications(self) -> Notifications:
        """Get notifications count."""

        headers = {"Referer": self.profile_url.human_repr()}
        r = await self.session.get(STEAM_URL.COMMUNITY / "actions/GetNotificationCounts", headers=headers)
        rj = await r.json()
        return Notifications(*(rj["notifications"][str(i)] for i in range(1, 12) if i != 7))

    def reset_items_notifications(self):
        """Fetching your inventory page, which resets new items notifications to 0."""

        return self.session.get(self.profile_url / "inventory/")
