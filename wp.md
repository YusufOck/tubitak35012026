Step1 cloning the check1.py from github using wget
Command is 
cd /home/drone1/Desktop/tubitak35012026/

wget -O sendd_signal_deneme_2.py https://raw.githubusercontent.com/usman2ki/Tubitak3501localization/main/Check1.py
This command will overwrite the code that already exits in the python file
### Step 2: Assign the Unique Node ID (CRITICAL)
Every drone must have a different ID, or they will transmit at the exact same time and crash the radio network.
Open the code in the text editor:
```bash
nano /home/drone1/Desktop/tubitak35012026/sendd_signal_deneme_2.py

```
Find line 11: NODE_ID = 1
Change 1 to the correct number for this specific drone (2, 3, or 4).
Save and exit (Ctrl+O, Enter, Ctrl+X).
### Step 3: Inject the Required Libraries
Ensure the virtual environment exists and force-install the exact library versions needed for the SDR and LoRa.
```bash
# Create the environment if it doesn't exist yet
python3 -m venv /home/drone1/dron_env

# Inject the libraries directly into the isolated environment
sudo /home/drone1/dron_env/bin/pip install numpy pyserial "setuptools<70.0.0" pyrtlsdr==0.2.7

```
### Step 4: Create the Background Service
Create the autonomous systemd service file so the code runs on boot.
```bash
sudo nano /etc/systemd/system/locnode.service

```
Paste this exact block into the file:
```ini
[Unit]
Description=UAV Localization Telemetry Node
After=network.target

[Service]
Type=simple
User=root
ExecStart=/home/drone1/dron_env/bin/python3 /home/drone1/Desktop/tubitak35012026/sendd_signal_deneme_2.py
WorkingDirectory=/home/drone1/Desktop/tubitak35012026/
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target

```
Save and exit (Ctrl+O, Enter, Ctrl+X).
### Step 5: Arm and Start the Drone
Tell Linux to reload its configurations, enable the service to start on every boot, and start it immediately.
```bash
sudo systemctl daemon-reload
sudo systemctl enable locnode.service
sudo systemctl start locnode.service

```
### Step 6: Verify Telemetry
Check the live logs to ensure the SDR is reading data and the LoRa is transmitting.
```bash
sudo journalctl -u locnode.service -f

```
You should see green text confirming the node is armed, followed by [TX] N2,-85 messages appearing every 4 seconds. Press Ctrl+C to exit the log viewer. The drone is now ready for flight.
"""
with open("SOP_Drone_Deployment_Guide.md", "w") as f:
f.write(content)
print("File generated successfully.")
```
Your Markdown file is ready
[file-tag: code-generated-file-0-1777462036393720085]

I have generated a step-by-step Standard Operating Procedure (SOP) document for your teammates. This covers the entire pipeline from pulling the code to injecting the libraries and arming the systemd daemon. 

### The Most Important Step for Your Team
When your teammates run through this, make absolutely sure they pay attention to **Step 2**. 

If they clone the code and forget to change `NODE_ID = 1` to `2`, `3`, and `4` on the other Pis, all the drones will calculate that they share the exact same TDMA slot (`slot_start = 0`). They will all try to shout over the radio channel at the exact same time, causing massive data packet collisions, and your ground station will receive corrupted garbage strings instead of clean CSV coordinates.

You can drop that Markdown file directly into your Tubitak GitHub repository as a `README` or share it in your team chat. Let me know when the swarm is fully provisioned and you are ready to write the ground station receiver code!

```