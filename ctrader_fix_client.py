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
        
        self.lock = threading.Lock()

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
                    self.handle_message(msg)
            except socket.timeout:
                continue # Just loop
            except Exception as e:
                logger.error(f"[{self.sender_sub_id}] Read error: {e}")
                self.app.on_disconnected(self.sender_sub_id, f"Read Error: {e}")
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
        self.positions = {} # SymbolID -> NetQty (+Buy, -Sell)

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
        for sym_id, qty in self.positions.items():
            if qty == 0: continue
            has_pos = True
            
            # Try to resolve name
            sym_name = sym_id
            for name, sid in self.symbol_map.items():
                if sid == str(sym_id):
                    sym_name = name
                    break
            
            side = "LONG" if qty > 0 else "SHORT"
            lines.append(f"- {sym_name}: {side} {abs(qty)}")
            
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
        
        # Retry Logic for Quote Session (5x)
        for i in range(5):
            try:
                self.quote_session.connect()
            except Exception as e:
                 logger.error(f"Quote connect error: {e}")
            
            time.sleep(2)
            if self.quote_session.connected:
                break
            logger.warning(f"Quote session failed to connect. Retrying ({i+1}/5)...")
            time.sleep(2)
            
        # Retry logic for Trade Session (5x)
        for i in range(5):
            try:
                self.trade_session.connect()
            except Exception as e:
                logger.error(f"Trade connect error: {e}")

            time.sleep(2)
            if self.trade_session.connected:
                break
            logger.warning(f"Trade session failed to connect. Retrying ({i+1}/5)...")
            time.sleep(2)
        
        # Final Status Check
        if self.quote_session.connected and self.trade_session.connected:
            logger.info("Connected to cTrader (Full).")
            if self.notifier:
                self.notifier.notify("✅ **SYSTEM STARTED**\nConnected to cTrader (Full).")
        elif self.quote_session.connected:
             msg = "⚠️ **PARTIAL CONNECTION**\nConnected to QUOTE Only. Trade session failed."
             logger.warning(msg)
             if self.notifier: self.notifier.notify(msg)
        elif self.trade_session.connected:
             msg = "⚠️ **PARTIAL CONNECTION**\nConnected to TRADE Only. Quote session failed."
             logger.warning(msg)
             if self.notifier: self.notifier.notify(msg)
        else:
            msg = "❌ **CONNECTION FAILED**\nCould not connect to cTrader."
            logger.error(msg)
            if self.notifier: self.notifier.notify(msg)

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
                if self.notifier: self.notifier.notify(f"✅ **ORDER ACCEPTED**\n{side_str} {symbol} {qty}")
            
            elif exec_type == b'F': # Trade (Partial or Full Fill)
                fill_px = msg.get(31).decode() if msg.get(31) else price
                fill_qty = msg.get(32).decode() if msg.get(32) else qty
                msg_text = f"💰 **ORDER FILLED** 💰\n{side_str} {symbol}\nQty: {fill_qty} @ {fill_px}"
                logger.info(msg_text)
                if self.notifier: self.notifier.notify(msg_text)
                
            elif exec_type == b'8': # Rejected
                msg_text = f"🚫 **ORDER REJECTED**\n{side_str} {symbol}\nReason: {text}"
                logger.warning(msg_text)
                if self.notifier: self.notifier.notify(msg_text)
                
            elif exec_type == b'4': # Canceled
                if order_id in self.open_orders:
                    del self.open_orders[order_id]
                    logger.info(f"Order {order_id} Canceled.")
            
            elif exec_type == b'I': # Order Status (Response to Mass Status)
                # If active, add to tracking
                if ord_status not in [b'2', b'8', b'4']: # Not Filled/Rejected/Canceled
                     self.open_orders[order_id] = {
                        "symbol": symbol, "side": side_str, "qty": qty, "price": price
                    }
                     # logger.info(f"Restored Active Order: {symbol} {side_str} {qty}")

        elif msg_type == b'AP': # Position Report
            # cTrader sends Position Report with Long/Short Qty
            try:
                sym = msg.get(55).decode() if msg.get(55) else "Unknown"
                long_qty = float(msg.get(704).decode()) if msg.get(704) else 0.0
                short_qty = float(msg.get(705).decode()) if msg.get(705) else 0.0
                
                net = long_qty - short_qty
                if net != 0:
                    self.positions[sym] = net
                    # logger.info(f"Restored Position: {sym} = {net}")
                else:
                    # Explicitly remove if net is 0 (closed)
                    if sym in self.positions:
                        del self.positions[sym]
                        
            except Exception as e:
                logger.error(f"Error parsing Position Report: {e}")

        else:
            logger.debug(f"[{source}] Unknown MsgType: {msg_type}")

    def clear_state(self):
        """Clear internal state (Orders/Positions) before a sync."""
        self.open_orders.clear()
        self.positions.clear()
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
        logger.info("Sending Position Request...")
        msg = simplefix.FixMessage()
        self.trade_session._add_header(msg, "AN")
        msg.append_pair(710, f"pos{int(time.time())}") # PosReqID
        # RequestForPositions handling varies, trying minimal valid request
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
        if not self.quote_session.connected:
            logger.warning("Cannot fetch symbols: Quote session not connected.")
            return

        logger.info("Fetching symbol list...")
        self.symbol_map.clear()
        
        # Try API Fetch
        try:
            self.send_security_list_request()
            # Wait for symbols to populate
            for _ in range(10): # Wait up to 5 seconds
                time.sleep(0.5)
                if len(self.symbol_map) > 10: 
                    break
        except Exception as e:
            logger.error(f"Error requesting symbol list: {e}")

        # Fallback if API failed
        if len(self.symbol_map) == 0:
            logger.warning("API Symbol fetch failed (or empty). Using Common Symbol Fallback.")
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

        
    def submit_order(self, symbol_id, qty, side, order_type='1', price=None, stop_px=None):
        # New Order Single (D)
        # order_type: 1=Market, 2=Limit, 3=Stop, 4=StopLimit
        msg = simplefix.FixMessage()
        self.trade_session._add_header(msg, "D")
        
        msg.append_pair(11, f"ord{int(time.time() * 1000)}") # ClOrdID (unique)
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
        
        self.trade_session._send_raw(msg)
