#!/bin/bash

# Start ExpressVPN daemon
# Note: The path might vary by version, checking common locations
if [ -f /usr/sbin/expressvpnd ]; then
    /usr/sbin/expressvpnd --start &
elif [ -f /usr/bin/expressvpnd ]; then
    /usr/bin/expressvpnd --start &
else
    echo "ExpressVPN daemon not found!"
fi

sleep 5

# Activate if code is provided
if [ -n "$EXPRESSVPN_ACTIVATION_CODE" ]; then
    echo "Activating ExpressVPN..."
    /usr/bin/expect /app/activate_expressvpn.exp
fi

# Configure preferences
expressvpn preferences set auto_connect true
expressvpn preferences set preferred_protocol lightway_udp
expressvpn preferences set send_diagnostics false

exec "$@"
