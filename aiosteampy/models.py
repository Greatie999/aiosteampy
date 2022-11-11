from enum import Enum
from dataclasses import dataclass, field
from typing import Literal, TypeAlias, ClassVar
from datetime import datetime

from yarl import URL

from .utils import create_ident_code


class STEAM_URL:
    API = URL("https://api.steampowered.com")
    COMMUNITY = URL("https://steamcommunity.com")
    STORE = URL("https://store.steampowered.com")
    HELP = URL("https://help.steampowered.com")
    INSPECT = URL("steam://rungame/730/76561202255233023")
    STATIC = URL("https://community.akamai.steamstatic.com")


# https://stackoverflow.com/a/54732120/19419998
class Game(Enum):
    CSGO = 730, 2
    DOTA2 = 570, 2
    H1Z1 = 433850, 2
    RUST = 252490, 2
    TF2 = 440, 2
    PUBG = 578080, 2

    STEAM = 753, 6  # not actually a game :)

    _steam_id_map: ClassVar[dict[int, "Game"]]

    def __new__(cls, *args, **kwargs):
        obj = object.__new__(cls)
        obj._value_ = args[0]
        return obj

    def __init__(self, _, context_id):
        self._context_id_ = context_id
        self._args_tuple_ = (self._value_, self._context_id_)

    @property
    def context_id(self) -> int:
        return self._context_id_

    @property
    def app_id(self) -> int:
        return self._value_

    @classmethod
    def by_steam_id(cls, steam_id: int) -> "Game | None":
        return cls._steam_id_map.get(steam_id)

    def __getitem__(self, index: int) -> int:
        return self._args_tuple_[index]

    def __iter__(self):  # for unpacking
        return iter(self._args_tuple_)


Game._steam_id_map = {g.value: g for g in Game.__members__.values()}

GameType: TypeAlias = Game | tuple[int, int]


class Currency(Enum):
    # https://partner.steamgames.com/doc/store/pricing/currencies

    USD = 1  # UnitedStates Dollar
    GBP = 2  # United Kingdom Pound
    EURO = 3  # European Union Euro
    CHF = 4  # Swiss Francs
    RUB = 5  # Russian Rouble
    PLN = 6  # Polish Złoty
    BRL = 7  # Brazilian Reals
    JPY = 8  # Japanese Yen
    NOK = 9  # Norwegian Krone
    IDR = 10  # Indonesian Rupiah
    MYR = 11  # Malaysian Ringgit
    PHP = 12  # Philippine Peso
    SGD = 13  # Singapore Dollar
    THB = 14  # Thai Baht
    VND = 15  # Vietnamese Dong
    KRW = 16  # South KoreanWon
    TRY = 17  # Turkish Lira
    UAH = 18  # Ukrainian Hryvnia
    MXN = 19  # Mexican Peso
    CAD = 20  # Canadian Dollars
    AUD = 21  # Australian Dollars
    NZD = 22  # New Zealand Dollar
    CNY = 23  # Chinese Renminbi (yuan)
    INR = 24  # Indian Rupee
    CLP = 25  # Chilean Peso
    PEN = 26  # Peruvian Sol
    COP = 27  # Colombian Peso
    ZAR = 28  # South AfricanRand
    HKD = 29  # Hong KongDollar
    TWD = 30  # New TaiwanDollar
    SAR = 31  # Saudi Riyal
    AED = 32  # United ArabEmirates Dirham
    # SEK = 33  # Swedish Krona
    ARS = 34  # Argentine Peso
    ILS = 35  # Israeli NewShekel
    # BYN = 36  # Belarusian Ruble
    KZT = 37  # Kazakhstani Tenge
    KWD = 38  # Kuwaiti Dinar
    QAR = 39  # Qatari Riyal
    CRC = 40  # Costa Rican Colón
    UYU = 41  # Uruguayan Peso
    # BGN = 42  # Bulgarian Lev
    # HRK = 43  # Croatian Kuna
    # CZK = 44  # Czech Koruna
    # DKK = 45  # Danish Krone
    # HUF = 46  # Hungarian Forint
    # RON = 47  # Romanian Leu

    _name_map: ClassVar[dict[str, "Currency"]]

    @classmethod
    def by_name(cls, name: str) -> "Currency":
        return cls._name_map[name]


Currency._name_map = {c.name: c for c in Currency.__members__.values()}


class TradeOfferState(Enum):
    INVALID = 1
    ACTIVE = 2
    ACCEPTED = 3
    COUNTERED = 4
    EXPIRED = 5
    CANCELED = 6
    DECLINED = 7
    INVALID_ITEMS = 8
    CONFIRMATION_NEED = 9
    CANCELED_BY_SECONDARY_FACTOR = 10
    STATE_IN_ESCROW = 11


@dataclass(eq=False, slots=True)
class ItemAction:
    link: str
    name: str


@dataclass(eq=False, slots=True)
class ItemDescription:
    value: str
    type: Literal["html"] = "html"  # just because
    color: str | None = None  # hexadecimal


@dataclass(eq=False, slots=True)
class ItemTag:
    category: str
    internal_name: str
    localized_category_name: str
    localized_tag_name: str
    color: str | None = None  # hexadecimal


