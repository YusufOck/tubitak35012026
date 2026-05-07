# UAV Localization Swarm: V2 Edge Architecture Update

## Overview
This document outlines the critical upgrades made to the telemetry node software and deployment architecture for our UAV localization swarm. The transition from the V1 bench prototype to the V2 flight-ready system ensures our Raspberry Pi edge nodes are stable, autonomous, and capable of providing clean, filtered data to the ground station solver.

---

## 1. Flight-Ready Code Upgrades (Check1.py)

We overhauled the main Python script to prevent mid-flight crashes and improve the mathematical accuracy of our RSSI readings.

### A. Hardware Stopwatch vs. System Clock (TDMA Drift Fix)
* **What changed:** Replaced `time.time()` with `time.monotonic()`.
* **Why:** The Linux system clock (`time.time()`) can jump forwards or backwards if the Pi syncs with an NTP server mid-flight. This would cause our Time Division Multiple Access (TDMA) slots to drift, resulting in drone radios talking over each other. `time.monotonic()` is a hardware-level stopwatch that cannot be altered by the OS, guaranteeing perfect TDMA synchronization.

### B. Multipath Fading Filter (Median Math)
* **What changed:** Instead of taking one massive SDR sample (65,536 bytes), the node now takes a rapid burst of three smaller samples (16,384 bytes) and transmits the **median** dBm value.
* **Why:** In real-world flight, radio waves bounce off the ground and the carbon fiber drone frame, causing artificial spikes or drops in signal strength (multipath fading). Sending a single raw snapshot ruins localization math. Taking a median filters out these reflections, sending only the true RF baseline to the ground station.

### C. Dynamic Port Discovery
* **What changed:** Replaced the hardcoded `/dev/ttyUSB0` port with a dynamic `_find_lora_port()` function.
* **Why:** If the LoRa module's buffer overflows or the Pi experiences a voltage dip, the Linux kernel resets the USB port and renames it (e.g., to `ttyUSB1`). The old code would crash. The new code dynamically hunts for the active port, surviving USB resets seamlessly.

### D. Payload Optimization (Airtime Diet)
* **What changed:** Changed the payload format from `D1:-85.20` to `N1,-85`.
* **Why:** At a 9600 baud rate, transmitting decimal places takes precious physical airtime and adds no value to our ground-station localization math. Sending an integer in a tight CSV format drastically reduces our transmission footprint, allowing us to safely shrink our `SLOT_DURATION` for faster swarm updates.

### E. Graceful Hardware Teardown
* **What changed:** Added the `signal` library to trap system shutdown commands.
* **Why:** Force-killing the old script left the RTL-SDR hardware engaged, causing a `Resource Busy` error on the next boot. The script now intercepts shutdown commands, safely closes the SDR connection, and unplugs the serial line before exiting.

---

## 2. Autonomous Edge Deployment (Systemd)

We abandoned manual script execution (`python3 script.py`) in favor of a professional, headless Linux daemon. 

### A. Autonomous Boot (No SSH Required)
* **What we did:** Created `/etc/systemd/system/locnode.service`.
* **Impact:** The script is now deeply integrated into the Pi's boot sequence. The moment a battery is plugged into the drone, the OS automatically loads the virtual environment and starts the radio telemetry. No human intervention or SSH connection is needed.

### B. Crash Auto-Recovery
* **What we did:** Configured the service with `Restart=always` and `RestartSec=5`.
* **Impact:** Drones operate in harsh physical environments. If the Python script crashes due to extreme RF interference or a hardware interrupt, the Linux OS will detect the failure and automatically reboot the script 5 seconds later. 

### C. Dependency Isolation
* **What we did:** Pointed the background service directly to an isolated Python virtual environment (`/home/drone1/dron_env/bin/python3`).
* **Impact:** The drone's flight code is completely quarantined from the Raspberry Pi's main operating system. Future system updates or global library changes will never accidentally break our localization dependencies (`numpy`, `pyrtlsdr`, `pyserial`).
