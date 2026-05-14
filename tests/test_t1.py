from unittest.mock import MagicMock, patch, PropertyMock
import pytest
from sdk.models import Calls, Puts, LegState
from sdk.order_manager import OrderManager


@pytest.fixture
def mock_ws():
    ws = MagicMock()
    ws.ltp = {}
    return ws


@pytest.fixture
def mock_symbols():
    sym = MagicMock()
    sym.filter_by_moneyness.return_value = [{
        "ws_token": "1002",
        "tradingsymbol": "BTC-28MAR25-50000-CE",
        "strike": 50000,
    }]
    return sym


@pytest.fixture
def mock_api():
    api = MagicMock()
    broker = MagicMock()
    broker.orders = []
    api.api.return_value = broker
    return api


@pytest.fixture
def om(mock_ws, mock_symbols, mock_api):
    config = {"quantity": 1, "stop_loss": 500, "target": 1000, "slippage": 0.5}
    return OrderManager(ws=mock_ws, symbols=mock_symbols, api=mock_api, config=config)


@pytest.fixture
def cs(om, mock_api, mock_symbols):
    from strategies.coinshort import Coinshort
    cs = Coinshort(
        config={"stop_loss": 500, "target": 1000, "ttl": 60},
        symbols=mock_symbols,
        api=mock_api,
        om=om,
        underlying_token=1001,
        underlying_symbol="BTC-USD",
    )
    cs.upper_bound = 0
    cs._entry_ce_id = None
    cs._entry_pe_id = None
    cs.ce = Calls()
    cs.pe = Puts()
    return cs


class TestEnterStraddle:
    def test_places_both_legs(self, cs, om):
        om.enter_short = MagicMock()
        om.enter_short.return_value = {
            "symbol": "BTC-50000-CE", "token": "1002", "strike": 50000,
            "price": 150.0, "short_id": "s1", "sl_id": "b1",
        }
        cs._enter_straddle(50000)
        assert cs._entry_ce_id == "s1"
        assert cs._entry_pe_id == "s1"
        assert om.enter_short.call_count == 2

    def test_skips_pe_on_ce_failure(self, cs, om):
        om.enter_short = MagicMock()
        om.enter_short.return_value = {"error": "no_quote"}
        cs._enter_straddle(50000)
        assert cs._entry_ce_id is None


class TestTickEntry:
    def test_enters_straddle_on_first_tick(self, cs):
        cs.upper_bound = 0
        with patch.object(cs, '_enter_straddle') as mock:
            cs.tick(50000)
            mock.assert_called_once_with(50000)

    def test_skips_entry_when_bounds_exist(self, cs):
        cs.upper_bound = 51000
        cs.lower_bound = 49000
        with patch.object(cs, '_enter_straddle') as mock:
            cs.tick(50000)
            mock.assert_not_called()

    def test_waits_for_fill(self, cs):
        cs.upper_bound = 0
        cs._entry_ce_id = "ce1"
        cs._entry_pe_id = "pe1"
        with patch.object(cs, '_is_order_complete', return_value=False):
            with patch.object(cs, '_finalize_entry') as mock:
                cs.tick(50000)
                mock.assert_not_called()

    def test_finalizes_when_both_filled(self, cs):
        cs.upper_bound = 0
        cs._entry_ce_id = "ce1"
        cs._entry_pe_id = "pe1"
        with patch.object(cs, '_is_order_complete', side_effect=[True, True]):
            with patch.object(cs, '_finalize_entry') as mock:
                cs.tick(50000)
                mock.assert_called_once_with(50000)


