import os
import requests
from stem import Signal
from stem.control import Controller
import time

# Config
TOR_SOCKS_PORT = int(os.environ.get('TOR_SOCKS_PORT', 9050))
TOR_CONTROL_PORT = int(os.environ.get('TOR_CONTROL_PORT', 9051))
TOR_PASSWORD = os.environ.get('TOR_PASSWORD', "welcomeTomyPa55word")

proxies = {
    'http': f'socks5h://127.0.0.1:{TOR_SOCKS_PORT}',
    'https': f'socks5h://127.0.0.1:{TOR_SOCKS_PORT}'
}

def check_tor():
    print(f"Checking Tor connection on SOCKS port {TOR_SOCKS_PORT} and Control port {TOR_CONTROL_PORT}...")
    
    # 1. Check Control Port
    try:
        print(f"Attempting to connect to Control Port {TOR_CONTROL_PORT}...")
        with Controller.from_port(port=TOR_CONTROL_PORT) as controller:
            controller.authenticate(password=TOR_PASSWORD)
            print("Successfully authenticated to Tor Control Port.")
            controller.signal(Signal.NEWNYM)
            print("Successfully sent NEWNYM signal.")
    except Exception as e:
        print(f"❌ Failed to connect/authenticate to Tor Control Port: {e}")
        print("Make sure Tor is running and the ControlPort is configured.")
        return False

    # 2. Check SOCKS Port
    try:
        print(f"Attempting to connect via SOCKS Port {TOR_SOCKS_PORT}...")
        session = requests.Session()
        session.proxies.update(proxies)
        resp = session.get("http://httpbin.org/ip", timeout=10)
        print(f"Successfully connected via Tor. IP: {resp.json().get('origin')}")
    except Exception as e:
        print(f"❌ Failed to connect via Tor SOCKS Port: {e}")
        return False

    print("✅ Tor configuration verified successfully!")
    return True

if __name__ == "__main__":
    if not check_tor():
        exit(1)
