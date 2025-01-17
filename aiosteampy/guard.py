from typing import TYPE_CHECKING
from time import time as time_time

from .utils import gen_two_factor_code, generate_confirmation_key, generate_device_id, async_throttle

if TYPE_CHECKING:
    from .client import SteamClient

__all__ = ("SteamGuardMixin",)


class SteamGuardMixin:
    """
    Mixin with Steam Guard related methods.
    """

    __slots__ = ()

    def __init__(self, *args, **kwargs):
        self.device_id = generate_device_id(self.steam_id)
        super().__init__(*args, **kwargs)

    @property
    def two_factor_code(self: "SteamClient") -> str:
        return gen_two_factor_code(self._shared_secret)

    @async_throttle(1, arg_name="tag")
    async def gen_confirmation_key(self: "SteamClient", *, tag: str) -> tuple[str, int]:
        ts = int(time_time())
        return generate_confirmation_key(self._identity_secret, tag, ts), ts
