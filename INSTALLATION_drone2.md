# INSTALLATION.md — Drone2 Sıfırdan Kurulum Rehberi

Bu rehber, format atılmış temiz bir Raspberry Pi üzerinde `drone2` kullanıcısıyla LoRa + RTL-SDR tabanlı UAV localization node yazılımını otomatik çalışan hale getirmek için hazırlanmıştır.

Hedef durum:

- Raspberry Pi açılır açılmaz telemetry/localization yazılımı otomatik çalışacak.
- Arayüze girip manuel `python ...` çalıştırılmayacak.
- `crontab @reboot` kullanılmayacak.
- Servis `systemd` ile yönetilecek.
- Python bağımlılıkları işletim sistemine karıştırılmadan virtual environment içine kurulacak.
- Drone2 için `NODE_ID = 2` yapılacak.

---

## 0. Neden crontab değil systemd?

Eski yöntem:

```bash
@reboot python3 script.py
```

Bu yöntem bu iş için tırt.

Çünkü:

- Python virtual environment düzgün yüklenmeyebilir.
- Script crash olursa otomatik ayağa kalkmaz.
- Log takibi zayıftır.
- USB LoRa / RTL-SDR hazır olmadan script erken başlayabilir.
- Hangi kullanıcıyla çalıştığı karışır.
- Hata ayıklamak zordur.

Yeni yöntem:

```bash
systemd service
```

Avantajları:

- Raspberry açılınca otomatik başlar.
- Çökerse tekrar başlatır.
- Loglar `journalctl` ile okunur.
- Virtual environment doğrudan çağrılır.
- Servis kolayca start / stop / restart yapılır.
- Drone uçuşa hazırlanırken SSH veya masaüstü arayüzü gerekmez.

---

## 1. Bu rehberde kullanılacak sabit bilgiler

Drone2 için kullanılacak bilgiler:

```bash
DRONE_USER=drone2
NODE_ID=2
REPO_URL=https://github.com/YusufOck/tubitak35012026
PROJECT_DIR=/home/drone2/Desktop/tubitak35012026
VENV_DIR=/home/drone2/drone_env
SERVICE_NAME=locnode.service
PY_FILE=sendd_signal_deneme_2.py
```

> Drone3 kurulacaksa `NODE_ID=3`, Drone4 kurulacaksa `NODE_ID=4` yapılmalıdır.  
> Bütün dronelarda aynı `NODE_ID` kalırsa TDMA çakışır ve LoRa ağı çöker.

---

## 2. Temiz sistem güncellemesi

Raspberry Pi terminalini aç.

```bash
sudo apt update
sudo apt upgrade -y
```

Gerekli sistem paketlerini kur:

```bash
sudo apt install -y \
  git \
  wget \
  nano \
  python3 \
  python3-venv \
  python3-pip \
  rtl-sdr \
  librtlsdr-dev \
  libusb-1.0-0-dev
```

---

## 3. Kullanıcı izinlerini ayarla

LoRa genelde `/dev/ttyUSB0`, `/dev/ttyUSB1` gibi portlardan gelir. Kullanıcının seri porta erişmesi gerekir.

```bash
sudo usermod -aG dialout,plugdev drone2
```

Bu komuttan sonra sistemi yeniden başlat:

```bash
sudo reboot
```

Yeniden açıldıktan sonra tekrar terminal aç.

Kontrol:

```bash
groups
```

Çıktıda şunlar görünmeli:

```bash
dialout plugdev
```

---

## 4. Projeyi Desktop içine çek

```bash
mkdir -p /home/drone2/Desktop
cd /home/drone2/Desktop

git clone https://github.com/YusufOck/tubitak35012026.git
cd /home/drone2/Desktop/tubitak35012026
```

Eğer repo zaten varsa:

```bash
cd /home/drone2/Desktop/tubitak35012026
git pull
```

---

## 5. Osman / Usman telemetry dosyasını yerleştir

Servisin çalıştıracağı dosya adı standart olarak şu olacak:

```bash
sendd_signal_deneme_2.py
```

Eğer dosya repoda `Check1.py` olarak geldiyse:

```bash
cd /home/drone2/Desktop/tubitak35012026
cp Check1.py sendd_signal_deneme_2.py
```

Eğer dosyayı doğrudan GitHub raw üzerinden çekmek gerekiyorsa:

```bash
cd /home/drone2/Desktop/tubitak35012026

wget -O sendd_signal_deneme_2.py \
https://raw.githubusercontent.com/usman2ki/Tubitak3501localization/main/Check1.py
```

Dosyanın oluştuğunu kontrol et:

```bash
ls -l /home/drone2/Desktop/tubitak35012026/sendd_signal_deneme_2.py
```