@dataclass(eq=False, slots=True)
class ItemClass:
    id: int  # classid
    instance_id: int
    game: GameType

    name: str
    market_name: str
    market_hash_name: str

    type: str | None

    name_color: str | None  # hexadecimal
    background_color: str | None

    icon: str
    icon_large: str | None

    actions: tuple[ItemAction, ...]
    market_actions: tuple[ItemAction, ...]
    owner_actions: tuple[ItemAction, ...]
    tags: tuple[ItemTag, ...]
    descriptions: tuple[ItemDescription, ...]

    fraud_warnings: tuple[str]

    commodity: bool  # ?
    tradable: bool
    marketable: bool
    market_tradable_restriction: int | None = None
    market_buy_country_restriction: str | None = None
    market_fee_app: int | None = None
    market_marketable_restriction: int | None = None

    # optional csgo attrs
    d_id: int | None = field(init=False, default=None)

    def __post_init__(self):
        self.actions and self._set_d_id()

    def _set_d_id(self):
        for action in self.actions:
            if "Inspect" in action.name:
                self.d_id = int(action.link.split("%D")[1])
                break

    @property
    def class_id(self) -> int:
        return self.id

    @property
    def icon_url(self) -> URL:
        return STEAM_URL.STATIC / f"economy/image/{self.icon}/96fx96f"

    @property
    def icon_large_url(self) -> URL | None:
        return (STEAM_URL.STATIC / f"economy/image/{self.icon_large}/330x192") if self.icon_large else None

    def __eq__(self, other: "ItemClass"):
        return (self.id == other.id) and (self.game[0] == other.game[0]) and (self.game[1] == other.game[1])

    def __hash__(self):
        return self.id


@dataclass(eq=False, slots=True)
class EconItem:
    """
    Represents Steam economy item (inventories).
    """

    id: int  # The item's unique ID within its app+context.
    owner_id: int

    class_: ItemClass

    amount: int

    inspect_link: str | None = field(init=False, default=None)  # optimization 🚀
    ident_code: str = field(init=False, default=None)

    def __post_init__(self):
        self._set_ident_code()
        self.class_.d_id and self._set_inspect_url()

    def _set_inspect_url(self):
        url = STEAM_URL.INSPECT / f"+csgo_econ_action_preview S{self.owner_id}A{self.id}D{self.class_.d_id}"
        self.inspect_link = url.human_repr()

    def _set_ident_code(self):
        self.ident_code = create_ident_code(self.id, *self.class_.game)

    @property
    def asset_id(self) -> int:
        return self.id

    def __eq__(self, other: "EconItem"):
        return (self.id == other.id) and (self.class_ == other.class_)

    def __hash__(self):
        return hash(self.ident_code)


# https://github.com/DoctorMcKay/node-steamcommunity/blob/master/resources/EConfirmationType.js
class ConfirmationType(Enum):
    UNKNOWN = 1
    TRADE = 2
    LISTING = 3

    @classmethod
    def get(cls, v: int) -> "ConfirmationType":
        try:
            return cls(v)
        except ValueError:
            return cls.UNKNOWN


# https://github.com/DoctorMcKay/node-steamcommunity/wiki/CConfirmation
@dataclass(eq=False, slots=True)
class Confirmation:
    id: int
    nonce: str  # conf key
    creator_id: int  # trade/listing id
    creation_time: datetime

    type: ConfirmationType

    icon: str
    multi: bool  # ?
    headline: str
    summary: str
    warn: str | None  # ?

    _asset_ident_code: str | None = None  # only to map confirmation to sell listing


@dataclass(eq=False, slots=True)
class Notifications:
    trades: int = 0  # 1
    game_turns: int = 0  # 2
    moderator_messages: int = 0  # 3
    comments: int = 0  # 4
    items: int = 0  # 5
    invites: int = 0  # 6
    # 7 missing
    gifts: int = 0  # 8
    chats: int = 0  # 9
    help_request_replies: int = 0  # 10
    account_alerts: int = 0  # 11


class MarketListingStatus(Enum):
    NEED_CONFIRMATION = 17
    ACTIVE = 1


@dataclass(eq=False, slots=True)
class SellOrderItem(EconItem):
    # presented only on active listing

    market_id: int | None = None  # listing id
    unowned_id: int | None = None
    original_amount: int | None = None
    unowned_context_id: int | None = None

    def _set_inspect_url(self):
        url = STEAM_URL.INSPECT / f"+csgo_econ_action_preview M{self.market_id}A{self.id}D{self.class_.d_id}"
        self.inspect_link = url.human_repr()


@dataclass(eq=False, slots=True)
class BaseOrder:
    id: int  # listing/buy order id

    price: float

    def __hash__(self):
        return self.id


@dataclass(eq=False, slots=True)
class MarketListing(BaseOrder):
    lister_steam_id: int
    time_created: datetime

    item: SellOrderItem

    status: MarketListingStatus
    active: bool

    # fields that can be useful
    item_expired: int
    cancel_reason: int
    time_finish_hold: int

    @property
    def listing_id(self) -> int:
        return self.id

    @property
    def confirmed(self) -> bool:
        return self.status is MarketListingStatus.ACTIVE


@dataclass(eq=False, slots=True)
class BuyOrder(BaseOrder):
    item_class: ItemClass

    quantity: int
    quantity_remaining: int

    @property
    def buy_order_id(self) -> int:
        return self.id
