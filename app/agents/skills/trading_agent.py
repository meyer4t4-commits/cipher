"""
Trading Agent - Stock/crypto data with real market prices.
Uses yfinance for real-time quotes and technical analysis.
Paper trading tracks positions against real prices.
ALL TRADES REQUIRE OPERATOR APPROVAL.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.logging import logger


class TradingAgent(BaseAgent):
    """Execute trades, manage portfolios, and analyze markets — real market data."""

    def __init__(self, paper_trading: bool = True):
        """
        Initialize the trading agent.

        Args:
            paper_trading: Use paper trading mode (no real money)
        """
        super().__init__(
            name="trading_agent",
            description="Trading and portfolio management with real market data",
            version="2.0.0",
            capabilities=[
                AgentCapability(
                    name="get_quote",
                    description="Get current stock/crypto quote (real prices)",
                    category="data",
                    timeout_seconds=15,
                ),
                AgentCapability(
                    name="get_portfolio",
                    description="Get portfolio positions and balance",
                    category="data",
                    timeout_seconds=10,
                ),
                AgentCapability(
                    name="place_order",
                    description="Place buy or sell order (paper trading)",
                    category="execution",
                    requires_approval=True,
                    timeout_seconds=30,
                ),
                AgentCapability(
                    name="get_order_history",
                    description="Get order history and fills",
                    category="data",
                    timeout_seconds=10,
                ),
                AgentCapability(
                    name="analyze_technical",
                    description="Technical analysis with real data (RSI, MACD, SMA, EMA)",
                    category="data",
                    timeout_seconds=30,
                ),
                AgentCapability(
                    name="set_watchlist",
                    description="Manage watchlists",
                    category="data",
                    timeout_seconds=10,
                ),
            ],
        )
        self.paper_trading = paper_trading
        self.position_size_limit = 0.05  # Max 5% per position
        self.daily_loss_limit = -1000.0

        # Paper trading state — persists to disk
        self._data_dir = Path("./data/trading")
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._portfolio_file = self._data_dir / "paper_portfolio.json"
        self._orders_file = self._data_dir / "paper_orders.json"
        self._watchlist_file = self._data_dir / "watchlists.json"

        # Load state
        self.paper_portfolio = self._load_json(self._portfolio_file, {
            "cash": 100000.0,
            "positions": {},
        })
        self.paper_orders = self._load_json(self._orders_file, [])
        self.watchlists = self._load_json(self._watchlist_file, {"default": []})

        logger.info(f"TradingAgent initialized (paper_trading={paper_trading})")

    def _load_json(self, path: Path, default: Any) -> Any:
        """Load JSON from file or return default."""
        try:
            if path.exists():
                return json.loads(path.read_text())
        except Exception:
            pass
        return default

    def _save_json(self, path: Path, data: Any) -> None:
        """Save data to JSON file."""
        try:
            path.write_text(json.dumps(data, indent=2, default=str))
        except Exception as e:
            logger.warning(f"Failed to save {path}: {e}")

    def requires_approval_for(self, instruction: str) -> bool:
        """All trade orders require approval."""
        return "place_order" in instruction or "order" in instruction.lower()

    async def validate(self, task: AgentTask) -> bool:
        """Validate trading task."""
        if not await super().validate(task):
            return False

        operation = task.params.get("operation", "quote")
        if operation == "place_order" and not task.approved_at:
            logger.warning(f"Task {task.task_id}: Trade order requires approval")
            return False

        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute trading operation."""
        operation = task.params.get("operation", "quote")

        try:
            if operation == "get_quote":
                symbol = task.params.get("symbol", "?")
                await self.emit_progress(f"Pulling live quote for {symbol.upper()}...")
                return await self._get_quote(task)
            elif operation == "get_portfolio":
                await self.emit_progress("Loading portfolio positions...")
                return await self._get_portfolio(task)
            elif operation == "place_order":
                await self.emit_progress("Preparing order for approval...")
                return await self._place_order(task)
            elif operation == "get_order_history":
                await self.emit_progress("Loading order history...")
                return await self._get_order_history(task)
            elif operation == "analyze_technical":
                symbol = task.params.get("symbol", "?")
                await self.emit_progress(f"Running technical analysis on {symbol.upper()}...")
                return await self._analyze_technical(task)
            elif operation == "set_watchlist":
                return await self._set_watchlist(task)
            else:
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"Unknown operation: {operation}",
                )
        except Exception as e:
            logger.error(f"Trading operation failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def _get_quote(self, task: AgentTask) -> AgentResult:
        """Get real stock/crypto quote using yfinance."""
        symbol = task.params.get("symbol")
        if not symbol:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="Missing 'symbol' parameter",
            )

        try:
            import yfinance as yf

            ticker = yf.Ticker(symbol.upper())
            info = ticker.fast_info

            # Get recent history for change calculation
            hist = ticker.history(period="2d")

            if hist.empty:
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"No data found for symbol '{symbol}'. Check if it's valid.",
                )

            current_price = float(hist["Close"].iloc[-1])
            prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else current_price
            change = current_price - prev_close
            change_pct = (change / prev_close * 100) if prev_close else 0

            output = {
                "symbol": symbol.upper(),
                "price": round(current_price, 2),
                "change": round(change, 2),
                "change_percent": round(change_pct, 2),
                "high": round(float(hist["High"].iloc[-1]), 2),
                "low": round(float(hist["Low"].iloc[-1]), 2),
                "open": round(float(hist["Open"].iloc[-1]), 2),
                "volume": int(hist["Volume"].iloc[-1]),
                "previous_close": round(prev_close, 2),
                "market_cap": getattr(info, "market_cap", None),
                "timestamp": datetime.utcnow().isoformat(),
            }

        except ImportError:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="yfinance not installed. Install with: pip install yfinance",
            )
        except Exception as e:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"Quote fetch failed: {str(e)}",
            )

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _get_portfolio(self, task: AgentTask) -> AgentResult:
        """Get paper trading portfolio with real prices."""
        positions = self.paper_portfolio.get("positions", {})
        cash = self.paper_portfolio.get("cash", 100000.0)

        # Get real prices for all positions
        position_details = []
        total_market_value = 0

        if positions:
            try:
                import yfinance as yf

                for symbol, pos_data in positions.items():
                    if pos_data.get("quantity", 0) <= 0:
                        continue

                    try:
                        ticker = yf.Ticker(symbol)
                        hist = ticker.history(period="1d")
                        current_price = float(hist["Close"].iloc[-1]) if not hist.empty else pos_data.get("avg_price", 0)
                    except Exception:
                        current_price = pos_data.get("avg_price", 0)

                    qty = pos_data["quantity"]
                    avg_cost = pos_data.get("avg_price", 0)
                    market_value = current_price * qty
                    cost_basis = avg_cost * qty
                    total_market_value += market_value

                    position_details.append({
                        "symbol": symbol,
                        "quantity": qty,
                        "avg_cost": round(avg_cost, 2),
                        "current_price": round(current_price, 2),
                        "market_value": round(market_value, 2),
                        "cost_basis": round(cost_basis, 2),
                        "unrealized_pnl": round(market_value - cost_basis, 2),
                        "unrealized_pnl_pct": round((market_value - cost_basis) / cost_basis * 100, 2) if cost_basis > 0 else 0,
                    })

            except ImportError:
                logger.warning("yfinance not available for real-time portfolio pricing")

        portfolio_value = cash + total_market_value

        output = {
            "mode": "paper_trading",
            "cash": round(cash, 2),
            "portfolio_value": round(portfolio_value, 2),
            "positions_value": round(total_market_value, 2),
            "positions": position_details,
            "position_count": len(position_details),
            "timestamp": datetime.utcnow().isoformat(),
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _place_order(self, task: AgentTask) -> AgentResult:
        """Place a paper trade order using real prices."""
        symbol = task.params.get("symbol", "").upper()
        side = task.params.get("side", "buy").lower()
        quantity = task.params.get("quantity")
        order_type = task.params.get("type", "market")

        if not symbol or not quantity:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="Missing 'symbol' or 'quantity' parameter",
            )

        if side not in ("buy", "sell"):
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="'side' must be 'buy' or 'sell'",
            )

        # Get real price for the order
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1d")
            if hist.empty:
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"Cannot get price for {symbol}",
                )
            fill_price = float(hist["Close"].iloc[-1])
        except ImportError:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="yfinance required for trading. Install with: pip install yfinance",
            )

        order_value = fill_price * quantity
        cash = self.paper_portfolio.get("cash", 100000.0)
        positions = self.paper_portfolio.get("positions", {})

        # Validate order
        if side == "buy":
            if order_value > cash:
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"Insufficient cash. Need ${order_value:.2f}, have ${cash:.2f}",
                )
            # Update position
            if symbol in positions:
                old_qty = positions[symbol]["quantity"]
                old_avg = positions[symbol]["avg_price"]
                new_qty = old_qty + quantity
                positions[symbol]["quantity"] = new_qty
                positions[symbol]["avg_price"] = (old_avg * old_qty + fill_price * quantity) / new_qty
            else:
                positions[symbol] = {"quantity": quantity, "avg_price": fill_price}
            self.paper_portfolio["cash"] = cash - order_value

        elif side == "sell":
            current_qty = positions.get(symbol, {}).get("quantity", 0)
            if quantity > current_qty:
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"Insufficient shares. Have {current_qty}, trying to sell {quantity}",
                )
            positions[symbol]["quantity"] = current_qty - quantity
            if positions[symbol]["quantity"] == 0:
                del positions[symbol]
            self.paper_portfolio["cash"] = cash + order_value

        self.paper_portfolio["positions"] = positions

        # Record order
        order = {
            "order_id": f"PAPER-{int(datetime.utcnow().timestamp())}",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "fill_price": round(fill_price, 2),
            "total_value": round(order_value, 2),
            "type": order_type,
            "status": "filled",
            "filled_at": datetime.utcnow().isoformat(),
            "paper_trading": True,
        }
        self.paper_orders.append(order)

        # Persist state
        self._save_json(self._portfolio_file, self.paper_portfolio)
        self._save_json(self._orders_file, self.paper_orders)

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=order,
        )

    async def _get_order_history(self, task: AgentTask) -> AgentResult:
        """Get paper trading order history from disk."""
        limit = task.params.get("limit", 50)

        orders = list(reversed(self.paper_orders[-limit:]))

        output = {
            "orders": orders,
            "count": len(orders),
            "total_orders": len(self.paper_orders),
            "limit": limit,
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _analyze_technical(self, task: AgentTask) -> AgentResult:
        """Technical analysis with real market data using yfinance."""
        symbol = task.params.get("symbol")
        period = task.params.get("period", "3mo")

        if not symbol:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="Missing 'symbol' parameter",
            )

        try:
            import yfinance as yf

            ticker = yf.Ticker(symbol.upper())
            hist = ticker.history(period=period)

            if hist.empty or len(hist) < 14:
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"Insufficient data for {symbol}. Need at least 14 days.",
                )

            closes = hist["Close"].values
            volumes = hist["Volume"].values

            # RSI (14-period)
            deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
            gains = [d if d > 0 else 0 for d in deltas]
            losses = [-d if d < 0 else 0 for d in deltas]

            avg_gain = sum(gains[-14:]) / 14
            avg_loss = sum(losses[-14:]) / 14
            rs = avg_gain / avg_loss if avg_loss != 0 else 100
            rsi = 100 - (100 / (1 + rs))

            # Simple Moving Averages
            sma_20 = sum(closes[-20:]) / min(20, len(closes)) if len(closes) >= 20 else sum(closes) / len(closes)
            sma_50 = sum(closes[-50:]) / min(50, len(closes)) if len(closes) >= 50 else sum(closes) / len(closes)

            # EMA (12 and 26 period)
            def ema(data, period):
                multiplier = 2 / (period + 1)
                result = data[0]
                for price in data[1:]:
                    result = (price - result) * multiplier + result
                return result

            ema_12 = ema(list(closes[-26:]), 12) if len(closes) >= 12 else closes[-1]
            ema_26 = ema(list(closes[-26:]), 26) if len(closes) >= 26 else closes[-1]

            # MACD
            macd_line = ema_12 - ema_26
            signal_line = ema(list(closes[-35:]), 9) if len(closes) >= 35 else 0
            macd_histogram = macd_line - signal_line

            # RSI interpretation
            if rsi > 70:
                rsi_signal = "overbought"
            elif rsi < 30:
                rsi_signal = "oversold"
            else:
                rsi_signal = "neutral"

            # MACD interpretation
            macd_signal = "bullish" if macd_histogram > 0 else "bearish"

            # Average volume
            avg_volume = int(sum(volumes[-20:]) / min(20, len(volumes)))

            output = {
                "symbol": symbol.upper(),
                "period": period,
                "data_points": len(hist),
                "current_price": round(float(closes[-1]), 2),
                "analysis": {
                    "RSI": {"value": round(rsi, 2), "signal": rsi_signal},
                    "MACD": {
                        "macd_line": round(macd_line, 4),
                        "signal_line": round(signal_line, 4),
                        "histogram": round(macd_histogram, 4),
                        "signal": macd_signal,
                    },
                    "SMA_20": round(sma_20, 2),
                    "SMA_50": round(sma_50, 2),
                    "EMA_12": round(ema_12, 2),
                    "EMA_26": round(ema_26, 2),
                    "avg_volume_20d": avg_volume,
                    "price_vs_sma20": "above" if closes[-1] > sma_20 else "below",
                    "price_vs_sma50": "above" if closes[-1] > sma_50 else "below",
                },
                "timestamp": datetime.utcnow().isoformat(),
            }

        except ImportError:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="yfinance required. Install with: pip install yfinance",
            )
        except Exception as e:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"Technical analysis failed: {str(e)}",
            )

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _set_watchlist(self, task: AgentTask) -> AgentResult:
        """Manage watchlists — persisted to disk."""
        action = task.params.get("action", "list")
        symbol = task.params.get("symbol", "").upper()
        name = task.params.get("name", "default")

        if name not in self.watchlists:
            self.watchlists[name] = []

        if action == "add" and symbol:
            if symbol not in self.watchlists[name]:
                self.watchlists[name].append(symbol)
        elif action == "remove" and symbol:
            if symbol in self.watchlists[name]:
                self.watchlists[name].remove(symbol)
        elif action == "clear":
            self.watchlists[name] = []

        self._save_json(self._watchlist_file, self.watchlists)

        output = {
            "watchlist_name": name,
            "action": action,
            "symbols": self.watchlists[name],
            "count": len(self.watchlists[name]),
            "all_watchlists": list(self.watchlists.keys()),
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def verify(self, result: AgentResult) -> bool:
        """Verify trading operation result."""
        if not isinstance(result.output, dict):
            logger.warning(f"Result {result.task_id}: Output is not a dict")
            return False

        if "price" in result.output:
            if not isinstance(result.output["price"], (int, float)):
                logger.warning(f"Result {result.task_id}: Invalid price format")
                return False

        return True
