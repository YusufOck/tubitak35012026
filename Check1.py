import numpy as np
import serial
import serial.tools.list_ports
import time
import sys
import signal
import logging
from rtlsdr import RtlSdr

# --- SWARM CONFIGURATION ---
NODE_ID = 2
TOTAL_NODES = 4
SLOT_DURATION = 1.0
CYCLE_DURATION = TOTAL_NODES * SLOT_DURATION
LORA_BAUD = 9600
SDR_FREQ = 446.450e6
SDR_SAMPLE_RATE = 2.048e6

# --- RETRY SETTINGS ---
LORA_RETRY_DELAY = 2
SDR_RETRY_DELAY = 3

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


class LocalizationNode:
    def __init__(self):
        self.node_id = NODE_ID
        self.running = True
        self.sdr = None
        self.lora = None

        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

        self.connect_hardware()

    # -------------------------------------------------
    # PORT SEARCH
    # -------------------------------------------------
    def list_serial_candidates(self):
        """
        Finds all possible serial ports.
        This includes ttyUSB, ttyACM and USB-Serial adapters.
        """
        candidates = []
        ports = list(serial.tools.list_ports.comports())

        for port in ports:
            device = port.device
            desc = (port.description or "").upper()
            hwid = (port.hwid or "").upper()

            logging.info(f"Detected port: {device} | {desc} | {hwid}")

            if (
                "TTYUSB" in device.upper()
                or "TTYACM" in device.upper()
                or "USB" in desc
                or "SERIAL" in desc
                or "CH340" in desc
                or "CP210" in desc
                or "FTDI" in desc
                or "UART" in desc
            ):
                candidates.append(device)

        # Remove duplicates
        candidates = list(dict.fromkeys(candidates))
        return candidates

    def find_working_lora_port(self):
        """
        Tries every candidate port until one opens successfully.
        """
        candidates = self.list_serial_candidates()

        if not candidates:
            logging.warning("No serial port candidate found.")
            return None

        for device in candidates:
            try:
                logging.info(f"Trying LoRa port: {device}")
                test = serial.Serial(device, LORA_BAUD, timeout=0.2)
                test.close()
                logging.info(f"Working LoRa port found: {device}")
                return device
            except Exception as e:
                logging.warning(f"Port failed: {device} | {e}")

        return None

    # -------------------------------------------------
    # HARDWARE CONNECT / RECONNECT
    # -------------------------------------------------
    def connect_lora(self):
        """
        Keeps trying until LoRa serial port is connected.
        """
        while self.running:
            port = self.find_working_lora_port()

            if not port:
                logging.warning(f"No LoRa port available. Retrying in {LORA_RETRY_DELAY}s...")
                time.sleep(LORA_RETRY_DELAY)
                continue

            try:
                self.lora = serial.Serial(port, LORA_BAUD, timeout=0.1)
                logging.info(f"LoRa connected on {port}")
                return True
            except Exception as e:
                logging.warning(f"Could not open LoRa on {port}: {e}")
                self.safe_close_lora()
                time.sleep(LORA_RETRY_DELAY)

        return False

    def connect_sdr(self):
        """
        Keeps trying until RTL-SDR is connected.
        """
        while self.running:
            try:
                self.sdr = RtlSdr()
                self.configure_sdr()
                logging.info("RTL-SDR connected and configured.")
                return True
            except Exception as e:
                logging.warning(f"SDR connection failed: {e}. Retrying in {SDR_RETRY_DELAY}s...")
                self.safe_close_sdr()
                time.sleep(SDR_RETRY_DELAY)

        return False

    def connect_hardware(self):
        """
        Connects both LoRa and SDR.
        If one is missing at boot, it waits instead of crashing.
        """
        logging.info("Waiting for hardware...")

        self.connect_lora()
        self.connect_sdr()

        logging.info(f"Localization Node {self.node_id} armed.")

    def reconnect_lora(self):
        """
        Reconnects LoRa after write failure or USB reset.
        """
        logging.warning("Reconnecting LoRa...")
        self.safe_close_lora()
        return self.connect_lora()

    def reconnect_sdr(self):
        """
        Reconnects SDR after read failure if needed.
        """
        logging.warning("Reconnecting SDR...")
        self.safe_close_sdr()
        return self.connect_sdr()

    # -------------------------------------------------
    # SDR
    # -------------------------------------------------
    def configure_sdr(self):
        self.sdr.sample_rate = SDR_SAMPLE_RATE
        self.sdr.center_freq = SDR_FREQ
        self.sdr.gain = "auto"

    def get_filtered_rssi(self):
        readings = []

        try:
            for _ in range(3):
                _ = self.sdr.read_samples(256)
                samples = self.sdr.read_samples(16384)
                power = np.mean(np.abs(samples) ** 2)
                dbm = 10 * np.log10(power + 1e-12)
                readings.append(dbm)

            return int(np.median(readings))

        except Exception as e:
            logging.error(f"SDR Read Error: {e}")
            self.reconnect_sdr()
            return -120

    # -------------------------------------------------
    # LORA TX
    # -------------------------------------------------
    def transmit(self, rssi):
        payload = f"N{self.node_id},{rssi}\n"

        for attempt in range(2):
            try:
                if self.lora is None or not self.lora.is_open:
                    self.reconnect_lora()

                self.lora.write(payload.encode("ascii"))
                self.lora.flush()
                logging.info(f"TX -> {payload.strip()}")
                return True

            except Exception as e:
                logging.error(f"LoRa TX Failure: {e}")
                self.reconnect_lora()

        logging.error("LoRa TX failed after reconnect attempt.")
        return False

    # -------------------------------------------------
    # SAFE CLOSE
    # -------------------------------------------------
    def safe_close_lora(self):
        try:
            if self.lora:
                self.lora.close()
        except Exception:
            pass
        self.lora = None

    def safe_close_sdr(self):
        try:
            if self.sdr:
                self.sdr.close()
        except Exception:
            pass
        self.sdr = None

    # -------------------------------------------------
    # SHUTDOWN
    # -------------------------------------------------
    def shutdown(self, signum, frame):
        logging.info("Initiating graceful teardown...")
        self.running = False
        self.safe_close_sdr()
        self.safe_close_lora()
        logging.info("Hardware released. Node disarmed.")
        sys.exit(0)

    # -------------------------------------------------
    # MAIN LOOP
    # -------------------------------------------------
    def run(self):
        logging.info(f"TDMA Grid Started. Cycle: {CYCLE_DURATION}s")
        start_anchor = time.monotonic()

        while self.running:
            current_time = time.monotonic()
            elapsed = (current_time - start_anchor) % CYCLE_DURATION

            slot_start = (self.node_id - 1) * SLOT_DURATION
            slot_end = slot_start + SLOT_DURATION

            if slot_start <= elapsed < slot_end:
                rssi = self.get_filtered_rssi()
                self.transmit(rssi)

                now = time.monotonic()
                remaining = slot_end - ((now - start_anchor) % CYCLE_DURATION)

                if remaining > 0.05:
                    time.sleep(remaining - 0.02)
            else:
                time.sleep(0.05)


if __name__ == "__main__":
    node = LocalizationNode()
    node.run()