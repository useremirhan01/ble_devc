# ble_commands.py
import asyncio
from bleak import BleakClient
from PyQt6.QtWidgets import QMessageBox

READ_UUID = "9E1547BA-C365-57B5-2947-C5E1C1E1D528"
WRITE_UUID = "772ae377-b3d2-4f8e-4042-5481d1e0098c"
async def read_versions_data(mac_address):
    async with BleakClient(mac_address) as client:
        if not client.is_connected:
            raise ConnectionError("Cihaza bağlanılamadı")
        await client.write_gatt_char(WRITE_UUID, bytearray([0x50, 0x01, 0x0D, 0x0A]), response=True)
        await asyncio.sleep(0.3)
        data = await client.read_gatt_char(READ_UUID)
        # ▶️ Gelen veri en az 2 byte olmalı:
        if data is None or len(data) < 2:
            raise ValueError(f"Cevap beklenen uzunlukta değil ({len(data) if data else 0} byte geldi)")
        yaz, don = data[0], data[1]
        return yaz, don

    
# ble_commands.py içinde:

async def read_yazilim_donanim_version(mac_address, yazilim_field, donanim_field, parent=None):
    """
    Cihaza bağlanır, CR+LF eklenmiş komutu yazar,
    indicate üzerinden yanıtı okur ve sırasıyla
    yazılım ile donanım versiyonunu UI alanlarına yazar.
    """
    try:
        async with BleakClient(mac_address) as client:
            await client.connect()
            if not client.is_connected:
                raise ConnectionError("Cihaza bağlanılamadı.")

            # 1) Indicate aboneliği için Future oluştur
            loop   = asyncio.get_running_loop()
            future = loop.create_future()

            def handler(handle, data: bytearray):
                if not future.done():
                    future.set_result(data)

            await client.start_notify(INDICATE_UUID, handler)

            # 2) Komutu CR+LF ile gönder ve response iste
            payload = bytearray([0x50, 0x01, 0x0D, 0x0A])
            await client.write_gatt_char(WRITE_UUID, payload, response=True)

            # 3) Yanıtı bekle (timeout isteğe bağlı)
            data = await asyncio.wait_for(future, timeout=5.0)

            # 4) Temizlik
            await client.stop_notify(INDICATE_UUID)

            # 5) Uzunluk kontrolü
            if len(data) < 2:
                raise ValueError(f"Cevap beklenen uzunlukta değil ({len(data)} byte geldi)")

            # 6) UI’ı güncelle
            yaz, don = data[0], data[1]
            yazilim_field.setText(f"{yaz:#04x}")
            donanim_field.setText(f"{don:#04x}")

    except Exception as e:
        # Hata durumunda dialog göster
        if parent:
            QMessageBox.critical(parent, "Versiyon Okuma Hatası", str(e))
        else:
            print("Versiyon okuma hatası:", e)
            
            
async def read_yazilim_version_notify(mac_address, yazilim_field, donanim_field, parent=None):
    """
    Cihazın yazılım & donanım versiyonunu, indicate üzerinden okur ve aracınıza yazar.
    """
    # Bu UUID’ler senin cihazına göre değişebilir!
    WRITE_UUID = "2d86686a-53dc-25b3-0c4a-f0e10c8dee20"    # Write karakteristiği
    INDICATE_UUID = "772ae377-b3d2-4f8e-4042-5481d1e0098c" # Indicate/Notify karakteristiği

    try:
        async with BleakClient(mac_address) as client:
            await client.connect()
            if not client.is_connected:
                raise ConnectionError("Cihaza bağlanılamadı.")

            # 1) Indicate handler hazırlayıp abone ol
            future = asyncio.get_event_loop().create_future()
            def handler(handle, data: bytearray):
                if not future.done():
                    future.set_result(data)

            await client.start_notify(INDICATE_UUID, handler)

            # 2) Komutu CR+LF ile gönder ve Response iste
            payload = bytearray([0x50, 0x01, 0x0D, 0x0A])
            await client.write_gatt_char(WRITE_UUID, payload, response=True)

            # 3) İndikatörden gelecek cevabı bekle (timeout isteğe bağlı)
            data = await asyncio.wait_for(future, timeout=3.0)

            # 4) Temizlik
            await client.stop_notify(INDICATE_UUID)

            # 5) Doğruluk kontrolü
            if len(data) < 2:
                raise ValueError(f"Cevap beklenen uzunlukta değil ({len(data)} byte geldi)")

            # 6) UI’ı güncelle
            yaz, don = data[0], data[1]
            yazilim_field.setText(f"{yaz:#04x}")
            donanim_field.setText(f"{don:#04x}")

    except Exception as e:
        # Hata durumunda dialog göster
        if parent:
            QMessageBox.critical(parent, "Oku Hatası", str(e))
        else:
            print("Oku hatası:", e)



