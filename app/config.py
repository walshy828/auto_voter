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
   {"alias": "usal", "loc": "us"},
{"alias": "usan", "loc": "us"},
{"alias": "usat", "loc": "us"},
{"alias": "usba", "loc": "us"},
{"alias": "usbi", "loc": "us"},
{"alias": "usbo", "loc": "us"},
{"alias": "usbr", "loc": "us"},
{"alias": "usbu", "loc": "us"},
{"alias": "usco", "loc": "us"},
{"alias": "uscs1", "loc": "us"},
{"alias": "usda", "loc": "us"},
{"alias": "usde", "loc": "us"},
{"alias": "usdm", "loc": "us"},
{"alias": "usfa", "loc": "us"},
{"alias": "usja", "loc": "us"},
{"alias": "usla1", "loc": "us"},
{"alias": "usla2", "loc": "us"},
{"alias": "usla3", "loc": "us"},
{"alias": "usla5", "loc": "us"},
{"alias": "uslo", "loc": "us"},
{"alias": "uslr", "loc": "us"},
{"alias": "uslv", "loc": "us"},
{"alias": "usma", "loc": "us"},
{"alias": "usmi", "loc": "us"},
{"alias": "usmi2", "loc": "us"},
{"alias": "usna", "loc": "us"},
{"alias": "usnb", "loc": "us"},
{"alias": "usnj1", "loc": "us"},
{"alias": "usnj2", "loc": "us"},
{"alias": "usnj3", "loc": "us"},
{"alias": "usno", "loc": "us"},
{"alias": "usny", "loc": "us"},
{"alias": "usoc", "loc": "us"},
{"alias": "usom", "loc": "us"},
{"alias": "usph", "loc": "us"},
{"alias": "uspm", "loc": "us"},
{"alias": "uspo", "loc": "us"},
{"alias": "uspr", "loc": "us"},
{"alias": "usse", "loc": "us"},
{"alias": "ussf", "loc": "us"},
{"alias": "ussl", "loc": "us"},
{"alias": "ussl1", "loc": "us"},
{"alias": "ussm", "loc": "us"},
{"alias": "usvb", "loc": "us"},
{"alias": "uswd", "loc": "us"},
{"alias": "uswi", "loc": "us"},
{"alias": "uslp", "loc": "us"},
{"alias": "usch", "loc": "us"},
{"alias": "uscw1", "loc": "us"},
    {"alias": "cato", "loc": ""},
    {"alias": "cato2", "loc": ""},
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
    # --- Desktop Windows (Chrome, Edge, Firefox) ---
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 OPR/109.0.0.0",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",

    # --- Desktop Mac (Safari, Chrome, Firefox) ---
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",

    # --- Mobile iOS (iPhone, iPad) ---
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_7_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/124.0.6367.88 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_8 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.6 Mobile/15E148 Safari/604.1",

    # --- Mobile Android (Chrome, Samsung Internet) ---
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.54 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.54 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.118 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SM-A546B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.54 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-A536B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.118 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.54 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.54 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SM-S921B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.54 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.118 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.119 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SAMSUNG SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/25.0 Chrome/121.0.6167.143 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SAMSUNG SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/24.0 Chrome/119.0.6045.193 Mobile Safari/537.36",
    
    
    # --- Tablets ---
    "Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/124.0.6367.88 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; SM-X900) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.118 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; SM-T870) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.119 Safari/537.36"
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

