from rtlsdr import RtlSdr
import numpy as np
import serial
import serial.tools.list_ports
import time

# --- AYARLAR ---
NODE_ID = 4
SLOT_LENGTH = 2.5
CYCLE_LENGTH = 4 * SLOT_LENGTH
BAUD_RATE = 9600

# Global donanım değişkenleri
lora = None
sdr = None

def find_lora():
    """Bağlı olan USB/Seri cihazları tarar ve LoRa modülünü bulur."""
    ports = serial.tools.list_ports.comports()
    for port in ports:
        # Hem cihaz yolunda (Linux) hem de cihaz açıklamasında (Windows) 'USB' arar
        if "USB" in port.device.upper() or "USB" in port.description.upper():
            try:
                ser = serial.Serial(port.device, BAUD_RATE, timeout=0.3)
                time.sleep(0.1)
                ser.close()
                print(f"LoRa bulundu: {port.device}")
                return port.device
            except:
                pass
    return None

def init_lora():
    """LoRa modülünü başlatır, bulamazsa sürekli dener."""
    global lora
    while True:
        port = find_lora()
        if port:
            try:
                lora = serial.Serial(port, BAUD_RATE, timeout=0.1)
                print(f"LoRa bağlandı: {port}")
                return
            except Exception as e:
                print(f"LoRa bağlanamadı: {e}")
        print("LoRa bulunamadı, tekrar deneniyor...")
        time.sleep(2)

def init_sdr():
    """SDR cihazını başlatır ve frekans ayarlarını yapar."""
    global sdr
    while True:
        try:
            sdr = RtlSdr()
            sdr.sample_rate = 2.4e6
            sdr.center_freq = 446.450e6
            sdr.gain = 5
            print("SDR başarıyla başlatıldı.")
            return
        except Exception as e:
            print(f"SDR başlatılamadı: {e}")
            time.sleep(2)

# --- ANA PROGRAM BAŞLANGICI ---
print(f"Drone {NODE_ID} başlatılıyor...")
init_lora()
init_sdr()

seq_id = 0
start_time = time.time()

while True:
    try:
        current_time = time.time()
        elapsed = (current_time - start_time) % CYCLE_LENGTH
        
        # Bu drone için ayrılmış zaman dilimini (slot) hesapla
        slot_start = (NODE_ID - 1) * SLOT_LENGTH
        slot_end = slot_start + SLOT_LENGTH

        # Eğer şu anki zaman, bu drone'un veri gönderme dilimindeyse:
        if slot_start <= elapsed < slot_end:
            
            # KRİTİK EKLENTİ: Beklerken biriken eski (bayat) SDR verilerini çöpe at.
            # Bu sayede sadece bu saniyeye ait en güncel veriyi ölçmüş oluruz.
            _ = sdr.read_samples(1024) 
            
            # Asıl veriyi oku ve gücünü (dB) hesapla
            samples = sdr.read_samples(128 * 1024)
            Psig = np.mean(np.abs(samples)**2)
            db = 10 * np.log10(Psig + 1e-12)

            msg = f"{seq_id},drone{NODE_ID}:{db:.2f}\n"

            try:
                lora.write(msg.encode('utf-8'))
            except Exception as e:
                print(f"LoRa yazma hatası! Yeniden bağlanılıyor... Hata: {e}")
                init_lora()

            print(f"drone{NODE_ID} gönderildi: {msg.strip()}")
            seq_id += 1
            
            # Gönderim yaptıktan sonra dilim (slot) süresi kadar uyu.
            # Bu, aynı dilim içinde birden fazla mesaj atılmasını engeller.
            time.sleep(SLOT_LENGTH)

        else:
            # Kendi sırası değilse CPU'yu yormamak için çok kısa bekle
            time.sleep(0.05)

    except Exception as e:
        print(f"HATA OLUŞTU: {e} | SDR yeniden başlatılıyor...")
        try:
            if sdr:
                sdr.close()
        except:
            pass
        init_sdr()