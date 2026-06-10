# Airline Radio Streamer & Wi-Fi Setup

This project is a lightweight, zero-dependency Python 3 application and web interface designed to run on a Raspberry Pi or any Debian-based Linux environment. It acts as an internet radio receiver that streams audio directly from the device's hardware audio port using `ffplay` and automates headless Wi-Fi network configuration.

---

## 1. System Requirements & Dependencies

Make sure your Raspberry Pi has the required system packages installed:

```bash
sudo apt update
sudo apt install -y ffmpeg network-manager
```

*   `ffmpeg`: Provides `ffplay` which is used for headless background audio streaming.
*   `network-manager`: Provides the `nmcli` utility used to scan and configure Wi-Fi.

---

## 2. Deploying Files to the Raspberry Pi

1.  Connect to your Raspberry Pi via SSH or open a terminal on it.
2.  Copy or clone this project's files into your home directory under `/home/pi/airline/`.
3.  Ensure the scripts are executable:

```bash
chmod +x /home/pi/airline/app.py
chmod +x /home/pi/airline/wifi_manager.py
```

---

## 3. Running as a Daemon (systemd service)

Running the application as a systemd service allows it to start automatically on system boot, automatically attempt recovery on failures, and run securely in the background.

We have included a pre-configured service template in `airline.service`.

### Step-by-Step Configuration Commands:

1.  **Copy the service file to the systemd directory:**
    ```bash
    sudo cp /home/pi/airline/airline.service /etc/systemd/system/airline.service
    ```

2.  **Verify/Edit paths in the service file:**
    If you installed the application in a directory other than `/home/pi/airline/`, edit the service file to point to your paths:
    ```bash
    sudo nano /etc/systemd/system/airline.service
    ```
    Ensure `WorkingDirectory` and `ExecStart` match your configuration.

3.  **Reload the systemd daemon configuration:**
    ```bash
    sudo systemctl daemon-reload
    ```

4.  **Enable the service (to start automatically on boot):**
    ```bash
    sudo systemctl enable airline.service
    ```

5.  **Start the daemon immediately:**
    ```bash
    sudo systemctl start airline.service
    ```

---

## 4. Monitoring & Troubleshooting Daemon Commands

Use these commands to manage and monitor the background daemon:

*   **Check service runtime status:**
    ```bash
    sudo systemctl status airline.service
    ```

*   **View live application logs (logs tail):**
    ```bash
    sudo journalctl -u airline.service -f -n 50
    ```

*   **Stop the daemon:**
    ```bash
    sudo systemctl stop airline.service
    ```

*   **Restart the daemon:**
    ```bash
    sudo systemctl restart airline.service
    ```

---

## 5. Using the Interface

Once the daemon starts, open your web browser and navigate to:
```
http://<your-raspberry-pi-ip-address>:8000/
```
If your Raspberry Pi is not connected to a Wi-Fi network, the startup sequence will automatically deploy a fallback Access Point hotspot named **`RaspberryRadio`** (Password: **`radio1234`**). Connect your phone/laptop directly to this hotspot, open a browser, and navigate to:
```
http://192.168.12.1:8000/
```
Use the **Wi-Fi Settings** tab on the dashboard to scan and connect the device to your home network.
