import serial
import time
import random # Sadece test verisi üretmek için, gerçek SDR kodunda silinebilir

# --- AYARLAR ---
IHA_ID = "N1" # Diğer dronelarda N2, N3, N4 olarak değiştirilecek
VERI_ON_EKI = "D1" # Diğer dronelarda D2, D3, D4 olarak değiştirilecek
LORA_PORT = "/dev/ttyUSB0" # Raspberry Pi'daki LoRa portu (ttyUSB0 veya ttyACM0 olabilir)
BAUD_RATE = 9600

# Gerçek SDR okuma fonksiyonun buraya gelecek
def sdr_rssi_oku():
    # TODO: Buraya kendi SDR kütüphanen ile RSSI ölçüm kodunu yazmalısın.
    # Şimdilik sistemin çalıştığını görmek için rastgele bir dBm değeri üretiyoruz.
    ornek_dbm = round(random.uniform(-10.0, -90.0), 2)
    return ornek_dbm

def main():
    try:
        # LoRa modülü ile seri haberleşmeyi başlat
        lora = serial.Serial(LORA_PORT, BAUD_RATE, timeout=0.1)
        print(f"[{IHA_ID}] LoRa modülü dinleniyor... Port: {LORA_PORT}")
        
        while True:
            # Arka planda sürekli güncel SDR verisini hazırda tut
            guncel_rssi = sdr_rssi_oku()
            
            # Gelen bir istek var mı diye portu kontrol et
            if lora.in_waiting > 0:
                # Gelen veriyi oku, boşlukları temizle ve string'e çevir
                gelen_istek = lora.readline().decode('utf-8').strip()
                
                # Gelen istek bu İHA'ya mı ait? (Örn: "N1?")
                if gelen_istek == f"{IHA_ID}?":
                    # İstenilen formatta yanıtı oluştur ve gönder
                    yanit = f"{VERI_ON_EKI}:{guncel_rssi}\r\n"
                    lora.write(yanit.encode('utf-8'))
                    print(f"Veri gönderildi: {yanit.strip()}")
            
            # CPU'yu %100 yormamak için çok küçük bir bekleme
            time.sleep(0.01)

    except serial.SerialException as e:
        print(f"Seri port hatası: {e}. Lütfen bağlantıları kontrol et.")
    except KeyboardInterrupt:
        print("\nProgram sonlandırıldı.")
        if 'lora' in locals() and lora.is_open:
            lora.close()

if __name__ == '__main__':
    main()