async def write_yazilim_version(mac_address, yazilim_field, parent=None):
    """
    Yazılım versiyonunu cihaza gönderir (write).
    
    :param mac_address: Cihaza bağlanmak için MAC adresi
    :param yazilim_field: QLineEdit içindeki değer alınır (örn: 0x10)
    :param parent: QMessageBox için opsiyonel QWidget referansı
    """
    try:
        versiyon_str = yazilim_field.text().strip()
        versiyon = int(versiyon_str, 0)  # otomatik 0x destekli dönüşüm
        
        if not (0 <= versiyon <= 0xFF):
            raise ValueError("Versiyon değeri 0-255 (0x00-0xFF) arasında olmalı.")
        
        async with BleakClient(mac_address) as client:
            if await client.is_connected():
                await client.write_gatt_char(
                    WRITE_UUID,
                    bytearray([0x50, 0x02, versiyon])
                )
                print(f"Yazılım versiyonu {versiyon:#04x} olarak gönderildi.")
    except Exception as e:
        if parent:
            QMessageBox.critical(parent, "Yazma Hatası", str(e))
        else:
            print("BLE yazma hatası:", e)

async def write_donanim_version(mac_address, donanim_field, parent=None):
    try:
        versiyon_str = donanim_field.text().strip()
        versiyon = int(versiyon_str, 0)  # otomatik 0x/dec destekler

        if not (0 <= versiyon <= 0xFF):
            raise ValueError("Versiyon 0-255 arasında olmalı.")

        async with BleakClient(mac_address) as client:
            if await client.is_connected():
                await client.write_gatt_char(
                    WRITE_UUID,
                    bytearray([0x50, 0x03, versiyon])  # komut: donanım versiyonu yaz
                )
                print(f"Donanım versiyonu {versiyon:#04x} olarak gönderildi.")
    except Exception as e:
        if parent:
            QMessageBox.critical(parent, "Yazma Hatası", str(e))
        else:
            print("Donanım versiyonu yazılamadı:", e)

async def write_donanim_version(mac_address, donanim_field, parent=None):
    """
    Donanım versiyonunu cihaza gönderir (write).
    
    :param mac_address: BLE cihaz MAC adresi
    :param donanim_field: QLineEdit içinden alınan versiyon değeri (örn: 0x20)
    :param parent: Opsiyonel UI referansı (QWidget) hata gösterimi için
    """
    try:
        versiyon_str = donanim_field.text().strip()
        versiyon = int(versiyon_str, 0)  # 0x20 veya 32 gibi girişi işler

        if not (0 <= versiyon <= 0xFF):
            raise ValueError("Versiyon 0-255 aralığında olmalı.")

        async with BleakClient(mac_address) as client:
            if await client.is_connected():
                await client.write_gatt_char(
                    WRITE_UUID,
                    bytearray([0x50, 0x03, versiyon])
                )
                print(f"Donanım versiyonu {versiyon:#04x} olarak gönderildi.")
    except Exception as e:
        if parent:
            QMessageBox.critical(parent, "Donanım Yazma Hatası", str(e))
        else:
            print("Donanım versiyonu yazma hatası:", e)