---

## 6. Drone2 için NODE_ID ayarla

Drone2 için `NODE_ID = 2` olmalı.

Otomatik değiştirmek için:

```bash
sed -i 's/^NODE_ID *= *.*/NODE_ID = 2  # Drone2/' /home/drone2/Desktop/tubitak35012026/sendd_signal_deneme_2.py
```

Kontrol et:

```bash
grep "NODE_ID" /home/drone2/Desktop/tubitak35012026/sendd_signal_deneme_2.py
```

Beklenen çıktı:

```python
NODE_ID = 2  # Drone2
```

Manuel düzenlemek istersen:

```bash
nano /home/drone2/Desktop/tubitak35012026/sendd_signal_deneme_2.py
```

Şu satırı bul:

```python
NODE_ID = 1
```

Şuna çevir:

```python
NODE_ID = 2
```

Kaydet:

```text
Ctrl + O
Enter
Ctrl + X
```

---

## 7. Python virtual environment oluştur

```bash
python3 -m venv /home/drone2/drone_env
```

Aktif et:

```bash
source /home/drone2/drone_env/bin/activate
```

Python ve pip kontrolü:

```bash
which python
which pip
python --version
pip --version
```

Beklenen yol şuna benzemeli:

```bash
/home/drone2/drone_env/bin/python
/home/drone2/drone_env/bin/pip
```

Eğer `pip` hâlâ sistem Python'una gidiyorsa kurulum hatalıdır. Devam etme.

---

## 8. Pip araçlarını güncelle

```bash
python -m pip install --upgrade pip==26.1
```

---

## 9. Gerekli Python kütüphanelerini görseldeki versiyonlarla kur

Görseldeki paketler:

| Paket | Versiyon |
|---|---:|
| numpy | 2.4.4 |
| packaging | 26.2 |
| pip | 26.1 |
| pyrtlsdr | 0.2.93 |
| pyserial | 3.5 |
| setuptools | 69.5.1 |
| wheel | 0.47.0 |

Kurulum:

```bash
pip install \
  numpy==2.4.4 \
  packaging==26.2 \
  pyrtlsdr==0.2.93 \
  pyserial==3.5 \
  setuptools==69.5.1 \
  wheel==0.47.0
```

Kontrol:

```bash
pip list
```

Beklenen çıktıda şunlar görünmeli:

```text
numpy       2.4.4
packaging   26.2
pip         26.1
pyrtlsdr    0.2.93
pyserial    3.5
setuptools  69.5.1
wheel       0.47.0
```

---

## 10. PEP668 / externally-managed-environment hatası alırsan

Normalde virtual environment içindeyken bu hatayı almaman gerekir.

Eğer şu tarz hata alırsan:

```text
error: externally-managed-environment
```

Önce şunu kontrol et:

```bash
which pip
```

Eğer çıktı `/home/drone2/drone_env/bin/pip` değilse yanlış pip kullanıyorsun.

Doğru komut:

```bash
/home/drone2/drone_env/bin/python -m pip install \
  numpy==2.4.4 \
  packaging==26.2 \
  pyrtlsdr==0.2.93 \
  pyserial==3.5 \
  setuptools==69.5.1 \
  wheel==0.47.0
```

Son çare olarak global sisteme kurulum yapılacaksa:

```bash
python3 -m pip install --break-system-packages \
  numpy==2.4.4 \
  packaging==26.2 \
  pyrtlsdr==0.2.93 \
  pyserial==3.5 \
  setuptools==69.5.1 \
  wheel==0.47.0
```

Ama bu yöntem önerilmez. Drone yazılımı için doğru yöntem virtual environment kullanmaktır.

---

## 11. RTL-SDR kernel driver çakışmasını engelle

Bazı Raspberry Pi kurulumlarında RTL-SDR cihazını Linux DVB driver'ı yakalar. Bu durumda Python kodu RTL-SDR'ye erişemez.

Blacklist dosyası oluştur:

```bash
sudo nano /etc/modprobe.d/blacklist-rtl-sdr.conf
```

İçine şunu yaz:

```text
blacklist dvb_usb_rtl28xxu
blacklist rtl2832
blacklist rtl2830
```

Kaydet ve çık.

Sonra reboot:

```bash
sudo reboot
```

---

## 12. Donanım bağlantısını kontrol et

Raspberry açıldıktan sonra LoRa USB portu görünüyor mu?

```bash
ls /dev/ttyUSB*
```

Beklenen örnek:

```bash
/dev/ttyUSB0
```

USB cihazlarını listele:

```bash
lsusb
```

RTL-SDR test:

```bash
rtl_test -t
```

Beklenen şekilde RTL2832 / R820T / R820T2 benzeri tuner bilgisi görünmeli.

