from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CURRENCY_DOLLAR
import yfinance as yf
import logging

_LOGGER = logging.getLogger(__name__)

def setup_platform(hass, config, add_entities, discovery_info=None):
    stocks = config.get("stocks", [])
    individual_sensors = []
    aggregate_data = {}
    total_portfolio_data = []

    for stock_config in stocks:
        # Create individual per-account sensors
        sensor = StockSensor(stock_config)
        individual_sensors.append(sensor)

        # Collect data per symbol for aggregation
        symbol = stock_config["symbol"]
        if symbol not in aggregate_data:
            aggregate_data[symbol] = []
        aggregate_data[symbol].append(stock_config)

        # Collect for total portfolio aggregation
        total_portfolio_data.append(stock_config)

    # Add individual sensors
    add_entities(individual_sensors, True)

    # Add aggregate-per-symbol sensors
    aggregate_sensors = [AggregateStockSensor(symbol, configs) for symbol, configs in aggregate_data.items()]
    add_entities(aggregate_sensors, True)

    # Add total portfolio sensor
    add_entities([TotalPortfolioSensor(total_portfolio_data)], True)


class StockSensor(SensorEntity):
    def __init__(self, stock_config):
        self.account = stock_config["account"]
        self.ticker = stock_config["symbol"]
        self.shares = stock_config["shares"]
        self.purchase_price = stock_config["purchase_price"]
        self._attr_name = f"{self.account} - {self.ticker}"
        self._attr_unique_id = f"{self.account.lower()}_{self.ticker.lower()}"
        self._attr_unit_of_measurement = CURRENCY_DOLLAR
        self._attr_icon = "mdi:chart-line"
        self._state = None
        self._attrs = {}

    def update(self):
        try:
            stock = yf.Ticker(self.ticker)
            price = stock.info.get("regularMarketPrice")
            if price is None:
                self._state = None
                return

            current_value = price * self.shares
            purchase_value = self.purchase_price * self.shares
            gain_loss = current_value - purchase_value
            gain_percent = (gain_loss / purchase_value) * 100 if purchase_value else 0

            self._state = round(current_value, 2)
            self._attrs = {
                "account": self.account,
                "ticker": self.ticker,
                "shares": self.shares,
                "purchase_price": self.purchase_price,
                "current_price": price,
                "gain_loss": round(gain_loss, 2),
                "gain_percent": round(gain_percent, 2)
            }

        except Exception as e:
            _LOGGER.error(f"Failed to update stock {self.ticker} in {self.account}: {e}")
            self._state = None

    @property
    def extra_state_attributes(self):
        return self._attrs


class AggregateStockSensor(SensorEntity):
    def __init__(self, symbol, configs):
        self.ticker = symbol
        self.configs = configs
        self._attr_name = f"{self.ticker} Total"
        self._attr_unique_id = f"{self.ticker.lower()}_total"
        self._attr_unit_of_measurement = CURRENCY_DOLLAR
        self._attr_icon = "mdi:finance"
        self._state = None
        self._attrs = {}

    def update(self):
        try:
            stock = yf.Ticker(self.ticker)
            price = stock.info.get("regularMarketPrice")
            if price is None:
                self._state = None
                return

            total_shares = 0
            total_purchase_value = 0
            account_breakdown = {}

            for config in self.configs:
                shares = config["shares"]
                purchase_price = config["purchase_price"]
                account = config["account"]
                total_shares += shares
                total_purchase_value += shares * purchase_price
                account_breakdown[account] = account_breakdown.get(account, 0) + shares

            current_value = price * total_shares
            gain_loss = current_value - total_purchase_value
            gain_percent = (gain_loss / total_purchase_value) * 100 if total_purchase_value else 0

            self._state = round(current_value, 2)
            self._attrs = {
                "ticker": self.ticker,
                "total_shares": total_shares,
                "current_price": price,
                "total_purchase_value": round(total_purchase_value, 2),
                "gain_loss": round(gain_loss, 2),
                "gain_percent": round(gain_percent, 2),
                "account_breakdown": account_breakdown
            }

        except Exception as e:
            _LOGGER.error(f"Failed to update aggregate sensor for {self.ticker}: {e}")
            self._state = None

    @property
    def extra_state_attributes(self):
        return self._attrs


class TotalPortfolioSensor(SensorEntity):
    def __init__(self, configs):
        self.configs = configs
        self._attr_name = "Total Portfolio Value"
        self._attr_unique_id = "total_portfolio_value"
        self._attr_unit_of_measurement = CURRENCY_DOLLAR
        self._attr_icon = "mdi:briefcase"
        self._state = None
        self._attrs = {}

    def update(self):
        total_value = 0
        total_purchase_value = 0
        per_stock = {}

        for config in self.configs:
            ticker = config["symbol"]
            shares = config["shares"]
            purchase_price = config["purchase_price"]

            try:
                stock = yf.Ticker(ticker)
                price = stock.info.get("regularMarketPrice")
                if price is None:
                    continue
            except Exception as e:
                _LOGGER.error(f"Failed to fetch price for {ticker}: {e}")
                continue

            current_value = price * shares
            purchase_value = purchase_price * shares
            gain_loss = current_value - purchase_value

            total_value += current_value
            total_purchase_value += purchase_value

            if ticker not in per_stock:
                per_stock[ticker] = {"shares": 0, "current_value": 0}
            per_stock[ticker]["shares"] += shares
            per_stock[ticker]["current_value"] += current_value

        gain = total_value - total_purchase_value
        gain_percent = (gain / total_purchase_value * 100) if total_purchase_value else 0

        self._state = round(total_value, 2)
        self._attrs = {
            "total_purchase_value": round(total_purchase_value, 2),
            "total_gain_loss": round(gain, 2),
            "total_gain_percent": round(gain_percent, 2),
            "by_stock": {k: round(v["current_value"], 2) for k, v in per_stock.items()}
        }

    @property
    def extra_state_attributes(self):
        return self._attrs
