# Docker Deployment Guide

This guide explains how to deploy the Auto Voter application using Docker with ExpressVPN support.

## Prerequisites

1.  **Docker** and **Docker Compose** installed.
2.  **ExpressVPN Activation Code**.

## Configuration

1.  **Update ExpressVPN Version (Optional)**:
    The `Dockerfile` downloads a specific version of ExpressVPN. If this version is outdated or the link is broken, update the URL in `Dockerfile`:
    ```dockerfile
    RUN wget -q https://www.expressvpn.works/clients/linux/expressvpn_3.70.0.2-1_amd64.deb ...
    ```
    You can find the latest link on the [ExpressVPN website](https://www.expressvpn.com/setup#linux).

2.  **Set Activation Code**:
    You need to provide your ExpressVPN activation code. You can do this by creating a `.env` file in the project root (do not commit this file to git):
    ```bash
    EXPRESSVPN_ACTIVATION_CODE=your_code_here
    ```
    Or export it in your shell:
    ```bash
    export EXPRESSVPN_ACTIVATION_CODE=your_code_here
    ```

## Building and Running

1.  **Build the images**:
    ```bash
    docker-compose build
    ```

2.  **Run the containers**:
    ```bash
    docker-compose up -d
    ```

3.  **Check logs**:
    ```bash
    docker-compose logs -f
    ```
    You should see "Activating ExpressVPN..." followed by successful activation messages.

## Troubleshooting

*   **VPN Connection Failed**: Ensure the container has `NET_ADMIN` capability and access to `/dev/net/tun`. This is configured in `docker-compose.yml`.
*   **Activation Failed**: Check your activation code. Ensure the container has internet access.
*   **Daemon Not Running**: The `entrypoint.sh` script attempts to start `expressvpnd`. If it fails, check the logs for error messages.

## Notes

*   The application uses `gevent` for async support, which is configured in the `CMD` of the Dockerfile.
*   The `entrypoint.sh` script automatically configures ExpressVPN to use Lightway UDP and auto-connect.
