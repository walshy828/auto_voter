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
    
    # Create torrc configuration with bridges for better connectivity
    cat > /etc/tor/torrc <<EOF
# Tor configuration for auto_voter
SocksPort ${TOR_SOCKS_PORT:-9050}
ControlPort ${TOR_CONTROL_PORT:-9051}
HashedControlPassword $HASHED_PASSWORD
CookieAuthentication 0
DataDirectory /var/lib/tor
Log info file /var/log/tor/notices.log
ClientOnly 1

# Use bridges to bypass blocking
UseBridges 1
ClientTransportPlugin obfs4 exec /usr/bin/obfs4proxy

# Public obfs4 bridges (from https://bridges.torproject.org)
Bridge obfs4 193.11.166.194:27015 2D82C2E354D531A68469ADF7F878FA6060C6BACA cert=4TLQPJrTSaDffMK7Nbao6LC7G9OW/NHkUwIdjLSS3KYf0Nv4/nQiiI8dY2TcsQx01NniOg iat-mode=0
Bridge obfs4 193.11.166.194:27020 86AC7B8D430DAC4117E9F42C9EAED18133863AAF cert=0LDeJH4JzMDtkJJrFphJCiPqKx7loozKN7VNfuukMGfHO0Z8OGdzHVkhVAOfo1mUdv9cMg iat-mode=0
Bridge obfs4 193.11.166.194:27025 1AE2C08904527FEA90C4C4F8C1083EA59FBC6FAF cert=ItvYZzW5tn6v3G4UnQa6Qz04Npro6e81AP70YujmK/KXwDFPTs3aHXcHp4n8Vt6w/bv8cA iat-mode=0
Bridge obfs4 38.229.1.78:80 C8CBDB2464FC9804A69531437BCF2BE31FDD2EE4 cert=Hmyfd2ev46gGY7NoVxA9ngrPF2zCZtzskRTzoWXbxNkzeVnGFPWmrTtILRyqCTjHR+s9dg iat-mode=2

# Firewall settings
FascistFirewall 1
ReachableAddresses *:80,*:443
EOF
    
    # Create log directory
    mkdir -p /var/log/tor
    # Set permissions for root (since we run as root to ensure VPN access)
    chown -R root:root /var/log/tor /var/lib/tor 2>/dev/null || true
    chmod 700 /var/lib/tor
    
    # Ensure torrc is readable
    chmod 644 /etc/tor/torrc
    
    # Verify network access (as root)
    echo "Verifying network access..."
    if curl -s --connect-timeout 5 https://1.1.1.1 > /dev/null; then
        echo "✓ System has internet access"
    else
        echo "✗ System CANNOT reach internet (curl failed)"
        echo "Debug: Checking routing table..."
        ip route show
    fi

    # Start Tor service in background as root
    # We run as root to ensure access to the VPN interface/routing
    echo "Starting Tor as root..."
    tor -f /etc/tor/torrc > /var/log/tor/tor.log 2>&1 &
    
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