class TestFinalizeEntry:
    def test_calculates_bounds(self, cs):
        cs._entry_ce_id = "ce1"
        cs._entry_pe_id = "pe1"
        cs.api.find_fillprice_from_order_id = MagicMock(side_effect=[150.0, 120.0])
        cs._finalize_entry(50000)
        assert cs.current_premium == 270.0
        assert cs.upper_bound == 50270.0
        assert cs.lower_bound == 49730.0
        assert cs._entry_ce_id is None

    def test_skips_if_price_not_available(self, cs):
        cs._entry_ce_id = "ce1"
        cs.api.find_fillprice_from_order_id = MagicMock(return_value=0.0)
        cs._finalize_entry(50000)
        assert cs.current_premium == 0

    def test_sets_legs_to_short(self, cs):
        cs._entry_ce_id = "ce1"
        cs._entry_pe_id = "pe1"
        cs.api.find_fillprice_from_order_id = MagicMock(side_effect=[150.0, 120.0])
        cs._finalize_entry(50000)
        assert cs.ce.status == LegState.SHORT
        assert cs.pe.status == LegState.SHORT


class TestManagerT1:
    def test_short_to_long_on_sl_hit(self, om):
        opt = Calls()
        opt.status = LegState.SHORT
        opt.buy_id = "b1"
        opt.buy_params = {"trigger_price": 50100, "price": 150.0}
        opt.tradingsymbol = "BTC-CE"
        broker = om.api.api()
        broker.orders = [{"order_id": "b1", "status": "COMPLETE"}]
        om.manage_leg(opt, {})
        assert opt.status == LegState.LONG
        assert opt.buy_params["price"] == 50100
        assert opt.buy_params["target"] == 50100 + om.target

    def test_no_change_when_sl_not_hit(self, om):
        opt = Calls()
        opt.status = LegState.SHORT
        opt.buy_id = "b1"
        opt.buy_params = {"price": 150.0}
        broker = om.api.api()
        broker.orders = [{"order_id": "b1", "status": "TRIGGER PENDING"}]
        om.manage_leg(opt, {})
        assert opt.status == LegState.SHORT

    def test_long_does_nothing(self, om):
        opt = Calls()
        opt.status = LegState.LONG
        om.manage_leg(opt, {})
        assert opt.status == LegState.LONG

    def test_long_to_short_on_sl_hit(self, om):
        opt = Calls()
        opt.status = LegState.LONG
        opt.buy_id = "b1"
        opt.buy_params = {"trigger_price": 49500, "price": 50100}
        opt.tradingsymbol = "BTC-CE"
        broker = om.api.api()
        broker.orders = [{"order_id": "b1", "status": "COMPLETE"}]
        om.manage_leg(opt, {})
        assert opt.status == LegState.SHORT
        assert "target" not in opt.buy_params


class TestT2Trigger:
    def test_t2_upper_when_price_above_and_call_long(self, cs):
        cs.upper_bound = 51000
        cs.lower_bound = 49000
        cs.ce.status = LegState.LONG
        cs.pe.status = LegState.SHORT
        cs.tier = 1
        with patch.object(cs, 't_upper_protocol') as mock:
            cs.tick(51500)
            assert cs.tier == 2
            mock.assert_called_once()

    def test_no_t2_when_call_not_long(self, cs):
        cs.upper_bound = 51000
        cs.lower_bound = 49000
        cs.ce.status = LegState.SHORT
        cs.tier = 1
        with patch.object(cs, 't_upper_protocol') as mock:
            cs.tick(51500)
            assert cs.tier == 1
            mock.assert_not_called()

    def test_no_t2_when_price_within_bounds(self, cs):
        cs.upper_bound = 51000
        cs.lower_bound = 49000
        cs.ce.status = LegState.LONG
        cs.tier = 1
        with patch.object(cs, 't_upper_protocol') as mock:
            cs.tick(50500)
            mock.assert_not_called()

    def test_t2_lower_when_price_below_and_put_long(self, cs):
        cs.upper_bound = 51000
        cs.lower_bound = 49000
        cs.pe.status = LegState.LONG
        cs.ce.status = LegState.SHORT
        cs.tier = 1
        with patch.object(cs, 't_lower_protocol') as mock:
            cs.tick(48500)
            assert cs.tier == 2
            mock.assert_called_once()
