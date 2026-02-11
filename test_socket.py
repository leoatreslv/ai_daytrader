import socket
import ssl
import os
from dotenv import load_dotenv

load_dotenv()

HOST = "demo-uk-eqx-01.p.c-trader.com"
PORT = 5211 # SSL Quote port

print(f"Connecting to {HOST}:{PORT}...")

try:
    raw_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    raw_s.settimeout(5)
    
    context = ssl.create_default_context()
    s = context.wrap_socket(raw_s, server_hostname=HOST)
    
    s.connect((HOST, PORT))
    print("Connected!")
    
    # Send a dummy Logon just to see if we get disconnected or data
    # Standard minimal logon message
    # 8=FIX.4.4|35=A|34=1|49=demo.pepperstone.5211712|56=cServer|50=QUOTE|57=QUOTE|52=...|98=0|108=30|554=...|141=Y|
    # Note: Using | for SOH
    
    # sender = os.getenv("CT_SENDER_COMP_ID", "demo.pepperstone.5211712")
    sender = "demo.pepperstone.5211712" 
    password = os.getenv("CT_PASSWORD", "PASS")
    
    import datetime
    t = datetime.datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3]
    
    import simplefix
    msg = simplefix.FixMessage()
    msg.append_pair(8, "FIX.4.4")
    msg.append_pair(35, "A")
    msg.append_pair(49, sender)
    msg.append_pair(50, "quote") 
    msg.append_pair(56, "cServer")
    msg.append_pair(57, "quote")
    msg.append_pair(34, 1)
    msg.append_pair(52, t)
    msg.append_pair(98, 0)
    msg.append_pair(108, 30)
    msg.append_pair(553, "5211712") 
    msg.append_pair(554, password)
    msg.append_pair(141, "Y")
    
    raw = msg.encode()
    print(f"Sending: {raw}")
    s.sendall(raw)
    
    print("Waiting for response...")
    data = s.recv(4096)
    print(f"Received: {data}")
    
    print(f"Received: {data}")
    
    s.close()

except KeyboardInterrupt:
    print("\nTest interrupted by user.")
    try:
        s.close()
    except:
        pass

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    try:
        s.close()
    except:
        pass
