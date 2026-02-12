import socket
import ssl
import time
import simplefix
import config
import threading
from datetime import datetime
from logger import setup_logger

logger = setup_logger("FixClient")

class FixSession:
    def __init__(self, host, port, sender_comp_id, target_comp_id, password, sender_sub_id, app):
        self.host = host
        self.port = port
        self.sender_comp_id = sender_comp_id
        self.target_comp_id = target_comp_id
        self.password = password
        self.sender_sub_id = sender_sub_id
        self.app = app
        
        self.sock = None
        self.parser = simplefix.FixParser()
        self.connected = False
        self.logged_on = False
        self.msg_seq_num = 1
        self.running = False
        
        self.lock = threading.RLock()

    def stop(self):
        """Force stop the session."""
        self.running = False
        self.connected = False
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
                self.sock.close()
            except:
                pass
            self.sock = None


    def connect(self):
        try:
            logger.info(f"Connecting to {self.host}:{self.port}...")
            raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            raw_sock.settimeout(10.0) 
            
            # Use a more permissive SSL context for compatibility with OpenSSL 3.0+ and legacy servers
            # Use a more permissive SSL context
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            # Allow legacy renegotiation in case server needs it
            context.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0)
            
            # Maximally permissive ciphers (SECLEVEL=0)
            try:
                context.set_ciphers('ALL:@SECLEVEL=0')
                logger.debug("SSL: Set cipher list to ALL:@SECLEVEL=0")
            except Exception as e:
                logger.debug(f"SSL: Could not set SECLEVEL=0: {e}")

            self.sock = context.wrap_socket(raw_sock, server_hostname=self.host)
            self.sock.connect((self.host, self.port))
            
            logger.info(f"SSL Connected. Version: {self.sock.version()}, Cipher: {self.sock.cipher()}")
            
            self.connected = True
            self.running = True
            
            # Start reader thread
            threading.Thread(target=self.read_loop, daemon=True).start()
            
            # Send Logon
            self.send_logon()
            
        except Exception as e:
            logger.error(f"[{self.sender_sub_id}] Connection failed: {e}")
            self.connected = False

    def _add_header(self, msg, msg_type):
        with self.lock:
            msg.append_pair(8, "FIX.4.4")
            msg.append_pair(35, msg_type)
            msg.append_pair(49, self.sender_comp_id)
            msg.append_pair(56, self.target_comp_id)
            msg.append_pair(50, self.sender_sub_id)
            msg.append_pair(57, self.sender_sub_id)
            msg.append_pair(34, self.msg_seq_num)
            
            self.msg_seq_num += 1
            
            msg.append_pair(52, datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3])

    def _send_raw(self, msg):
        raw = msg.encode()
        if self.sock:
            try:
                self.sock.sendall(raw)
            except Exception as e:
                logger.error(f"[{self.sender_sub_id}] Send Error: {e}")

    def send_logon(self):
        msg = simplefix.FixMessage()
        self._add_header(msg, "A")
        
        msg.append_pair(98, "0") # EncryptMethod
        msg.append_pair(108, "30") # HeartBtInt
        
        # Extract Username from SenderCompID (e.g. demo.pepperstone.5211712 -> 5211712)
        try:
            username = self.sender_comp_id.split('.')[-1]
            msg.append_pair(553, username)
        except:
             pass
        
        msg.append_pair(554, self.password)
        msg.append_pair(141, "Y") # ResetSeqNum (Clean session for demo)
        
        # Debug Log (Mask Password)
        try:
            raw_msg = msg.encode()
            if self.password:
                debug_msg = raw_msg.replace(self.password.encode(), b"******")
            else:
                debug_msg = raw_msg # No password to mask
            logger.info(f"[{self.sender_sub_id}] Sending Logon: {debug_msg}")
        except Exception as e:
             logger.error(f"[{self.sender_sub_id}] Logon log error: {e}")
        
        self._send_raw(msg)

    def send_heartbeat(self):
        msg = simplefix.FixMessage()
        self._add_header(msg, "0")
        self._send_raw(msg)

    def send_message(self, msg):
        # Deprecated: usage should be updated to _add_header + _send_raw pattern
        # keeping for compatibility if called externally, but must assume msg is empty?
        # NO, existing calls might build body first.
        # We need to change subscribe/submit to use new pattern.
        pass

    def read_loop(self):
        while self.running and self.sock:
            try:
                data = self.sock.recv(4096)
                if not data:
                    break
                self.parser.append_buffer(data)
                
                while True:
                    msg = self.parser.get_message()
                    if msg is None:
                        break
                    
                    try:
                         # self.handle_message(msg) -> self.app.on_message? 
                         # The viewed code has 'self.handle_message(msg)' at line 147.
                         # But wait, line 147 in viewed code says 'self.handle_message(msg)'.
                         # Does FixSession have handle_message? No, it's not defined in the snippet.
                         # It should likely be self.app.on_message(self.sender_sub_id, msg).
                         # I will use self.handle_message(msg) if that is what was there, but wrap it.
                         self.handle_message(msg)
                    except Exception as e:
                        logger.error(f"[{self.sender_sub_id}] Error in handle_message: {e}")
                        import traceback
                        logger.error(traceback.format_exc())

            except socket.timeout:
                continue # Just loop
            except Exception as e:
                logger.error(f"[{self.sender_sub_id}] Read error: {e}")
                import traceback
                logger.error(traceback.format_exc())
                # self.app.on_disconnected(self.sender_sub_id, f"Read Error: {e}") # Don't disconnect immediately?
                # Actually, read error usually means broken socket.
                self.connected = False
                break
        
        if self.connected: # If we were connected and loop broke
             logger.info(f"[{self.sender_sub_id}] Disconnected.")
             if self.running: # Unexpected disconnect
                 self.app.on_disconnected(self.sender_sub_id, "Connection Reset/Closed")
        
        self.connected = False
        self.logged_on = False

    def handle_message(self, msg):
        msg_type = msg.get(35)
        # print(f"[{self.sender_sub_id}] Recv: {msg_type}")
        
        if msg_type == b'0': # Heartbeat
            pass 
        elif msg_type == b'1': # Test Request
            self.send_heartbeat()
        elif msg_type == b'5': # Logout
            logger.info(f"[{self.sender_sub_id}] Logout received: {msg.get(58)}")
            self.running = False
            self.logged_on = False
        elif msg_type == b'A': # Logon
            self.logged_on = True
            logger.info(f"[{self.sender_sub_id}] Logged On!")
        
        # Pass to main app logic
        self.app.on_message(self.sender_sub_id, msg)