Not:

```text
PLL not locked
```

tek başına ölümcül değildir. Anten, frekans, sinyal seviyesi veya ilk başlatma koşullarında görülebilir. Ama sürekli SDR okuma hatası alınıyorsa donanım / anten / driver tarafı tekrar kontrol edilmelidir.

---

## 13. Scripti manuel test et

Servise geçmeden önce script bir kez manuel denenmeli.

```bash
cd /home/drone2/Desktop/tubitak35012026
source /home/drone2/drone_env/bin/activate

python sendd_signal_deneme_2.py
```

Beklenen log örneği:

```text
Localization Node 2 armed on /dev/ttyUSB0
TDMA Grid Started
TX -> N2,-85
```

Çıkmak için:

```text
Ctrl + C
```

Eğer burada çalışmıyorsa systemd tarafına geçme. Önce manuel hata çözülmeli.

---

## 14. systemd service dosyasını oluştur

```bash
sudo nano /etc/systemd/system/locnode.service
```

İçine aynen şunu yapıştır:

```ini
[Unit]
Description=UAV Localization Telemetry Node - Drone2
After=multi-user.target
Wants=multi-user.target

[Service]
Type=simple
User=drone2
Group=drone2
WorkingDirectory=/home/drone2/Desktop/tubitak35012026
ExecStart=/home/drone2/drone_env/bin/python /home/drone2/Desktop/tubitak35012026/sendd_signal_deneme_2.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Kaydet:

```text
Ctrl + O
Enter
Ctrl + X
```

---

## 15. Servisi aktif et

```bash
sudo systemctl daemon-reload
sudo systemctl enable locnode.service
sudo systemctl start locnode.service
```

Durum kontrol:

```bash
sudo systemctl status locnode.service
```

Canlı log:

```bash
sudo journalctl -u locnode.service -f
```

Beklenen örnek:

```text
Localization Node 2 armed on /dev/ttyUSB0
TDMA Grid Started
TX -> N2,-85
```

Logdan çıkmak için:

```text
Ctrl + C
```

---

## 16. Raspberry yeniden başlatma testi

Asıl test budur. Servis manuel değil, boot ile açılmalı.

```bash
sudo reboot
```

Raspberry açıldıktan sonra:

```bash
sudo systemctl status locnode.service
sudo journalctl -u locnode.service -n 50
```

Eğer `TX -> N2,...` görüyorsan Drone2 hazırdır.

---

## 17. Faydalı servis komutları

Servisi durdur:

```bash
sudo systemctl stop locnode.service
```

Servisi başlat:

```bash
sudo systemctl start locnode.service
```

Servisi yeniden başlat:

```bash
sudo systemctl restart locnode.service
```

Servisi boot'tan kaldır:

```bash
sudo systemctl disable locnode.service
```

Servis loglarını canlı izle:

```bash
sudo journalctl -u locnode.service -f
```

Son 100 log:

```bash
sudo journalctl -u locnode.service -n 100
```

Bugünkü loglar:

```bash
sudo journalctl -u locnode.service --since today
```

---

## 18. Güncelleme akışı

Kod GitHub'a pushlandıktan sonra Drone2 üzerinde güncellemek için:

```bash
cd /home/drone2/Desktop/tubitak35012026
git pull
```

Eğer `Check1.py` güncellendiyse ve servis `sendd_signal_deneme_2.py` dosyasını çalıştırıyorsa:

```bash
cp Check1.py sendd_signal_deneme_2.py
sed -i 's/^NODE_ID *= *.*/NODE_ID = 2  # Drone2/' sendd_signal_deneme_2.py
```

Sonra servisi restart et:

```bash
sudo systemctl restart locnode.service
sudo journalctl -u locnode.service -f
```

---

## 19. Drone ID tablosu

| Drone | Linux kullanıcı adı | NODE_ID | TDMA slot |
|---|---|---:|---:|
| Drone1 | drone1 | 1 | 0-1 s |
| Drone2 | drone2 | 2 | 1-2 s |
| Drone3 | drone3 | 3 | 2-3 s |
| Drone4 | drone4 | 4 | 3-4 s |

Kodda şu değerler varsa:

```python
TOTAL_NODES = 4
SLOT_DURATION = 1.0
```

Toplam çevrim:

```text
4 saniye
```

Her drone kendi saniyesinde LoRa paketi basar.

Örnek paketler:

```text
N1,-85
N2,-87
N3,-82
N4,-90
```

---

## 20. En sık hatalar

### Hata 1 — Bütün dronelar NODE_ID=1 kaldı

Belirti:

- LoRa paketleri çakışır.
- Ground station saçma veri alır.
- Bazı paketler bozulur.

Çözüm:

```bash
grep "NODE_ID" /home/drone2/Desktop/tubitak35012026/sendd_signal_deneme_2.py
```

Drone2 için:

```python
NODE_ID = 2
```

---

### Hata 2 — Servis çalışıyor ama LoRa port bulunamıyor

Kontrol:

```bash
ls /dev/ttyUSB*
```

Hiç çıktı yoksa:

- LoRa USB takılı değil.
- Kablo bozuk.
- USB dönüştürücü arızalı.
- Yetki sorunu var.

Yetki kontrol:

```bash
groups
```

`dialout` görünmeli.

---

### Hata 3 — RTL-SDR resource busy

Kontrol:

```bash
rtl_test -t
```

Eğer resource busy alırsan:

```bash
sudo systemctl stop locnode.service
sudo killall python python3
```

Sonra tekrar:

```bash
rtl_test -t
```

Devam ederse blacklist adımını tekrar kontrol et.

---

### Hata 4 — Servis permission denied veriyor

Servis loglarını oku:

```bash
sudo journalctl -u locnode.service -n 100
```

Yetki grupları:

```bash
groups drone2
```

Gerekirse:

```bash
sudo usermod -aG dialout,plugdev drone2
sudo reboot
```

---

### Hata 5 — pip yanlış Python'a kuruyor

Kontrol:

```bash
which python
which pip
```

Doğru çıktı:

```bash
/home/drone2/drone_env/bin/python
/home/drone2/drone_env/bin/pip
```

Yanlışsa:

```bash
source /home/drone2/drone_env/bin/activate
```

veya doğrudan:

```bash
/home/drone2/drone_env/bin/python -m pip list
```

---

## 21. Temiz kurulum tek komut özeti

Aşağıdaki blok, ana kurulum akışının kısa halidir.

```bash
sudo apt update
sudo apt upgrade -y