async def read_afe_value(mac_address, read_command_code, target_field, parent=None):
    try:
        async with BleakClient(mac_address) as client:
            if await client.is_connected():
                # Okuma komutunu gönder
                await client.write_gatt_char(
                    WRITE_UUID,
                    bytearray([0x52, read_command_code])
                )
                await asyncio.sleep(0.5)  # cihazdan cevap gelmesi için bekleme süresi

                # Karakteristikten cevabı oku
                data = await client.read_gatt_char(READ_UUID)
                if data and len(data) > 0:
                    hex_value = f"{data[0]:#04x}"
                    target_field.setText(hex_value)
                    print(f"AFE {read_command_code:#04x} OKUNDU: {hex_value}")
                else:
                    raise ValueError("Cihazdan geçerli veri alınamadı.")
    except Exception as e:
        if parent:
            QMessageBox.critical(parent, "AFE Okuma Hatası", str(e))
        else:
            print("AFE okuma hatası:", e)


async def write_afe_value(mac_address, command_code, value_field, parent=None):
    try:
        value_str = value_field.text().strip()
        value = int(value_str, 0)

        if not (0 <= value <= 0xFF):
            raise ValueError("Değer 0-255 arasında olmalı.")

        async with BleakClient(mac_address) as client:
            if await client.is_connected():
                await client.write_gatt_char(
                    WRITE_UUID,
                    bytearray([0x52, command_code, value])
                )
                print(f"AFE {command_code:#04x} komutuyla {value:#04x} yazıldı.")
    except Exception as e:
        if parent:
            QMessageBox.critical(parent, "AFE Yazma Hatası", str(e))
        else:
            print("AFE yazma hatası:", e)
            
async def read_calisma_suresi(mac_address, target_field, parent=None):
    try:
        async with BleakClient(mac_address) as client:
            if await client.is_connected():
                await client.write_gatt_char(WRITE_UUID, bytearray([0x51, 0x01]))
                await asyncio.sleep(0.3)
                data = await client.read_gatt_char(READ_UUID)
                if data:
                    sure = int.from_bytes(data[:1], byteorder='little')
                    target_field.setText(str(sure))
                    print(f"Çalışma süresi okundu: {sure} sn")
                else:
                    raise ValueError("Veri alınamadı.")
    except Exception as e:
        if parent:
            QMessageBox.critical(parent, "Çalışma Süresi Okuma Hatası", str(e))
        else:
            print("Çalışma süresi okuma hatası:", e)

async def write_calisma_suresi(mac_address, value_field, parent=None):
    try:
        value_str = value_field.text().strip()
        value = int(value_str)

        if not (0 <= value <= 255):
            raise ValueError("Çalışma süresi 0–255 arasında olmalı.")

        async with BleakClient(mac_address) as client:
            if await client.is_connected():
                await client.write_gatt_char(
                    WRITE_UUID,
                    bytearray([0x51, 0x02, value])
                )
                print(f"Çalışma süresi {value} sn olarak gönderildi.")
    except Exception as e:
        if parent:
            QMessageBox.critical(parent, "Çalışma Süresi Yazma Hatası", str(e))
        else:
            print("Çalışma süresi yazma hatası:", e)

async def read_glucose_thresholds(mac_address, field_dict, parent=None):
    try:
        async with BleakClient(mac_address) as client:
            if await client.is_connected():
                await client.write_gatt_char(WRITE_UUID, bytearray([0x53, 0x01]))
                await asyncio.sleep(0.3)
                data = await client.read_gatt_char(READ_UUID)

                if data and len(data) >= 3:
                    field_dict["Düşük"].setText(str(data[0]))
                    field_dict["Normal"].setText(str(data[1]))
                    field_dict["Yüksek"].setText(str(data[2]))
                    print("Glikoz eşikleri okundu:", list(data[:3]))
                else:
                    raise ValueError("Glikoz eşik verisi eksik.")
    except Exception as e:
        if parent:
            QMessageBox.critical(parent, "Glikoz Okuma Hatası", str(e))
        else:
            print("Glikoz okuma hatası:", e)

