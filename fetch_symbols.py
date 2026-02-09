import time
import config
from ctrader_fix_client import FixSession
import simplefix

class FetcherApp:
    def __init__(self):
        self.session = FixSession(
            config.CT_HOST, config.CT_TRADE_PORT,
            config.CT_SENDER_COMP_ID, config.CT_TARGET_COMP_ID,
            config.CT_PASSWORD, "TRADE", self
        )

    def start(self):
        print("Connecting...")
        self.session.connect()
        
        # Wait for actual LOGON message
        self.logged_on = False
        for _ in range(10):
            if self.logged_on: break
            time.sleep(1)
            
        if self.logged_on:
            print("Confirmed Logged On. Sending Security List Request...")
            self.send_security_list_request()
            
            print("Waiting for Security List (30s)...")
            time.sleep(30)
        else:
            print("Failed to receive Logon (A).")
            
        self.session.running = False


    def send_security_list_request(self):
        msg = simplefix.FixMessage()
        self.session._add_header(msg, "x")
        msg.append_pair(320, "req_sym") 
        msg.append_pair(559, "0") # All Symbols
        self.session._send_raw(msg)

    def on_message(self, source, msg):
        mtype = msg.get(35)
        
        # Debug Print all types
        # print(f"Msg: {mtype}")
        
        if mtype == b'A':
            print("Logon Received!")
            self.logged_on = True
            
        elif mtype == b'3': # Reject
             print(f"REJECT: {msg.get(58)}")
             
        elif mtype == b'y': # SecurityList
             sym_id = msg.get(55)
             desc = msg.get(107)
             text = msg.get(58)
             
             print(f"RAW: ID={sym_id} Desc={desc} Text={text}")

if __name__ == "__main__":
    app = FetcherApp()
    app.start()
