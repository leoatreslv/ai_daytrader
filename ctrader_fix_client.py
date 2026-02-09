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
            msg.append_pair(50, self.sender_sub_id)
            # msg.append_pair(57, self.sender_sub_id) # Removing TargetSubID likely causes disconnect if server doesn't expect it
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
                break
        
        logger.info(f"[{self.sender_sub_id}] Disconnected.")
        self.connected = False

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
        elif msg_type == b'A': # Logon
            logger.info(f"[{self.sender_sub_id}] Logged On!")
        
        # Pass to main app logic
        self.app.on_message(self.sender_sub_id, msg)

class CTraderFixClient:
    def __init__(self,):
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
        
    def start(self):
        logger.info("Connecting to cTrader FIX...")
        self.quote_session.connect()
        time.sleep(2) 
        self.trade_session.connect()
        
        # Wait for logon
        time.sleep(2)
        if self.quote_session.connected and self.trade_session.connected:
            logger.info("Connected to cTrader.")
        elif self.trade_session.connected:
             logger.warning("Connected to cTrader (TRADE Only).")
        else:
            logger.error("Failed to connect to cTrader.")

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

    def handle_market_data(self, symbol_id, price):
        for cb in self.market_data_callbacks:
            cb(symbol_id, price)

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
