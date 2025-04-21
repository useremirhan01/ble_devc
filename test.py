import asyncio
from bleak import BleakScanner, BleakClient, BleakError

# —————— CONFIG ——————
DEVICE_NAME   = "WIZEPOD"
DEVICE_ADDR   = "48:23:35:F4:00:0B"

# WRITE ve INDICATE UUID’leri
WRITE_UUID    = "5a87b4ef-3bfa-76a8-e642-92933c31434f"  # Write Without Response
INDICATE_UUID = "9e1547ba-c365-57b5-2947-c5e1c1e1d528"  # Indicate
# ————————————————————

def to_hex(data: bytes) -> str:
    """0xAA 0xBB 0xCC formatında hex string döner."""
    return ' '.join(f'0x{b:02X}' for b in data)

class Wizepod:
    def __init__(self, addr):
        self.addr     = addr
        self.client   = BleakClient(addr)
        self._evt     = asyncio.Event()
        self._last    = None

    async def connect(self):
        await self.client.connect()
        if not self.client.is_connected:
            raise BleakError("BLE bağlantısı kurulamadı")
        # Indicate callback’i kaydet
        await self.client.start_notify(INDICATE_UUID, self._on_indicate)

    async def disconnect(self):
        try:
            await self.client.stop_notify(INDICATE_UUID)
        except Exception:
            pass
        await self.client.disconnect()

    def _on_indicate(self, sender, data: bytearray):
        # İlk 0x00 bildirimlerini atla
        if data == b'\x00':
            return
        self._last = bytes(data)
        self._evt.set()

    async def send(self, cmd_bytes: list[int], timeout: float = 5.0) -> bytes:
        """
        cmd_bytes: [0x51, 0x02, 0x10] gibi doğrudan hex byte’lar
        Döner: gelen raw bayt dizisi
        """
        cmd = bytearray(cmd_bytes)
        print(f"Gönderilen komut: {to_hex(cmd)}")

        # Event’i sıfırla
        self._evt.clear()
        self._last = None

        # Yaz (Write Without Response)
        await self.client.write_gatt_char(WRITE_UUID, cmd, response=False)

        # Indicate’dan cevabı bekle
        try:
            await asyncio.wait_for(self._evt.wait(), timeout)
        except asyncio.TimeoutError:
            raise TimeoutError("Cihazdan yanıt gelmedi (indicate).")

        print(f"Gelen raw: {to_hex(self._last)}")
        return self._last

    @staticmethod
    def parse(raw: bytes) -> list[int]:
        """Her 2 baytı little‑endian 16‑bit tamsayıya çevir."""
        return [
            int.from_bytes(raw[i : i + 2], byteorder="little", signed=False)
            for i in range(0, len(raw), 2)
        ]

async def main():
    # 1) Tara
    print("BLE cihazları taranıyor…")
    devices = await BleakScanner.discover()
    addr = next(
        (d.address for d in devices 
         if d.name == DEVICE_NAME or d.address == DEVICE_ADDR),
        None
    )
    if not addr:
        print(f"{DEVICE_NAME} bulunamadı!")
        return

    wize = Wizepod(addr)
    try:
        # 2) Bağlan
        await wize.connect()
        print(f"Bağlandı: {addr}\n")

        # 3) Komutları doğrudan hex listesi olarak tanımla
        commands = [
            [0x50, 0x01, 0x0D, 0x0A],  # versiyon sorgu
            [0x51, 0x02, 0x10],        # çalışma süresi ayarla → 0x10
            [0x61, 0x01, 0x0D, 0x0A],  # başka bir örnek komut
        ]

        # 4) Gönder ve parse et
        for cmd_bytes in commands:
            raw = await wize.send(cmd_bytes)
            vals = Wizepod.parse(raw)
            print("Parsed 16-bit değerler:", vals, "\n")

    except Exception as e:
        print("Hata:", e)
    finally:
        await wize.disconnect()
        print("Bağlantı sonlandırıldı.")

if __name__ == "__main__":
    asyncio.run(main())