class CTraderFixClient:
    # Fallback map for common symbols (Demo/Live IDs are usually consistent for majors)
    COMMON_SYMBOLS = {
        "EURUSD": "1", "GBPUSD": "2", "USDJPY": "4", "GBPJPY": "6", 
        "AUDUSD": "9", "NZDUSD": "13", "USDCAD": "14", "USDCHF": "15",
        "XAUUSD": "41", "ETHUSD": "1002", "BTCUSD": "1001"
    }

    def __init__(self, notifier=None):
        self.notifier = notifier
        self.quote_session = FixSession(
            config.CT_HOST, config.CT_QUOTE_PORT,
            config.CT_SENDER_COMP_ID, config.CT_TARGET_COMP_ID,
            config.CT_PASSWORD, "QUOTE", self
        )
        self.trade_session = FixSession(
            config.CT_HOST, config.CT_TRADE_PORT,
            config.CT_SENDER_COMP_ID, config.CT_TARGET_COMP_ID,
            config.CT_PASSWORD, "TRADE", self
        )
        self.market_data_callbacks = []
        self.latest_prices = {} # Store latest price by SymbolID
        self.last_price_times = {} # Store last update time
        self.symbol_map = {}
        # Tracking State (In-Memory)
        self.open_orders = {} # OrderID -> {Symbol, Side, Qty, Price}
        self.positions = {} # SymbolID -> {'long': 0.0, 'short': 0.0}
        self.position_details = {} # PositionID -> {Symbol, Side, Qty}
        self.order_counter = 0
        self.trade_history = self._load_trades() # Load persistent history
        self.lock = threading.RLock()
    
    def _load_trades(self):
        """Load trade history from JSON file."""
        import json
        import os
        try:
            if os.path.exists("trades.json"):
                with open("trades.json", "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load trades.json: {e}")
        return []

    def _save_trades(self):
        """Save trade history to JSON file."""
        import json
        try:
            with open("trades.json", "w") as f:
                json.dump(self.trade_history, f, indent=4, default=str)
        except Exception as e:
            logger.error(f"Failed to save trades.json: {e}")

    def get_daily_report(self):
        """Generate a report of trades executed today."""
        from datetime import datetime
        
        today_str = datetime.now().strftime("%Y-%m-%d")
        lines = [f"📊 **DAILY REPORT ({today_str})**"]
        
        daily_pnl = 0.0
        trade_count = 0
        
        # Filter for today
        # Stored format in JSON usually ISO string for datetime
        
        for trade in self.trade_history:
            # Check date
            t_time = trade.get('time')
            if not t_time: continue
            
            # Simple string check if format is compatible
            if t_time.startswith(today_str):
                trade_count += 1
                symbol = trade.get('symbol', 'Unknown')
                side = trade.get('side', '?')
                qty = trade.get('qty', 0)
                price = trade.get('price', 0)
                pnl = trade.get('pnl')
                ord_type = trade.get('type', 'MARKET')
                
                # Format Line
                # 13:45 | SELL XAUUSD 10 @ 2025.50 | +50.00 (TP)
                time_part = t_time.split(' ')[1][:8] if ' ' in t_time else t_time
                
                pnl_str = "-"
                if pnl is not None:
                    try:
                        val = float(pnl)
                        daily_pnl += val
                        icon = "🟢" if val >= 0 else "🔴"
                        pnl_str = f"{icon} {val:.2f}"
                    except:
                        pass
                
                lines.append(f"{time_part} | {side} {symbol} {qty} @ {price} | {pnl_str} ({ord_type})")
        
        if trade_count == 0:
            lines.append("No trades executed today.")
        else:
            icon_total = "🟢" if daily_pnl >= 0 else "🔴"
            lines.append(f"\n**Total Daily PnL: {icon_total} {daily_pnl:.2f}**")
            
        return "\n".join(lines)
    
    def stop(self):
        """Stop all sessions."""
        logger.info("Stopping FIX Client...")
        self.quote_session.stop()
        self.trade_session.stop()


    def close_all_positions(self):
        """Close all open positions with Market Orders."""
        if not self.positions:
            logger.info("No positions to close.")
            return

        logger.info(f"Closing all positions: {self.positions}")
        if self.notifier:
            self.notifier.notify(f"🛑 **MARKET CLOSE**\nClosing all {len(self.positions)} positions.")

        # Iterate copy of keys
        for symbol_id, pos_data in list(self.positions.items()):
            long_qty = pos_data.get('long', 0.0)
            short_qty = pos_data.get('short', 0.0)
            
            if long_qty > 0:
                logger.info(f"Closing {symbol_id}: SELL {long_qty} (Close Long)")
                self.submit_order(symbol_id, long_qty, '2', order_type='1')
                
            if short_qty > 0:
                 logger.info(f"Closing {symbol_id}: BUY {short_qty} (Close Short)")
                 self.submit_order(symbol_id, short_qty, '1', order_type='1')

    def get_orders_string(self):
        if not self.open_orders:
            return "📭 **NO ACTIVE ORDERS**"
        
        lines = ["📋 **ACTIVE ORDERS**"]
        for oid, details in self.open_orders.items():
            lines.append(f"- {details['side']} {details['symbol']} {details['qty']} @ {details['price']}")
        return "\n".join(lines)

    def get_positions_string(self):
        if not self.positions:
            return "🧘 **NO OPEN POSITIONS**"
            
        lines = ["💼 **CURRENT POSITIONS**"]
        has_pos = False
        for sym_id, pos_data in self.positions.items():
            long_qty = pos_data.get('long', 0.0)
            short_qty = pos_data.get('short', 0.0)
            
            if long_qty == 0 and short_qty == 0: continue
            has_pos = True
            
            # Try to resolve name
            sym_name = sym_id
            for name, sid in self.symbol_map.items():
                if sid == str(sym_id):
                    sym_name = name
                    break
            
            if long_qty > 0:
                lines.append(f"- {sym_name}: LONG {long_qty}")
            if short_qty > 0:
                lines.append(f"- {sym_name}: SHORT {short_qty}")
            
        if not has_pos:
            return "🧘 **NO OPEN POSITIONS**"
            
        if not has_pos:
            return "🧘 **NO OPEN POSITIONS**"
            
        return "\n".join(lines)

    def get_open_position_count(self):
        """Count number of symbols with active open positions."""
        count = 0
        for pos_data in self.positions.values():
            if pos_data.get('long', 0.0) > 0 or pos_data.get('short', 0.0) > 0:
                count += 1
        return count

    def get_position_pnl_string(self):
        """Get string representation of positions with estimated PnL."""
        if not self.positions:
            return "🧘 **NO OPEN POSITIONS**"
            
        lines = ["💼 **CURRENT POSITIONS (w/ Approx PnL)**"]
        has_pos = False
        total_pnl_points = 0.0
        
        for sym_id, pos_data in self.positions.items():
            long_qty = pos_data.get('long', 0.0)
            short_qty = pos_data.get('short', 0.0)
            entry_px_long = pos_data.get('long_avg_px', 0.0)
            entry_px_short = pos_data.get('short_avg_px', 0.0)
            
            if long_qty == 0 and short_qty == 0: continue
            has_pos = True
            
            # Try to resolve name
            sym_name = sym_id
            for name, sid in self.symbol_map.items():
                if sid == str(sym_id):
                    sym_name = name
                    break
            
            current_price = self.latest_prices.get(str(sym_id))
            
            if long_qty > 0:
                pnl_str = ""
                if current_price and entry_px_long > 0:
                    raw_diff = current_price - entry_px_long
                    # Estimate PnL (Points * Qty) - Very rough
                    # For XAUUSD (0.01 tick), if diff is 1.00, that's 100 pips?
                    # Let's just show price diff * qty for now
                    pnl_val = raw_diff * long_qty
                    total_pnl_points += pnl_val
                    icon = "🟢" if pnl_val >= 0 else "🔴"
                    pnl_str = f" | PnL: {icon} {pnl_val:.2f}"
                
                lines.append(f"- {sym_name}: LONG {long_qty} @ {entry_px_long:.4f}{pnl_str}")

            if short_qty > 0:
                pnl_str = ""
                if current_price and entry_px_short > 0:
                    raw_diff = entry_px_short - current_price
                    pnl_val = raw_diff * short_qty
                    total_pnl_points += pnl_val
                    icon = "🟢" if pnl_val >= 0 else "🔴"
                    pnl_str = f" | PnL: {icon} {pnl_val:.2f}"
                
                lines.append(f"- {sym_name}: SHORT {short_qty} @ {entry_px_short:.4f}{pnl_str}")
            
        if not has_pos:
            return "🧘 **NO OPEN POSITIONS**"
            
        # Total PnL (Estimation)
        lines.append(f"\nΣ Est. Net PnL (Points): {total_pnl_points:.2f}")
            
        return "\n".join(lines)
        
    def handle_market_data(self, symbol_id, price):
        # Ensure symbol_id is string
        if isinstance(symbol_id, bytes):
            symbol_id = symbol_id.decode()

        self.latest_prices[str(symbol_id)] = price
        if hasattr(self, 'last_price_times'):
             self.last_price_times[symbol_id] = datetime.now()
             
        for cb in self.market_data_callbacks:
            cb(symbol_id, price)
        
    def start(self):
        logger.info("Connecting to cTrader FIX...")
        
        # Helper retry function
        def connect_session(session, name):
            for i in range(5):
                try:
                    logger.info(f"Connecting to {name} (Attempt {i+1}/5)...")
                    session.connect()
                    
                    # Wait for Logon
                    for _ in range(20): 
                        if session.logged_on: return True
                        if not session.running: return False # Check if stopped
                        time.sleep(0.5)
                        
                except Exception as e:
                    logger.error(f"{name} connect error: {e}")
                
                logger.warning(f"{name} failed to connect (or Logon). Retrying...")
                time.sleep(2)
            return False

        # Connect Quote
        if not connect_session(self.quote_session, "QUOTE"):
             logger.error("Failed to connect QUOTE session.")

        # Connect Trade
        if not connect_session(self.trade_session, "TRADE"):
             logger.error("Failed to connect TRADE session.")
        
        # Final Status Check
        if self.quote_session.connected and self.trade_session.connected:
            logger.info("Connected to cTrader (Full).")
            if self.notifier:
                self.notifier.notify("✅ **SYSTEM STARTED**\nConnected to cTrader (Full).")
        elif self.quote_session.connected:
             msg = "[WARN] PARTIAL CONNECTION: Connected to QUOTE Only. Trade session failed."
             logger.warning(msg)
             if self.notifier: self.notifier.notify("⚠️ **PARTIAL CONNECTION**\nConnected to QUOTE Only. Trade session failed.")
        elif self.trade_session.connected:
             msg = "[WARN] PARTIAL CONNECTION: Connected to TRADE Only. Quote session failed."
             logger.warning(msg)
             if self.notifier: self.notifier.notify("⚠️ **PARTIAL CONNECTION**\nConnected to TRADE Only. Quote session failed.")
        else:
            msg = "[ERROR] CONNECTION FAILED: Could not connect to cTrader."
            logger.error(msg)
            if self.notifier: self.notifier.notify("❌ **CONNECTION FAILED**\nCould not connect to cTrader.")

    def on_disconnected(self, session_type, reason="Unknown"):
        msg = f"[FAILED] **DISCONNECTED**\nSession: {session_type}\nReason: {reason}"
        logger.warning(msg)
        if self.notifier:
            self.notifier.notify(msg)

    def on_message(self, source, msg):
        msg_type = msg.get(35)
        
        if msg_type == b'W' or msg_type == b'X': # Market Data Snapshot / Incremental
             symbol_id = msg.get(55)
             price = msg.get(270) # MDEntryPx
             if price:
                 self.handle_market_data(symbol_id, float(price))
                 
        elif msg_type == b'3': # Reject
            logger.warning(f"[{source}] REJECT: {msg.get(58)}")
            
        elif msg_type == b'Y': # Market Data Request Reject
            logger.warning(f"[{source}] MD REJECT: {msg.get(58)} (ReqID: {msg.get(262)})")

        elif msg_type == b'j': # Business Message Reject
            ref_msg_type = msg.get(372)
            text = msg.get(58).decode() if msg.get(58) else "Unknown"
            reason = msg.get(380)
            
            # Suppress notification for known "SecurityListRequestType" reject (we have fallback)
            if b'SecurityListRequestType' in msg.get(58) or b'SecurityListRequestType' in (msg.get(380) or b''):
                 logger.warning(f"[{source}] Security List Request not supported (using fallback): {text}")
            else:
                 logger.error(f"[{source}] BUSINESS REJECT: Type={ref_msg_type}, Reason={reason}, Text={text}")
                 if self.notifier:
                     self.notifier.notify(f"🚫 **BUSINESS REJECT**\nReason: {text}")

        elif msg_type == b'y': # Security List
             # cTrader sends 55=ID, 107=Description (Name)
             sym_id = msg.get(55)
             sym_name = msg.get(107)
             if sym_id and sym_name:
                 # Map Name -> ID (e.g. "EURUSD" -> "1")
                 self.symbol_map[sym_name.decode()] = sym_id.decode()
                 # Also valid to map "EUR/USD" or other variations if needed later based on 107 format

        elif msg_type == b'8': # Execution Report
            exec_type = msg.get(150) # 0=New, F=Trade, 8=Rejected
            ord_status = msg.get(39) # 0=New, 1=PartiallyFilled, 2=Filled, 8=Rejected
            order_id = msg.get(37).decode() if msg.get(37) else "Unknown"
            symbol = msg.get(55).decode() if msg.get(55) else "Unknown"
            side = msg.get(54) # 1=Buy, 2=Sell
            side_str = "BUY" if side == b'1' else "SELL"
            qty = msg.get(38).decode() if msg.get(38) else "?"
            price = msg.get(44).decode() if msg.get(44) else "Market"
            text = msg.get(58).decode() if msg.get(58) else ""
            
            if exec_type == b'0': # New
                logger.info(f"[{source}] Order Accepted: {side_str} {symbol} {qty}")
                # Add to Open Orders Tracking
                self.open_orders[order_id] = {
                    "symbol": symbol, "side": side_str, "qty": qty, "price": price
                }
                if self.notifier: self.notifier.notify(f"✅ **ORDER ACCEPTED**\n{side_str} {symbol} {qty}")
            
            elif exec_type == b'F': # Trade (Partial or Full Fill)
                fill_px = msg.get(31).decode() if msg.get(31) else price
                fill_qty = msg.get(32).decode() if msg.get(32) else qty
                
                # Plain text log
                log_msg = f"ORDER FILLED: {side_str} {symbol} Qty: {fill_qty} @ {fill_px}"
                logger.info(log_msg)
                
                # Determine Order Type for Notification
                ord_type = msg.get(40) # 1=Market, 2=Limit, 3=Stop
                # If not in msg, try to find in open_orders (if we tracked it)
                # But open_orders might be deleted by 'F' handling if we did that first? 
                # Actually we don't delete from open_orders until we see 'Filled' status, but here we are in 'F'.
                
                title = "💰 **ORDER FILLED** 💰"
                if ord_type == b'3':
                    title = "🛡️ **STOP LOSS FILLED** 🛡️"
                elif ord_type == b'2':
                    title = "💰 **TAKE PROFIT / LIMIT FILLED** 💰"
                elif ord_type == b'1':
                    title = "🚀 **MARKET ORDER FILLED** 🚀"
                
                # Calculate Realized PnL
                pnl_str = ""
                realized_pnl = None
                try:
                    # Look up Entry Price from cached positions
                    entry_px = 0.0
                    is_long_close = (side == b'2') # Selling to close Long
                    is_short_close = (side == b'1') # Buying to close Short
                    
                    fill_val = float(fill_qty)
                    fill_p = float(fill_px)

                    # Check position cache
                    # Note: Symbol ID is in 'symbol' variable (decoded), but positions keys might be strings
                    if symbol in self.positions:
                        pos_data = self.positions[symbol]
                        if is_long_close:
                            entry_px = pos_data.get('long_avg_px', 0.0)
                            if entry_px > 0:
                                pnl = (fill_p - entry_px) * fill_val
                                realized_pnl = pnl
                                icon = "🟢" if pnl >= 0 else "🔴"
                                pnl_str = f"\n**Realized PnL: {icon} {pnl:.2f}**"
                        
                        elif is_short_close:
                            entry_px = pos_data.get('short_avg_px', 0.0)
                            if entry_px > 0:
                                pnl = (entry_px - fill_p) * fill_val
                                realized_pnl = pnl
                                icon = "🟢" if pnl >= 0 else "🔴"
                                pnl_str = f"\n**Realized PnL: {icon} {pnl:.2f}**"
                except Exception as e:
                    logger.error(f"Error calculating Realized PnL: {e}")

                # Save to History
                try:
                    trade_record = {
                        'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'symbol': symbol,
                        'side': side_str,
                        'qty': fill_qty,
                        'price': fill_px,
                        'pnl': realized_pnl,
                        'type': 'STOP' if ord_type == b'3' else 'LIMIT' if ord_type == b'2' else 'MARKET'
                    }
                    self.trade_history.append(trade_record)
                    self._save_trades()
                except Exception as e:
                    logger.error(f"Error saving trade history: {e}")

                # Rich text notification
                if self.notifier: 
                    notify_msg = f"{title}\n{side_str} {symbol}\nQty: {fill_qty} @ {fill_px}{pnl_str}"
                    self.notifier.notify(notify_msg)
                
                # Update Net Position Tracking
                try:
                    f_qty = float(fill_qty)
                    if side == b'2': # Sell
                        f_qty = -f_qty
                    
                    
                    # Accumulate net position
                    # For robust hedging support, we should rely on Position Reports (AP) or distinct logic.
                    # Since we are switching to Sync-On-Fill, we can skip manual accumulation here 
                    # OR do a best-effort update.
                    
                    # Logic: Side 1 (Buy) adds to Long? Or reduces Short?
                    # Without knowing if it's "Close" or "Open", it's ambiguous in Hedging.
                    # Best to rely on the Sync triggered below.
                    pass
                    
                except Exception as e:
                    logger.error(f"Error updating position from execution report: {e}")

                
            elif exec_type == b'8': # Rejected
                if order_id in self.open_orders:
                    del self.open_orders[order_id]
                
                # Plain text log
                log_msg = f"ORDER REJECTED: {side_str} {symbol} Reason: {text}"
                logger.warning(log_msg)
                
                # Rich text notification
                if self.notifier: 
                    notify_msg = f"🚫 **ORDER REJECTED**\n{side_str} {symbol}\nReason: {text}"
                    self.notifier.notify(notify_msg)
                
            elif exec_type == b'4': # Canceled
                if order_id in self.open_orders:
                    del self.open_orders[order_id]
                    logger.info(f"Order {order_id} Canceled.")
                    if self.notifier: self.notifier.notify(f"🗑️ **ORDER CANCELED**\n{side_str} {symbol} {qty}")
            
            elif exec_type == b'I': # Order Status (Response to Mass Status)
                # If active, add to tracking
                if ord_status not in [b'2', b'8', b'4']: # Not Filled/Rejected/Canceled
                     self.open_orders[order_id] = {
                        "symbol": symbol, "side": side_str, "qty": qty, "price": price
                    }
                
                # If Filled, trigger a Sync to maintain accurate positions
                if ord_status == b'2' or ord_status == b'1': 
                    # Delay slightly to allow server to process, then Clear & Request
                    def scheduled_sync():
                        time.sleep(1)
                        self.clear_state()
                        self.send_positions_request()
                        
                    threading.Thread(target=scheduled_sync, daemon=True).start()

        elif msg_type == b'AP': # Position Report
            # cTrader sends Position Report with Long/Short Qty
            try:
                # Debug Raw
                # logger.info(f"Received AP (Raw): {msg}")
                
                sym = msg.get(55).decode() if msg.get(55) else "Unknown"
                long_qty = float(msg.get(704).decode()) if msg.get(704) else 0.0
                short_qty = float(msg.get(705).decode()) if msg.get(705) else 0.0
                pos_id = msg.get(721).decode() if msg.get(721) else None # PositionID
                
                # Entry Price (AvgPx) from Tag 731 (SettlPrice), 44 (Price) or 31 (LastPx)?
                # Standard Position Report (AP) often uses Tag 731 for SettlPrice (Mark-to-Market)
                # or Tag 730 (SettlPrice)
                # Let's check available tags in typical cTrader AP response.
                # Assuming Tag 31 (LastPx) might be used for 'AvgPx' if not explicit.
                # However, Tag 730 is standard 'SettlPrice'.
                # Let's try to grab whatever looks like price.
                # Tag 731 is often used for SettlPriceType.
                # Tag 730 is SettlPrice.
                # But for 'Entry Price', we want avg cost.
                # cTrader FIX API: PositionReport -> No explicit 'Entry Price' tag in standard?
                # Actually, standard FIX 4.4 Position Report has 'SettlPrice' (730).
                # But 'AvgPx' might be in Tag 6 (AvgPx) IF provided?
                # Let's try 730 (SettlPrice) as best proxy or see if 31 is there.
                
                # For now, let's use a placeholder if we can't find it, or log it.
                # Let's try to extract Price (44) if present, or SettlPrice (730).
                entry_px = 0.0
                if msg.get(730):
                    entry_px = float(msg.get(730).decode())
                elif msg.get(44):
                    entry_px = float(msg.get(44).decode())
                
                # Since Position Report splits Long/Short, it might give One Price?
                # Usually LongQty and ShortQty are reported. 
                # If both exist, the Price applies to... net? or one side?
                # Does AP report separate entries for Long vs Short or one combined?
                # If msg has LongQty=X and ShortQty=Y, it usually means 'Net' report or 'Position' report.
                # If we get separate reports per position ID, we get specific prices.
                
                logger.info(f"Position Report for {sym}: Long={long_qty}, Short={short_qty}, ID={pos_id}, Px={entry_px}")
                
                # Initialize format if not present
                if sym not in self.positions:
                    self.positions[sym] = {
                        'long': 0.0, 'short': 0.0, 
                        'long_avg_px': 0.0, 'short_avg_px': 0.0
                    }
                    
                # Update logic
                # If this is a snapshot update, we replace or accumulate?
                # "Position Report" is usually a snapshot of current state for that ID/Symbol.
                # If we rely on clearing state before request, we can just set it.
                # But Position Reports come per PositionID in hedging?
                
                # Simplified aggregation:
                # We need to compute Weighted Avg Price if we are aggregating multiple position IDs
                # Current 'positions' dict aggregates by Symbol.
                # If we get multiple Position IDs for same symbol (Hedging), we need to average.
                
                curr_long = self.positions[sym]['long']
                curr_short = self.positions[sym]['short']
                curr_long_px = self.positions[sym].get('long_avg_px', 0.0)
                curr_short_px = self.positions[sym].get('short_avg_px', 0.0)
                
                # If we are clearing state before request, we start from 0.
                # But if we receive partial updates...
                # Assuming "Clear & Request" flow used in main.py:
                # self.positions is cleared. Then we receive N reports.
                
                # Re-calculating weighted average:
                # New Long Qty = curr_long + long_qty
                # New Long Px = ((curr_long * curr_long_px) + (long_qty * entry_px)) / (curr_long + long_qty)
                
                if long_qty > 0:
                     new_total = curr_long + long_qty
                     if new_total > 0:
                         avg_px = ((curr_long * curr_long_px) + (long_qty * entry_px)) / new_total
                         self.positions[sym]['long'] = new_total
                         self.positions[sym]['long_avg_px'] = avg_px
                
                if short_qty > 0:
                     new_total = curr_short + short_qty
                     if new_total > 0:
                         avg_px = ((curr_short * curr_short_px) + (short_qty * entry_px)) / new_total
                         self.positions[sym]['short'] = new_total
                         self.positions[sym]['short_avg_px'] = avg_px
                
                # Update Detailed Positions (Hedging)
                if pos_id:
                     details = {
                         'symbol_id': sym,
                         'qty': long_qty if long_qty > 0 else short_qty,
                         'side': 'long' if long_qty > 0 else 'short',
                         'entry_price': entry_px,
                         'position_id': pos_id
                     }
                     self.position_details[pos_id] = details
                     logger.info(f"Updated Detail Position: {details}")
 
            except Exception as e:
                logger.error(f"Error parsing Position Report: {e}")

        else:
            logger.debug(f"[{source}] Unknown MsgType: {msg_type}")

    def clear_state(self):
        """Clear internal state (Orders/Positions) before a sync."""
        self.open_orders.clear()
        self.positions.clear()
        self.position_details.clear()
        logger.info("Internal state cleared.")

    def send_order_mass_status_request(self):
        """Request status of all active orders."""
        logger.info("Sending Order Mass Status Request...")
        msg = simplefix.FixMessage()
        self.trade_session._add_header(msg, "AF")
        msg.append_pair(584, f"mass{int(time.time())}") # MassStatusReqID
        msg.append_pair(585, "7") # 7 = Status for all orders
        self.trade_session._send_raw(msg)

    def send_positions_request(self):
        """Request all open positions."""
        if not self.trade_session.logged_on:
             logger.warning("Cannot request positions: Trade session not logged on.")
             return

        logger.info("Sending Position Request (AN)...")
        msg = simplefix.FixMessage()
        self.trade_session._add_header(msg, "AN")
        msg.append_pair(710, f"pos{int(time.time())}") # PosReqID
        # Tag 724 (PosReqType) removed - unsupported by cTrader Demo
        
        self.trade_session._send_raw(msg)

    def send_security_list_request(self):
        """Request list of all symbols to build the map."""
        msg = simplefix.FixMessage()
        self.quote_session._add_header(msg, "x")
        msg.append_pair(320, "1") # SecurityReqID
        msg.append_pair(559, "4") # SecurityListRequestType = All Securities
        self.quote_session._send_raw(msg)

    def fetch_symbols(self):
        """Blocking call to fetch symbols."""
        logger.info("Loading symbol list from Config...")
        self.symbol_map.clear()
        
        # Load from config.SYMBOLS
        if hasattr(config, 'SYMBOLS'):
             # Ensure values are strings
             for k,v in config.SYMBOLS.items():
                 self.symbol_map[k] = str(v)
        
        # Fallback if Config failed or empty
        if len(self.symbol_map) == 0:
            logger.warning("Config SYMBOLS empty. Using Common Symbol Fallback.")
            self.symbol_map.update(self.COMMON_SYMBOLS)
        
        logger.info(f"Loaded {len(self.symbol_map)} symbols.")

    def get_symbol_id(self, name):
        """Resolve symbol name to ID (Case-Insensitive)."""
        # Direct lookup
        if name in self.symbol_map:
             return self.symbol_map[name]
        
        # Case insensitive lookup
        name_upper = name.upper()
        for k, v in self.symbol_map.items():
            if k.upper() == name_upper:
                return v
        return None

    def get_symbol_name(self, symbol_id):
        """Resolve symbol ID to Name (Reverse Lookup)."""
        # Linear search (map is small)
        str_id = str(symbol_id)
        for name, sid in self.symbol_map.items():
            if str(sid) == str_id:
                return name
        return str_id # Return ID if name not found



    def subscribe_market_data(self, symbol_id, request_id):
        # Market Data Request (V)
        msg = simplefix.FixMessage()
        
        # Fallback to Trade Session if Quote is down
        if self.quote_session.connected:
            session = self.quote_session
        elif self.trade_session.connected:
            session = self.trade_session
            logger.warning("Using TRADE session for Market Data (QUOTE down).")
        else:
            logger.error("No active session for Market Data.")
            return

        session._add_header(msg, "V")
        
        msg.append_pair(262, request_id) # MDReqID
        msg.append_pair(263, "1") # SubscriptionRequestType
        msg.append_pair(264, "1") # MarketDepth
        msg.append_pair(265, "1") # UpdateType
        
        msg.append_pair(267, "2") # NoMDEntryTypes
        msg.append_pair(269, "0")
        msg.append_pair(269, "1")
        
        msg.append_pair(146, "1") # NoRelatedSym
        msg.append_pair(55, symbol_id) # Symbol
        
        session._send_raw(msg)

        
    def submit_order(self, symbol_id, qty, side, order_type='1', price=None, stop_px=None, position_id=None):
        # New Order Single (D)
        # order_type: 1=Market, 2=Limit, 3=Stop, 4=StopLimit
        with self.lock:
            self.order_counter += 1
            counter = self.order_counter
            
        msg = simplefix.FixMessage()
        self.trade_session._add_header(msg, "D")
        
        # Unique ClOrdID: Time + Counter to prevent collisions in rapid fire (SL/TP)
        cls_ord_id = f"ord{int(time.time() * 1000)}_{counter}"
        msg.append_pair(11, cls_ord_id) 
        msg.append_pair(55, symbol_id)
        msg.append_pair(54, side) 
        msg.append_pair(60, datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3])
        msg.append_pair(38, qty)
        msg.append_pair(40, order_type)
        msg.append_pair(59, "1") # GTC usually okay, or 0 (Day)
        
        if price:
            msg.append_pair(44, price) # Price (for Limit)
        if stop_px:
            msg.append_pair(99, stop_px) # StopPx (for Stop)
        
        if position_id:
            msg.append_pair(721, position_id) # PositionID for closing specific position in Hedging
            logger.info(f"Attaching PositionID {position_id} to order.")
            
        self.trade_session._send_raw(msg)
