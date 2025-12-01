#!/bin/bash
set -e

echo "Starting ExpressVPN daemon..."

# Start ExpressVPN daemon (no --start flag, just run the daemon)
if [ -f /usr/sbin/expressvpnd ]; then
    /usr/sbin/expressvpnd &
elif [ -f /usr/bin/expressvpnd ]; then
    /usr/bin/expressvpnd &
else
    echo "WARNING: ExpressVPN daemon not found! VPN features will not work."
fi

# Wait for daemon to be ready
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
    # Force disable network lock multiple ways
    expressvpn preferences set network_lock off || true
    expressvpn preferences set network_lock_enabled false || true
    expressvpn preferences set network_lock_enabled false || true
else
    echo "WARNING: ExpressVPN daemon not responding, skipping preference configuration"
fi

# Add static routes for private networks to ensure Web UI remains accessible
# This prevents the VPN from hijacking local traffic (split tunneling)
echo "Configuring split tunneling for local networks..."
GW=$(ip route show | grep default | awk '{print $3}' | head -n 1)
if [ -n "$GW" ]; then
    echo "Default gateway found: $GW"
    ip route add 10.0.0.0/8 via $GW dev eth0 || true
    ip route add 172.16.0.0/12 via $GW dev eth0 || true
    ip route add 192.168.0.0/16 via $GW dev eth0 || true
    echo "Local routes added successfully"
else
    echo "WARNING: Could not determine default gateway, skipping route configuration"
fi

echo "Starting application..."
exec "$@"
