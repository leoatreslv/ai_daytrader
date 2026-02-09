# Walkthrough - AI Day Trader Enhancements

## Features Implemented

### 1. LLM Bias Integration
-   **What**: The strategy now consults the LLM every 30 minutes to get a market sentiment bias (BULLISH/BEARISH/NEUTRAL).
-   **Why**: To filter technical signals against a broader "AI intuition" or macro view.
-   **How**:
    -   `strategy.py`: `update_llm_bias()` fetches sentiment.
    -   `strategy.py`: `check_signal()` uses bias to approve/reject RSI+BB signals.

### 2. Common Logging
-   **What**: Centralized logging to `trading_system.log` and Console.
-   **Why**: To have a persistent record of trades, errors, and logic for debugging.
-   **How**:
    -   Created `logger.py`.
    -   Integrated into all core modules (`main.py`, `strategy.py`, `llm_client.py`, `ctrader_fix_client.py`).

### 3. Graceful Termination
-   **What**: Responsive shutdown mechanism.
-   **Why**: Accessing `send_command_input` was unreliable for long sleeps.
-   **How**:
    -   Passes `stop.txt` check into `main.py` loops constantly.
    -   Use `smart_sleep(seconds)` instead of `time.sleep(seconds)`.
    -   To stop: Create a file named `stop.txt` in the app directory.

### 4. Linux Portability (Docker)
-   **What**: Containerized the application for running on Linux/Cloud.
-   **files**: `Dockerfile`, `docker-compose.yml`, `.dockerignore`.
-   **How to Run**:
    ```bash
    # Build
    docker-compose build
    
    # Run (Detached)
    docker-compose up -d
    
    # View Logs
    docker-compose logs -f
    
    # Stop
    docker-compose down
    ```

### Troubleshooting
**Error: `PermissionError: [Errno 13] Permission denied`**
This happens on Linux if your user doesn't have access to the Docker socket.
*   **Quick Fix**: Run with sudo: `sudo docker-compose up -d --build`
*   **Permanent Fix**: Add your user to the docker group:
    ```bash
    sudo usermod -aG docker $USER
    newgrp docker
    ```

**Error: `KeyError: 'ContainerConfig'` (Persistent)**
If `docker rm` didn't work, you likely have "orphan" containers or containers with different names.
*   **Best Fix**: Run the provided cleanup script:
    ```bash
    chmod +x clean_docker.sh
    ./clean_docker.sh
    ```
*   **Manual Fix**:
    1.  List all containers: `docker ps -a`
    2.  Remove **ANY** container related to this project (look for `ai_daytrader`, `ai_trader`, or random names if you see the ID `d7327e3dea85` from your error).
    3.  Run: `docker rm -f <container_id>`

**Error: `[QUOTE] Read error: 56` (SSL Handshake Failure)**
This happens because newer Linux/Python versions (OpenSSL 3.0+) are too strict for some legacy cTrader servers.
*   **Fix Implemented**: We switched the Docker image to `python:3.11-slim-bullseye` (OpenSSL 1.1) and relaxed SSL security levels in `ctrader_fix_client.py`.
*   **Action**: Ensure you pull the latest code and rebuild: `docker-compose up -d --build`

**Error: `[QUOTE] Read error: 56` (Immediate Disconnect)**
If SSL connects but immediately disconnects with "Read error: 56", the server likely rejected the Logon message.
*   **Cause**: Sending `TargetSubID` (Tag 57) when the server doesn't expect it.
*   **Fix Implemented**: Removed Tag 57 from `ctrader_fix_client.py`.
*   **Action**: Rebuild: `docker-compose up -d --build`

**Error: `ModuleNotFoundError: No module named 'pkg_resources'`**
Occurs during build or runtime because `setuptools` is missing in modern Python environments.
*   **Fix Implemented**:
    1.  Upgraded build tools in `Dockerfile`.
    2.  Added `--no-build-isolation` to `pip install`.
    3.  Added `setuptools` to `requirements.txt`.
*   **Action**: Rebuild the container: `docker-compose up -d --build`

## Verification

### Logging & Connection
Ran `main.py`, verified logs:
```
2026-02-09 10:43:13,861 - FixClient - INFO - Connected to cTrader.
2026-02-09 10:43:13,861 - Main - INFO - Subscribing to 41...
2026-02-09 10:43:13,862 - Main - INFO - Entering Main Loop...
```

### Shutdown Test
Created `stop.txt` while running, verified immediate stop:
```
2026-02-09 10:43:29,873 - Main - INFO - Stop signal received (stop.txt). Stopping...
```
