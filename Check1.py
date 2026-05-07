import numpy as np
import serial
import serial.tools.list_ports
import time
import sys
import signal
import logging
from rtlsdr import RtlSdr

# --- SWARM CONFIGURATION ---
NODE_ID = 2  # Change this for Node 2, 3, and 4
TOTAL_NODES = 4
SLOT_DURATION = 1.0  # Dropped to 1 second for faster localization updates
CYCLE_DURATION = TOTAL_NODES * SLOT_DURATION
LORA_BAUD = 9600
SDR_FREQ = 446.450e6
SDR_SAMPLE_RATE = 2.048e6

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class LocalizationNode:
    def __init__(self):
        self.node_id = NODE_ID
        self.running = True
        self.sdr = None
        self.lora = None
        
        # Trap termination signals to prevent SDR locking
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

        port = self._find_lora_port()
        if not port:
            logging.critical("No LoRa module found. Halting.")
            sys.exit(1)

        try:
            self.lora = serial.Serial(port, LORA_BAUD, timeout=0.1)
            self.sdr = RtlSdr()
            self._configure_sdr()
            logging.info(f"Localization Node {self.node_id} armed on {port}")
        except Exception as e:
            logging.critical(f"Hardware Boot Failure: {e}")
            self.shutdown(None, None)

    def _find_lora_port(self):
        """
        Finds possible LoRa serial ports robustly.
        Tries ttyUSB*, ttyACM*, and USB-Serial adapters.
        """
        candidates = []

        ports = list(serial.tools.list_ports.comports())

        for port in ports:
            device = port.device
            description = port.description.upper()
            hwid = port.hwid.upper()

            logging.info(f"Detected serial candidate: {device} | {description} | {hwid}")

            if (
                "USB" in device.upper()
                or "TTYUSB" in device.upper()
                or "TTYACM" in device.upper()
                or "USB" in description
                or "SERIAL" in description
                or "CH340" in description
                or "CP210" in description
                or "FTDI" in description
            ):
                candidates.append(device)

        for device in candidates:
            try:
                test_serial = serial.Serial(device, LORA_BAUD, timeout=0.2)
                test_serial.close()
                logging.info(f"LoRa serial port selected: {device}")
                return device
            except Exception as e:
                logging.warning(f"Port rejected: {device} | {e}")

        return None

    def _configure_sdr(self):
        self.sdr.sample_rate = SDR_SAMPLE_RATE
        self.sdr.center_freq = SDR_FREQ
        self.sdr.gain = 'auto'

    def get_filtered_rssi(self):
        """Takes a burst of 3 readings and returns the median to eliminate RF spikes."""
        readings = []
        try:
            for _ in range(3):
                _ = self.sdr.read_samples(256)  # Flush stale buffer quickly
                samples = self.sdr.read_samples(16384) # Smaller sample for 1GB Pi processing speed
                power = np.mean(np.abs(samples)**2)
                dbm = 10 * np.log10(power + 1e-12)
                readings.append(dbm)
            
            return int(np.median(readings)) # Integer saves LoRa payload space
        except Exception as e:
            logging.warning(f"SDR Read Error: {e}")
            return -120 

    def transmit(self, rssi):
        payload = f"N{self.node_id},{rssi}\n"
        try:
            self.lora.write(payload.encode('ascii'))
            self.lora.flush()
            logging.info(f"TX -> {payload.strip()}")
        except Exception as e:
            logging.error(f"LoRa TX Failure: {e}")

    def shutdown(self, signum, frame):
        logging.info("Initiating graceful teardown...")
        self.running = False
        if self.sdr:
            self.sdr.close()
        if self.lora:
            self.lora.close()
        logging.info("Hardware released. Node disarmed.")
        sys.exit(0)

    def run(self):
        logging.info(f"TDMA Grid Started. Cycle: {CYCLE_DURATION}s")
        start_anchor = time.monotonic() # Bulletproof timing

        while self.running:
            current_time = time.monotonic()
            elapsed = (current_time - start_anchor) % CYCLE_DURATION
            
            slot_start = (self.node_id - 1) * SLOT_DURATION
            slot_end = slot_start + SLOT_DURATION

            if slot_start <= elapsed < slot_end:
                val = self.get_filtered_rssi()
                self.transmit(val)
                
                # Sleep safely until the slot ends
                now = time.monotonic()
                remaining = slot_end - ((now - start_anchor) % CYCLE_DURATION)
                if remaining > 0.05:
                    time.sleep(remaining - 0.02)
            else:
                time.sleep(0.05)

if __name__ == "__main__":
    node = LocalizationNode()
    node.run()
