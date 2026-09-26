import httpx
import pytest

from trade_simulator.adapters.sp500_universe import Sp500Universe
from trade_simulator.core.errors import MarketDataError

CSV = "Symbol,Security,GICS Sector\nMMM,3M,Industrials\nbrk.b,Berkshire,Financials\n"


def test_symbols_are_read_from_csv_and_upper_cased():
    universe = Sp500Universe(transport=httpx.MockTransport(lambda r: httpx.Response(200, text=CSV)))

    assert universe.symbols() == frozenset({"MMM", "BRK.B"})


def test_download_failure_is_a_market_data_error():
    universe = Sp500Universe(transport=httpx.MockTransport(lambda r: httpx.Response(500)))

    with pytest.raises(MarketDataError):
        universe.symbols()
