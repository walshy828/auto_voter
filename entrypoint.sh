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
else
    echo "WARNING: ExpressVPN daemon not responding, skipping preference configuration"
fi

echo "Starting application..."
exec "$@"
