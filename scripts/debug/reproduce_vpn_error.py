from expressvpn import connect_alias

try:
    print("Attempting to connect to 'usa' alias...")
    connect_alias("usa")
except Exception as e:
    print(f"Caught expected error: {type(e).__name__}: {e}")