sudo apt install -y git wget nano python3 python3-venv python3-pip rtl-sdr librtlsdr-dev libusb-1.0-0-dev

sudo usermod -aG dialout,plugdev drone2

mkdir -p /home/drone2/Desktop
cd /home/drone2/Desktop

git clone https://github.com/YusufOck/tubitak35012026.git || true
cd /home/drone2/Desktop/tubitak35012026
git pull || true

if [ -f Check1.py ]; then
  cp Check1.py sendd_signal_deneme_2.py
else
  wget -O sendd_signal_deneme_2.py https://raw.githubusercontent.com/usman2ki/Tubitak3501localization/main/Check1.py
fi

sed -i 's/^NODE_ID *= *.*/NODE_ID = 2  # Drone2/' sendd_signal_deneme_2.py

python3 -m venv /home/drone2/drone_env
/home/drone2/drone_env/bin/python -m pip install --upgrade pip==26.1

/home/drone2/drone_env/bin/python -m pip install \
  numpy==2.4.4 \
  packaging==26.2 \
  pyrtlsdr==0.2.93 \
  pyserial==3.5 \
  setuptools==69.5.1 \
  wheel==0.47.0

sudo tee /etc/modprobe.d/blacklist-rtl-sdr.conf > /dev/null <<'EOF'
blacklist dvb_usb_rtl28xxu
blacklist rtl2832
blacklist rtl2830
EOF

sudo tee /etc/systemd/system/locnode.service > /dev/null <<'EOF'
[Unit]
Description=UAV Localization Telemetry Node - Drone2
After=multi-user.target
Wants=multi-user.target

[Service]
Type=simple
User=drone2
Group=drone2
WorkingDirectory=/home/drone2/Desktop/tubitak35012026
ExecStart=/home/drone2/drone_env/bin/python /home/drone2/Desktop/tubitak35012026/sendd_signal_deneme_2.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable locnode.service

echo "Kurulum bitti. Şimdi reboot at:"
echo "sudo reboot"
```

Reboot sonrası kontrol:

```bash
sudo systemctl status locnode.service
sudo journalctl -u locnode.service -f
```

---

## 22. Final kabul kriteri

Drone2 kurulumu başarılı sayılacaksa şu 5 şart sağlanmalı:

1. Repo şu dizinde olmalı:

```bash
/home/drone2/Desktop/tubitak35012026
```

2. Script şu dosyada olmalı:

```bash
/home/drone2/Desktop/tubitak35012026/sendd_signal_deneme_2.py
```

3. Drone2 ID şu olmalı:

```python
NODE_ID = 2
```

4. Servis aktif olmalı:

```bash
sudo systemctl status locnode.service
```

5. Loglarda TX paketi görünmeli:

```text
TX -> N2,...
```

Bu 5 şart tamamlanmadan drone hazır kabul edilmemelidir.
