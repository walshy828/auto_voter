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

# Wait for daemon to be ready
echo "Waiting for ExpressVPN daemon..."
MAX_RETRIES=15
count=0
while ! expressvpn status >/dev/null 2>&1; do
    sleep 1
    count=$((count+1))
    if [ $count -ge $MAX_RETRIES ]; then
        echo "WARNING: Timed out waiting for ExpressVPN daemon"
        break
    fi
done

# Activate if code is provided
if [ -n "$EXPRESSVPN_ACTIVATION_CODE" ]; then
    echo "Activating ExpressVPN..."
    /usr/bin/expect /app/activate_expressvpn.exp || echo "WARNING: ExpressVPN activation failed"
fi

# Configure preferences (only if daemon is running)
if expressvpn status &>/dev/null; then
    echo "Configuring ExpressVPN preferences..."
    expressvpn preferences set auto_connect false || true
    expressvpn preferences set preferred_protocol auto || true
    expressvpn preferences set send_diagnostics false || true
    # Network lock not available in Docker containers, ignore failure
    expressvpn preferences set network_lock default || echo "network lock not available"
    
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

# Run database migrations
echo "Running database migrations..."
if [ -f "alembic.ini" ]; then
    alembic upgrade head || echo "WARNING: Database migration failed, but continuing..."
else
    echo "alembic.ini not found, skipping migrations"
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
