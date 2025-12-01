#!/bin/bash
set -e

echo "Starting ExpressVPN daemon..."

# Start ExpressVPN daemon (no --start flag, just run the daemon)
if [ -f /usr/sbin/expressvpnd ]; then
    /usr/sbin/expressvpnd > /dev/null 2>&1 &
elif [ -f /usr/bin/expressvpnd ]; then
    /usr/bin/expressvpnd > /dev/null 2>&1 &
else
    echo "WARNING: ExpressVPN daemon not found! VPN features will not work."
fi

# Wait for daemon to be ready t
sleep 5

# Activate if code is provided
if [ -n "$EXPRESSVPN_ACTIVATION_CODE" ]; then
    echo "Activating ExpressVPN..."
    /usr/bin/expect /app/activate_expressvpn.exp || echo "WARNING: ExpressVPN activation failed"
fi

# Configure preferences (only if daemon is running)
if expressvpn status &>/dev/null; then
    echo "Configuring ExpressVPN preferences..."
    expressvpn preferences set auto_connect false || true
    expressvpn preferences set preferred_protocol lightway_udp || true
    expressvpn preferences set send_diagnostics false || true
    # Force disable network lock
    expressvpn preferences set network_lock off || true
else
    echo "WARNING: ExpressVPN daemon not responding, skipping preference configuration"
fi

# Add static routes for private networks to ensure Web UI remains accessible
# This prevents the VPN from hijacking local traffic (split tunneling)
echo "Configuring split tunneling for local networks..."
GW=$(ip route show | grep default | awk '{print $3}' | head -n 1)
if [ -n "$GW" ]; then
    echo "Default gateway found: $GW"
    # Helper function to add route if not exists
    add_route() {
        # Check if route exists to avoid error
        if ! ip route show | grep -q "$1"; then
            # Try to add route, suppress stderr to avoid log spam
            ip route add "$1" via "$GW" dev eth0 >/dev/null 2>&1 || true
        fi
    }
    
    add_route "10.0.0.0/8"
    add_route "172.16.0.0/12"
    add_route "192.168.0.0/16"
    echo "Local routes configuration completed"
else
    echo "WARNING: Could not determine default gateway, skipping route configuration"
fi

# Start Tor service if TOR_PASSWORD is set
if [ -n "$TOR_PASSWORD" ]; then
    echo "Configuring and starting Tor..."
    
    # Generate hashed password for Tor
    HASHED_PASSWORD=$(tor --hash-password "$TOR_PASSWORD" 2>/dev/null | tail -n 1)
    
    # Create torrc configuration
    cat > /etc/tor/torrc <<EOF
# Tor configuration for auto_voter
SocksPort ${TOR_SOCKS_PORT:-9050}
ControlPort ${TOR_CONTROL_PORT:-9051}
HashedControlPassword $HASHED_PASSWORD
CookieAuthentication 0
DataDirectory /var/lib/tor
Log notice file /var/log/tor/notices.log
EOF
    
    # Create log directory
    mkdir -p /var/log/tor
    chown -R debian-tor:debian-tor /var/log/tor /var/lib/tor 2>/dev/null || true
    
    # Ensure torrc is readable
    chmod 644 /etc/tor/torrc
    
    # Start Tor service in background as debian-tor user
    # We use su to drop privileges since we are running as root
    su -s /bin/bash debian-tor -c "tor -f /etc/tor/torrc > /var/log/tor/tor.log 2>&1 &"
    
    # Wait for Tor to be ready
    echo "Waiting for Tor to start..."
    TOR_STARTED=false
    for i in {1..15}; do
        if ss -tuln 2>/dev/null | grep -q ":${TOR_SOCKS_PORT:-9050}"; then
            echo "✓ Tor started successfully on port ${TOR_SOCKS_PORT:-9050}"
            TOR_STARTED=true
            break
        fi
        sleep 1
    done

    if [ "$TOR_STARTED" = false ]; then
        echo "ERROR: Tor failed to start on port ${TOR_SOCKS_PORT:-9050}"
        if [ -f /var/log/tor/tor.log ]; then
            echo "--- Tor Log Tail ---"
            tail -n 20 /var/log/tor/tor.log
            echo "--------------------"
        else
            echo "No Tor log file found at /var/log/tor/tor.log"
        fi
    fi
else
    echo "TOR_PASSWORD not set, skipping Tor configuration"
fi

echo "Starting application with command: $@"
"$@"
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "Application crashed with exit code $EXIT_CODE"
    # Sleep to prevent tight restart loop and allow log inspection
    sleep 30
fi

exit $EXIT_CODE
