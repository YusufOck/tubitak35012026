import numpy as np
import serial
import serial.tools.list_ports
import time
import sys
from rtlsdr import RtlSdr

# --- ARCHITECTURAL CONFIGURATION ---
NODE_ID = 4  
TOTAL_NODES = 4
SLOT_DURATION = 2.0  
CYCLE_DURATION = TOTAL_NODES * SLOT_DURATION
LORA_BAUD = 9600
SDR_FREQ = 446.450e6
SDR_SAMPLE_RATE = 2.048e6  

class AeroGuardianNode:
    def __init__(self):
        self.node_id = NODE_ID
        self.latest_value = -120.0  # En güncel veriyi tutan değişken
        
        # 1. Otomatik Port Bulma
        port = self.find_lora_port()
        
        try:
            self.lora = serial.Serial(port, LORA_BAUD, timeout=0.1)
            self.sdr = RtlSdr()
            self.configure_sdr()
            print(f"[SYSTEM] Node {self.node_id} initialized on {port}")
        except Exception as e:
            print(f"[CRITICAL] Initialization Failure: {e}")
            sys.exit(1)

    def find_lora_port(self):
        """USB portlarını tarar ve uygun cihazı bulur."""
        ports = serial.tools.list_ports.comports()
        for p in ports:
            if "USB" in p.description.upper() or "UART" in p.description.upper():
                print(f"[AUTO-DETECT] Cihaz bulundu: {p.device}")
                return p.device
        print("[ERROR] LoRa/USB cihazı bulunamadı!")
        sys.exit(1)

    def configure_sdr(self):
        self.sdr.sample_rate = SDR_SAMPLE_RATE
        self.sdr.center_freq = SDR_FREQ
        self.sdr.gain = 'auto'

    def get_signal_strength(self):
        try:
            _ = self.sdr.read_samples(1024)
            samples = self.sdr.read_samples(65536) 
            power = np.mean(np.abs(samples)**2)
            dbm = 10 * np.log10(power + 1e-12)
            return round(dbm, 2)
        except:
            return -120.0 

    def transmit(self):
        """Sadece hafızadaki en güncel veriyi yollar."""
        payload = f"D{self.node_id}:{self.latest_value}\n"
        try:
            self.lora.write(payload.encode('ascii'))
            self.lora.flush() 
            print(f"[TX] Slot Geldi! En güncel veri gönderildi: {self.latest_value} dBm")
        except Exception as e:
            print(f"[ERROR] TX Failure: {e}")

    def run(self):
        print(f"[STATUS] TDMA Cycle Started. Duration: {CYCLE_DURATION}s")
        start_anchor = time.time()
        last_measurement_time = 0

        while True:
            current_time = time.time()
            elapsed = (current_time - start_anchor) % CYCLE_DURATION
            
            # --- SÜREKLİ ÖLÇÜM (Her 1 saniyede bir hafızayı güncelle) ---
            if int(current_time) > last_measurement_time:
                self.latest_value = self.get_signal_strength()
                last_measurement_time = int(current_time)
                print(f"[MONITOR] Ölçüm güncellendi: {self.latest_value} dBm")

            # --- TDMA YAYIN (Sadece kendi slotunda) ---
            slot_start = (self.node_id - 1) * SLOT_DURATION
            slot_end = slot_start + SLOT_DURATION

            if slot_start <= elapsed < slot_end:
                # Slot içindeyiz, hafızadaki en son değeri gönder
                self.transmit()
                
                # Slotun geri kalanında bekle (tekrar gönderimi önlemek için)
                remaining = slot_end - ((time.time() - start_anchor) % CYCLE_DURATION)
                if remaining > 0:
                    time.sleep(remaining)
            else:
                # Kendi slotumuz değilse işlemciyi yormadan ölçüme devam et
                time.sleep(0.05)

if __name__ == "__main__":
    node = AeroGuardianNode() 
    node.run()