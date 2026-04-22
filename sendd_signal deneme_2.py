import numpy as np
import serial
import time
import sys
from rtlsdr import RtlSdr

# --- ARCHITECTURAL CONFIGURATION ---
NODE_ID = 4  # Unique ID for each drone
TOTAL_NODES = 4
SLOT_DURATION = 2.0  # Seconds
CYCLE_DURATION = TOTAL_NODES * SLOT_DURATION
LORA_BAUD = 9600
SDR_FREQ = 446.450e6
SDR_SAMPLE_RATE = 2.048e6  # Standard power-of-2 rate for better stability

class AeroGuardianNode:
    def __init__(self, port):
        self.node_id = NODE_ID
        try:
            self.lora = serial.Serial(port, LORA_BAUD, timeout=0.1)
            self.sdr = RtlSdr()
            self.configure_sdr()
            print(f"[SYSTEM] Node {self.node_id} initialized on {port}")
        except Exception as e:
            print(f"[CRITICAL] Initialization Failure: {e}")
            sys.exit(1)

    def configure_sdr(self):
        self.sdr.sample_rate = SDR_SAMPLE_RATE
        self.sdr.center_freq = SDR_FREQ
        self.sdr.gain = 'auto' # Let the AGC handle initial leveling

    def get_signal_strength(self):
        """Measures and calculates the power in dBm with noise floor compensation."""
        try:
            # Drop the initial buffer to ensure fresh data (Pseudo-flush)
            _ = self.sdr.read_samples(1024)
            samples = self.sdr.read_samples(65536) # Optimized sample size for Pi Zero 2W
            power = np.mean(np.abs(samples)**2)
            dbm = 10 * np.log10(power + 1e-12)
            return round(dbm, 2)
        except:
            return -120.0 # Return noise floor on failure

    def transmit(self, value):
        """Binary-efficient string formatting for lower air-time."""
        payload = f"D{self.node_id}:{value}\n"
        try:
            self.lora.write(payload.encode('ascii'))
            self.lora.flush() # Ensure data is physically sent
            print(f"[TX] Node {self.node_id} -> {value} dBm")
        except Exception as e:
            print(f"[ERROR] TX Failure: {e}")

    def run(self):
        print(f"[STATUS] TDMA Cycle Started. Duration: {CYCLE_DURATION}s")
        # Synchronization Anchor
        # NOTE: For real-world robustness, wait for a 'START' packet from Master.
        start_anchor = time.time() 

        while True:
            current_time = time.time()
            elapsed = (current_time - start_anchor) % CYCLE_DURATION
            
            slot_start = (self.node_id - 1) * SLOT_DURATION
            slot_end = slot_start + SLOT_DURATION

            # Check if current time falls within assigned TDMA slot
            if slot_start <= elapsed < slot_end:
                val = self.get_signal_strength()
                self.transmit(val)
                
                # Wait until the end of the slot to prevent double-transmission
                remaining_in_slot = slot_end - ((time.time() - start_anchor) % CYCLE_DURATION)
                if remaining_in_slot > 0:
                    time.sleep(remaining_in_slot)
            else:
                # Sleep briefly to reduce CPU load while waiting for slot
                time.sleep(0.1)

if __name__ == "__main__":
    # In production, use persistent naming like /dev/ttyUSB0 or /dev/serial0
    # For now, we use your discovery logic or direct port
    node = AeroGuardianNode('/dev/ttyUSB0') 
    node.run()