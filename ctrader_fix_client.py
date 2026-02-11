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
        self.lock = threading.RLock()
    
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
                
                # Rich text notification
                if self.notifier: 
                    notify_msg = f"💰 **ORDER FILLED** 💰\n{side_str} {symbol}\nQty: {fill_qty} @ {fill_px}"
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
                
                logger.info(f"Position Report for {sym}: Long={long_qty}, Short={short_qty}, ID={pos_id}")
                
                # Initialize format if not present
                if sym not in self.positions:
                    self.positions[sym] = {'long': 0.0, 'short': 0.0}
                    
                # Accumulate (since we might receive multiple reports)
                self.positions[sym]['long'] += long_qty
                self.positions[sym]['short'] += short_qty
                
                # Update Detailed Positions (Hedging)
                if pos_id:
                     details = {
                         'symbol_id': sym,
                         'qty': long_qty if long_qty > 0 else short_qty,
                         'side': 'long' if long_qty > 0 else 'short',
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
