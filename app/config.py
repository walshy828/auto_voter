import os

# VPN Configuration
vpn_maxvotes = 0
vpnmode = 2  # 1=US Only; 2=expanded list
CoolDownCount = 3
Cooldown = 92

# Voting Behavior
cntToPause = 1  # after this number, the script will pause based on the longPauseSeconds
longPauseSeconds = 90

# InfluxDB Configuration - Use environment variables
INFLUX_URL = os.environ.get('INFLUX_URL', '')
INFLUX_TOKEN = os.environ.get('INFLUX_TOKEN', '')
INFLUX_ORG = os.environ.get('INFLUX_ORG', '')
INFLUX_BUCKET = os.environ.get('INFLUX_BUCKET', '')

# VPN Locations
vpnloc = [
    {"alias": "usnj1", "loc": "us"},
    {"alias": "usny", "loc": "us"},
    {"alias": "usla2", "loc": "us"},
    {"alias": "uswd", "loc": "us"},
    {"alias": "usse", "loc": "us"},
    {"alias": "usho", "loc": "us"},
    {"alias": "usph", "loc": "us"},
    {"alias": "usla1", "loc": "us"},
    {"alias": "ussf", "loc": "us"},
    {"alias": "usmi", "loc": "us"},
    {"alias": "usmi2", "loc": "us"},
    {"alias": "usta1", "loc": "us"},
    {"alias": "usla3", "loc": "us"},
    {"alias": "usnj3", "loc": "us"},
    {"alias": "usat", "loc": "us"},
    {"alias": "usda", "loc": "us"},
    {"alias": "usde", "loc": "us"},
    {"alias": "uslp", "loc": "us"},
    {"alias": "usal", "loc": "us"},
    {"alias": "usch", "loc": "us"},
    {"alias": "ussl1", "loc": "us"},
    {"alias": "usnj2", "loc": "us"},
    {"alias": "usla5", "loc": "us"},
    {"alias": "ussm", "loc": "us"},
    {"alias": "cato", "loc": ""},
    {"alias": "camo", "loc": ""},
    {"alias": "cava", "loc": ""},
    {"alias": "defr1", "loc": ""},
    {"alias": "denu", "loc": ""},
    {"alias": "mx", "loc": ""},
    {"alias": "uklo", "loc": ""},
    {"alias": "ukto", "loc": ""},
    {"alias": "ukel", "loc": ""},
    {"alias": "ukmi", "loc": ""},
    {"alias": "ukwe", "loc": ""},
    {"alias": "nlam", "loc": ""},
    {"alias": "nlro", "loc": ""},
    {"alias": "nlth", "loc": ""},
    {"alias": "frpa2", "loc": ""},
    {"alias": "frma", "loc": ""},
    {"alias": "frpa1", "loc": ""},
    {"alias": "frst", "loc": ""},
    {"alias": "fral", "loc": ""},
    {"alias": "itco", "loc": ""},
    {"alias": "itmi", "loc": ""},
    {"alias": "itna", "loc": ""},
    {"alias": "br2", "loc": ""},
    {"alias": "br", "loc": ""},
    {"alias": "pa", "loc": ""},
    {"alias": "ar", "loc": ""},
    {"alias": "cr", "loc": ""},
    {"alias": "co", "loc": ""},
    {"alias": "bs", "loc": ""},
    {"alias": "do", "loc": ""},
    {"alias": "pr", "loc": ""},
    {"alias": "se", "loc": ""},
    {"alias": "se2", "loc": ""},
    {"alias": "ch", "loc": ""},
    {"alias": "tr", "loc": ""},
    {"alias": "is", "loc": ""},
    {"alias": "no", "loc": ""},
    {"alias": "dk", "loc": ""},
    {"alias": "be", "loc": ""},
    {"alias": "fi", "loc": ""},
    {"alias": "gr", "loc": ""},
    {"alias": "pt", "loc": ""},
    {"alias": "at", "loc": ""},
    {"alias": "cz", "loc": ""},
    {"alias": "lu", "loc": ""},
    {"alias": "ua", "loc": ""},
    {"alias": "si", "loc": ""},
    {"alias": "sk", "loc": ""},
    {"alias": "mc", "loc": ""},
]

# User Agents
useragents = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_7_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_7_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_7_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_7_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/135.0.7049.83 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 15) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.7049.79 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 15; SM-A205U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.7049.79 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone17,1; CPU iPhone OS 18_2_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Mohegan Sun/4.7.4",
    "Mozilla/5.0 (iPhone17,3; CPU iPhone OS 18_3_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 FireKeepers/1.6.1",
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 15; SM-S931B Build/AP3A.240905.015.A2; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/127.0.6533.103 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 15; SM-S931B Build/AP3A.240905.015.A2; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/127.0.6533.103 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 9 Pro Build/AD1A.240418.003; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/124.0.6367.54 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 9 Build/AD1A.240411.003.A5; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/124.0.6367.54 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 15; Pixel 8 Build/AP4A.250105.002; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/132.0.6834.163 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone17,5; CPU iPhone OS 18_3_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 FireKeepers/1.7.0",
    "Mozilla/5.0 (iPhone17,5; CPU iPhone OS 18_3_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 FireKeepers/1.7.0",
    "Mozilla/5.0 (iPhone17,3; CPU iPhone OS 18_3_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 FireKeepers/1.6.1",
    "Mozilla/5.0 (iPhone14,7; CPU iPhone OS 18_3_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Mohegan Sun/4.7.3",
]


def get_setting(key, default=None):
    """
    Get a setting from the database, falling back to the default value.
    This allows runtime configuration via the UI.
    """
    try:
        from app.db import SessionLocal
        from app.models import SystemSetting
        
        db = SessionLocal()
        try:
            setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
            if setting and setting.value:
                return setting.value
        finally:
            db.close()
    except:
        pass  # Database not available yet (e.g., during initial setup)
    
    return default


def get_int_setting(key, default=0):
    """Get an integer setting from the database."""
    value = get_setting(key, default)
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