async def write_glucose_thresholds(mac_address, field_dict, parent=None):
    try:
        low = int(field_dict["Düşük"].text())
        normal = int(field_dict["Normal"].text())
        high = int(field_dict["Yüksek"].text())

        for v in (low, normal, high):
            if not (0 <= v <= 255):
                raise ValueError("Her eşik 0–255 aralığında olmalı.")

        payload = bytearray([0x53, 0x02, low, normal, high])

        async with BleakClient(mac_address) as client:
            if await client.is_connected():
                await client.write_gatt_char(WRITE_UUID, payload)
                print("Glikoz eşikleri gönderildi:", list(payload[2:]))
    except Exception as e:
        if parent:
            QMessageBox.critical(parent, "Glikoz Yazma Hatası", str(e))
        else:
            print("Glikoz yazma hatası:", e)

async def read_temperature_thresholds(mac_address, field_dict, parent=None):
    try:
        async with BleakClient(mac_address) as client:
            if await client.is_connected():
                await client.write_gatt_char(WRITE_UUID, bytearray([0x54, 0x01]))
                await asyncio.sleep(0.3)
                data = await client.read_gatt_char(READ_UUID)

                if data and len(data) >= 2:
                    field_dict["Düşük"].setText(str(data[0]))
                    field_dict["Yüksek"].setText(str(data[1]))
                    print("Sıcaklık eşikleri okundu:", list(data[:2]))
                else:
                    raise ValueError("Sıcaklık verisi eksik veya hatalı.")
    except Exception as e:
        if parent:
            QMessageBox.critical(parent, "Sıcaklık Okuma Hatası", str(e))
        else:
            print("Sıcaklık okuma hatası:", e)

async def write_temperature_thresholds(mac_address, field_dict, parent=None):
    try:
        low = int(field_dict["Düşük"].text())
        high = int(field_dict["Yüksek"].text())

        for v in (low, high):
            if not (0 <= v <= 255):
                raise ValueError("Her sıcaklık değeri 0–255 arasında olmalı.")

        payload = bytearray([0x54, 0x02, low, high])

        async with BleakClient(mac_address) as client:
            if await client.is_connected():
                await client.write_gatt_char(WRITE_UUID, payload)
                print("Sıcaklık eşikleri gönderildi:", list(payload[2:]))
    except Exception as e:
        if parent:
            QMessageBox.critical(parent, "Sıcaklık Yazma Hatası", str(e))
        else:
            print("Sıcaklık yazma hatası:", e)
            
async def read_vibration_status(mac_address, label_widget, parent=None):
    try:
        async with BleakClient(mac_address) as client:
            if await client.is_connected():
                await client.write_gatt_char(WRITE_UUID, bytearray([0x55, 0x01]))
                await asyncio.sleep(0.3)
                data = await client.read_gatt_char(READ_UUID)
                if data and len(data) > 0:
                    status = data[0]
                    if status == 1:
                        label_widget.setText("AÇIK")
                        label_widget.setStyleSheet("color: green; font-weight: bold;")
                    else:
                        label_widget.setText("KAPALI")
                        label_widget.setStyleSheet("color: red; font-weight: bold;")
                else:
                    raise ValueError("Cihazdan geçerli titreşim bilgisi alınamadı.")
    except Exception as e:
        if parent:
            QMessageBox.critical(parent, "Titreşim Okuma Hatası", str(e))
        else:
            print("Titreşim okuma hatası:", e)

async def toggle_vibration_status(mac_address, label_widget, parent=None):
    try:
        current_status = label_widget.text().strip().upper()
        new_status = 0x00 if current_status == "AÇIK" else 0x01

        async with BleakClient(mac_address) as client:
            if await client.is_connected():
                await client.write_gatt_char(
                    WRITE_UUID,
                    bytearray([0x55, 0x02, new_status])
                )
                print("Titreşim modu ayarlandı:", "AÇIK" if new_status == 1 else "KAPALI")
                await read_vibration_status(mac_address, label_widget, parent)  # durumu güncelle
    except Exception as e:
        if parent:
            QMessageBox.critical(parent, "Titreşim Yazma Hatası", str(e))
        else:
            print("Titreşim yazma hatası:", e)

def run_if_connected(self, coro_func, *args):
    if not hasattr(self, "selected_mac"):
        QMessageBox.warning(self, "Bağlantı Yok", "Lütfen önce bir cihaza bağlanın.")
        return
    asyncio.create_task(coro_func(self.selected_mac, *args, self))


#titreşim test (on/off) | status: 