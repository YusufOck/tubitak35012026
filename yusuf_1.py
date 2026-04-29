import numpy as np
import serial
import serial.tools.list_ports
import time
import sys
from rtlsdr import RtlSdr
import os
import grp

# --- MİMARİ YAPILANDIRMA ---
NODE_ID = 4  # Her drone için bu ID'yi (1, 2, 3 veya 4) değiştirin
TOTAL_NODES = 4
SLOT_DURATION = 1.5  # Her drone'un veri gönderme aralığı (Saniye)
CYCLE_DURATION = TOTAL_NODES * SLOT_DURATION # Toplam döngü süresi (Örn: 6.0 saniye)
LORA_BAUD = 9600
SDR_FREQ = 446.450e6
SDR_SAMPLE_RATE = 2.048e6

class AeroGuardianNode:
    def __init__(self):
        self.node_id = NODE_ID
        self.lora = None
        self.sdr = RtlSdr()
        self.configure_sdr()
        self.connect_lora() # Otomatik port bulma ve bağlanma

    def connect_lora(self):
        """'dialout' grubuna ait olan tüm seri/USB portlarını otomatik bulur ve bağlanır."""
        while self.lora is None or not self.lora.is_open:
            # pyserial donanımsal portları listeler (USB'ler dahil)
            ports = list(serial.tools.list_ports.comports())
            target_port = None
            
            for p in ports:
                device_path = p.device
                try:
                    # Portun sistem bilgilerini al
                    stat_info = os.stat(device_path)
                    # Grubunu kontrol et (dialout mu?)
                    group_name = grp.getgrgid(stat_info.st_gid).gr_name
                    
                    if group_name == 'dialout':
                        target_port = device_path
                        break # Uygun port bulundu, döngüden çık
                except Exception:
                    # Dosya okunamıyorsa veya yetki yoksa atla
                    continue 
            
            if target_port:
                try:
                    self.lora = serial.Serial(target_port, LORA_BAUD, timeout=0.1)
                    print(f"[SYSTEM] Node {self.node_id} basariyla {target_port} portuna baglandi.")
                except Exception as e:
                    print(f"[ERROR] Porta baglanilamadi ({target_port}): {e}. 2 saniye sonra tekrar denenecek...")
                    time.sleep(2)
            else:
                print("[WARNING] Bekleniyor... 'dialout' grubuna ait USB/Seri cihaz bulunamadi.")
                time.sleep(2)

    def configure_sdr(self):
        self.sdr.sample_rate = SDR_SAMPLE_RATE
        self.sdr.center_freq = SDR_FREQ
        self.sdr.gain = 'auto'

    def get_signal_strength(self):
        try:
            _ = self.sdr.read_samples(1024)
            samples = self.sdr.read_samples(16384)
            power = np.mean(np.abs(samples)**2)
            dbm = 10 * np.log10(power + 1e-12)
            return round(dbm, 2)
        except:
            return -120.0

    def transmit(self, value):
        payload = f"D{self.node_id}:{value}\n"
        try:
            self.lora.write(payload.encode('ascii'))
            self.lora.flush()
            print(f"[TX] Node {self.node_id} gonderdi -> {value} dBm")
        except Exception as e:
            # [Errno 5] hatası yakalandığında portu kapatıp yeniden bağlanmayı dener
            print(f"[CRITICAL] TX Hatasi (Errno 5 olabilir): {e}")
            print("[SYSTEM] Baglanti sifirlaniyor...")
            if self.lora:
                self.lora.close()
            self.connect_lora()

    def run(self):
        print(f"[STATUS] TDMA Basladi. Node ID: {self.node_id}, Dongu: {CYCLE_DURATION}s")
        
        # Bekleme süresince toplanan sinyal verilerini tutacak liste
        signal_buffer = []

        while True:
            # Mutlak zaman kullanımı: Tüm Pi'lerin saatleri senkronizeyse asla çakışmaz.
            current_time = time.time()
            elapsed_in_cycle = current_time % CYCLE_DURATION
            
            # Bu node'un başlangıç ve bitiş zaman aralıkları (Slot)
            slot_start = (self.node_id - 1) * SLOT_DURATION
            slot_end = slot_start + SLOT_DURATION

            # Sürekli SDR dinlemesi yap ve listeye ekle
            current_signal = self.get_signal_strength()
            signal_buffer.append(current_signal)
            
            # Çok fazla veri birikmemesi için listeyi son 10 veriyle sınırla
            if len(signal_buffer) > 10:
                signal_buffer.pop(0)

            # EGER BENIM SIRAM GELDİYSE (Slot içerisindeysem)
            if slot_start <= elapsed_in_cycle < slot_end:
                # Biriken verilerden en güncelini al (listenin son elemanı)
                if signal_buffer:
                    latest_signal = signal_buffer[-1]
                else:
                    latest_signal = current_signal
                
                # Veriyi gönder
                self.transmit(latest_signal)
                
                # Gönderimden sonra, kendi sıramın (slot) bitmesini bekle ki 
                # aynı slot içinde yanlışlıkla 2. kez paket göndermeyeyim.
                time_left_in_slot = slot_end - (time.time() % CYCLE_DURATION)
                if time_left_in_slot > 0:
                    time.sleep(time_left_in_slot)
                
                # Sıram bitti, listeyi temizle ve diğerlerini beklemeye geç
                signal_buffer.clear()
                
            else:
                # Benim sıram değilse (drone beklemedeyse), sadece dinleme yapıp buffer doldurmak için 
                # CPU'yu yormadan kısa bir bekleme yap
                time.sleep(0.1)

if __name__ == "__main__":
    node = AeroGuardianNode() 
    node.run()