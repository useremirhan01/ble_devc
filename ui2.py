import sys
from qasync import QEventLoop
from qasync import asyncSlot
import asyncio
import csv
from ble_commands import *
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QComboBox, QLineEdit, QLabel, QTextEdit, QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from bleak import BleakScanner, BleakClient


# CSV Dosya Adı
CSV_FILE = "bluetooth_data.csv"

# =======================
# Bluetooth İş Parçacıkları
# MAC : 48:23:35:F4:00:0B
# =======================

class BluetoothScanner(QThread):
    """Bluetooth cihazlarını tarar ve liste döner"""
    devices_found = pyqtSignal(list)

    async def scan_devices(self):
        devices = await BleakScanner.discover()
        self.devices_found.emit([(d.name or "Bilinmeyen", d.address) for d in devices])

    def run(self):
        asyncio.run(self.scan_devices())

class BluetoothConnector(QThread):
    """Cihaza bağlanıp UUID’leri listeleyen iş parçacığı"""
    connected = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, mac_address):
        super().__init__()
        self.mac_address = mac_address

    async def connect_device(self):
        try:
            async with BleakClient(self.mac_address) as client:
                if await client.is_connected():
                    services = await client.get_services()
                    uuid_list = [char.uuid for service in services for char in service.characteristics]
                    self.connected.emit(uuid_list)
                else:
                    self.error.emit("Cihaza bağlanılamadı!")
        except Exception as e:
            self.error.emit(f"Bağlantı hatası: {e}")

    def run(self):
        asyncio.run(self.connect_device())

class BluetoothReader(QThread):
    """Seçilen UUID’den saniyelik veri çeken iş parçacığı"""
    new_data = pyqtSignal(str)

    def __init__(self, mac_address, char_uuid):
        super().__init__()
        self.mac_address = mac_address
        self.char_uuid = char_uuid
        self.running = True

    async def read_sensor_data(self):
        async with BleakClient(self.mac_address) as client:
            if await client.is_connected():
                while self.running:
                    try:
                        data = await client.read_gatt_char(self.char_uuid)
                        decoded_data = data.decode(errors="ignore")
                        self.new_data.emit(decoded_data)
                        self.save_to_csv(decoded_data)
                    except Exception as e:
                        self.new_data.emit("Hata: " + str(e))
                    await asyncio.sleep(1)

    def run(self):
        asyncio.run(self.read_sensor_data())

    def stop(self):
        self.running = False

    def save_to_csv(self, data):
        file_exists = os.path.isfile(CSV_FILE)
        with open(CSV_FILE, mode="a", newline="") as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(["Zaman", "Veri"])
            writer.writerow([asyncio.get_event_loop().time(), data])
            
class VersionReadThread(QThread):
    result = pyqtSignal(int, int)
    error  = pyqtSignal(str)

    def __init__(self, mac_address):
        super().__init__()
        self.mac = mac_address

    def run(self):
        try:
            yaz, don = asyncio.run(read_versions_data(self.mac))
            self.result.emit(yaz, don)
        except Exception as e:
            self.error.emit(str(e))


# =======================
# Bluetooth Bağlantı Paneli (SOL PANEL)
# =======================

class BluetoothApp(QWidget):
    connected_signal = pyqtSignal(str)  # MAC adresi yaymak için sinyal
    def __init__(self):
        
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Bluetooth Bağlantı Paneli")
        self.setMinimumSize(400, 350)

        layout = QVBoxLayout()

        self.label = QLabel("Bluetooth Cihazlarını Tara:")
        layout.addWidget(self.label)

        self.device_list = QComboBox()
        layout.addWidget(self.device_list)

        self.scan_button = QPushButton("Cihazları Tara")
        self.scan_button.clicked.connect(self.scan_devices)
        layout.addWidget(self.scan_button)

        self.connect_button = QPushButton("Cihaza Bağlan")
        self.connect_button.clicked.connect(self.connect_device)
        layout.addWidget(self.connect_button)

        self.uuid_label = QLabel("UUID Seç:")
        layout.addWidget(self.uuid_label)

        self.uuid_list = QComboBox()
        layout.addWidget(self.uuid_list)

        self.start_button = QPushButton("Veri Okumaya Başla")
        self.start_button.clicked.connect(self.start_reading)
        layout.addWidget(self.start_button)

        self.data_field = QLineEdit("Veri burada görünecek...")
        self.data_field.setStyleSheet("background-color: #2b2b2b; color: #e0e0e0;")
        layout.addWidget(self.data_field)

        self.setLayout(layout)

    def scan_devices(self):
        self.device_list.clear()
        self.scanner_thread = BluetoothScanner()
        self.scanner_thread.devices_found.connect(self.update_device_list)
        self.scanner_thread.start()

    def update_device_list(self, devices):
        self.device_list.clear()
        for name, mac in devices:
            self.device_list.addItem(f"{name} ({mac})", mac)

    def connect_device(self):
        index = self.device_list.currentIndex()
        if index == -1:
            QMessageBox.warning(self, "Bağlantı Hatası", "Lütfen bir cihaz seçin!")
            return
        self.selected_mac = self.device_list.itemData(index)  # Burası önemli
        self.connector_thread = BluetoothConnector(self.selected_mac)
        self.connector_thread.connected.connect(self.update_uuid_list)
        self.connector_thread.error.connect(self.show_error)
        self.connector_thread.start()

    def update_uuid_list(self, uuid_list):
        self.uuid_list.clear()
        for uuid in uuid_list:
            self.uuid_list.addItem(uuid)

        self.connected = True  # 🔥 Cihaza başarıyla bağlandık
        print("Cihaz bağlantısı başarıyla tamamlandı.")
        QMessageBox.information(self, "Bağlandı", f"{self.selected_mac} adresine başarıyla bağlandınız.")
        self.connected = True
        self.connected_signal.emit(self.selected_mac)



    def show_error(self, message):
        QMessageBox.critical(self, "Bağlantı Hatası", message)

    def start_reading(self):
        index = self.uuid_list.currentIndex()
        if index == -1:
            return
        char_uuid = self.uuid_list.currentText()
        self.reader_thread = BluetoothReader(self.selected_mac, char_uuid)
        self.reader_thread.new_data.connect(self.update_data_field)
        self.reader_thread.start()

    def update_data_field(self, data):
        self.data_field.setText(data)

# =======================
# WIZEPOD Ana Pencere
# =======================

class WIZEPODMainWindow(QMainWindow):
    def on_read_version(self):
        if not getattr(self, "connected", False):
            QMessageBox.warning(self, "Bağlantı Yok", "Lütfen önce bağlanın.")
            return

        self._ver_thread = VersionReadThread(self.selected_mac)
        self._ver_thread.result.connect(self.handle_version_result)
        self._ver_thread.error.connect(lambda msg: QMessageBox.critical(self, "Hata", msg))
        self._ver_thread.start()

    def handle_version_result(self, yaz, don):
        self.yazilim_version_field.setText(f"{yaz:#04x}")
        self.donanim_version_field.setText(f"{don:#04x}")

    
    def set_connected_device(self, mac):
        self.selected_mac = mac
        self.connected = True
        print(f"[WIZEPOD] Bağlı cihaz: {mac}")





    def __init__(self):
        super().__init__()
        self.setWindowTitle("WIZEPOD")
        self.setMinimumSize(1200, 800)

        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)

        self.left_panel = BluetoothApp()
        main_layout.addWidget(self.left_panel, 1)
        self.connected = False
        self.selected_mac = None

        self.left_panel.connected_signal.connect(self.set_connected_device)

        self.right_panel = QWidget()
        self.init_right_panel()
        main_layout.addWidget(self.right_panel, 3)

        self.setCentralWidget(main_widget)

    def init_right_panel(self):
        layout = QVBoxLayout(self.right_panel)

        # --- Version Sections ---
        version_layout = QHBoxLayout()
        yazilim_group = QGroupBox("Yazılım Versiyon")
        yazilim_layout = QHBoxLayout()
        self.yazilim_version_field = QLineEdit()
        self.yazilim_version_field.setPlaceholderText("Yazılım Versiyon")
        self.yazilim_version_field.setStyleSheet("background-color: #2b2b2b; color: #e0e0e0;")
        yr = QPushButton("OKU"); yw = QPushButton("YAZ")
        # init_right_panel() içinde Yazılım OKU buton bağlantısı
        yr.clicked.connect(
            lambda: asyncio.create_task(
                read_yazilim_version_notify(
                    self.selected_mac,
                    self.yazilim_version_field,
                    self.donanim_version_field,
                    self
                )
            )
        )



        yw.clicked.connect(self.write_yazilim_version)
        yazilim_layout.addWidget(self.yazilim_version_field)
        yazilim_layout.addWidget(yr)
        yazilim_layout.addWidget(yw)
        yazilim_group.setLayout(yazilim_layout)
        version_layout.addWidget(yazilim_group)

        donanim_group = QGroupBox("Donanım Versiyon")
        donanim_layout = QHBoxLayout()
        self.donanim_version_field = QLineEdit()
        self.donanim_version_field.setPlaceholderText("Donanım Versiyon")
        self.donanim_version_field.setStyleSheet("background-color: #2b2b2b; color: #e0e0e0;")
        dr = QPushButton("OKU"); dw = QPushButton("YAZ")
        dr.clicked.connect(self.read_donanim_version)
        dw.clicked.connect(self.write_donanim_version)
        donanim_layout.addWidget(self.donanim_version_field)
        donanim_layout.addWidget(dr)
        donanim_layout.addWidget(dw)
        donanim_group.setLayout(donanim_layout)
        version_layout.addWidget(donanim_group)

        layout.addLayout(version_layout)

        # --- AFE Ayarları ---
        afe_group = QGroupBox("AFE Ayarları")
        afe_layout = QGridLayout()
        self.afe_fields = {}
        fields = ["TIACN", "REFCN", "MODECN"]
        for i, field in enumerate(fields):
            afe_layout.addWidget(QLabel(field), i, 0)
            le = QLineEdit()
            le.setPlaceholderText(field)
            le.setStyleSheet("background-color: #2b2b2b; color: #e0e0e0;")
            afe_layout.addWidget(le, i, 1)
            self.afe_fields[field] = le
        afe_btns = QHBoxLayout()
        afe_ok = QPushButton("OKU"); afe_yr = QPushButton("YAZ")
        afe_ok.clicked.connect(self.read_afe_all)
        afe_yr.clicked.connect(self.write_afe_all)
        afe_btns.addWidget(afe_ok)
        afe_btns.addWidget(afe_yr)
        afe_layout.addLayout(afe_btns, len(fields), 0, 1, 2)
        afe_group.setLayout(afe_layout)
        layout.addWidget(afe_group)

        # --- Çalışma Süresi & Titreşim (equal width) ---
        side_layout = QHBoxLayout()

        cal_group = QGroupBox("Çalışma Süresi")
        cal_layout = QHBoxLayout()
        cal_layout.addWidget(QLabel("Çalışma Süresi"))
        self.calisma_suresi_field = QLineEdit()
        self.calisma_suresi_field.setPlaceholderText("Çalışma Süresi")
        self.calisma_suresi_field.setStyleSheet("background-color: #2b2b2b; color: #e0e0e0;")
        cal_layout.addWidget(self.calisma_suresi_field)
        cro = QPushButton("OKU"); cry = QPushButton("YAZ")
        cro.clicked.connect(self.read_calisma_suresi)
        cry.clicked.connect(self.write_calisma_suresi)
        cal_layout.addWidget(cro)
        cal_layout.addWidget(cry)
        cal_group.setLayout(cal_layout)

        vib_group = QGroupBox("Titreşim")
        vib_layout = QHBoxLayout()
        vib_layout.addWidget(QLabel("Titreşim"))
        self.titresim_status = QLabel("Kapalı")
        vib_layout.addWidget(self.titresim_status)
        on_btn = QPushButton("Aç"); off_btn = QPushButton("Kapat")
        on_btn.clicked.connect(lambda: self.titresim_status.setText("Açık"))
        off_btn.clicked.connect(lambda: self.titresim_status.setText("Kapalı"))
        vib_layout.addWidget(on_btn)
        vib_layout.addWidget(off_btn)
        vib_group.setLayout(vib_layout)

        # equal stretch
        side_layout.addWidget(cal_group, 1)
        side_layout.addWidget(vib_group, 1)
        layout.addLayout(side_layout)

        # --- Glikoz Seviyeleri ---
        groups_layout = QHBoxLayout()
        self.glucose_group = QGroupBox("Glikoz Seviyeleri")
        glucose_layout = QGridLayout()
        self.glucose_fields = {}
        glucose_levels = ["Düşük", "Normal", "Yüksek"]
        for i, lvl in enumerate(glucose_levels):
            glucose_layout.addWidget(QLabel(lvl), i, 0)
            fld = QLineEdit()
            fld.setPlaceholderText(lvl)
            fld.setStyleSheet("background-color: #2b2b2b; color: #e0e0e0;")
            glucose_layout.addWidget(fld, i, 1, 1, 3)
            self.glucose_fields[lvl] = fld
        gl_btns = QHBoxLayout()
        gl_ok = QPushButton("OKU"); gl_yr = QPushButton("YAZ")
        gl_ok.clicked.connect(self.read_glucose_levels)
        gl_yr.clicked.connect(self.write_glucose_levels)
        gl_btns.addWidget(gl_ok)
        gl_btns.addWidget(gl_yr)
        glucose_layout.addLayout(gl_btns, len(glucose_levels), 0, 1, 4)
        self.glucose_group.setLayout(glucose_layout)
        groups_layout.addWidget(self.glucose_group)

        # --- Sıcaklık Seviyeleri ---
        self.temperature_group = QGroupBox("Sıcaklık Seviyeleri")
        temp_layout = QGridLayout()
        self.temperature_fields = {}
        temp_levels = ["Düşük", "Yüksek"]
        for i, lvl in enumerate(temp_levels):
            temp_layout.addWidget(QLabel(lvl), i, 0)
            fld = QLineEdit()
            fld.setPlaceholderText(lvl)
            fld.setStyleSheet("background-color: #2b2b2b; color: #e0e0e0;")
            temp_layout.addWidget(fld, i, 1, 1, 3)
            self.temperature_fields[lvl] = fld
        temp_btns = QHBoxLayout()
        temp_ok = QPushButton("OKU"); temp_yr = QPushButton("YAZ")
        temp_ok.clicked.connect(self.read_temp_levels)
        temp_yr.clicked.connect(self.write_temp_levels)
        temp_btns.addWidget(temp_ok)
        temp_btns.addWidget(temp_yr)
        temp_layout.addLayout(temp_btns, len(temp_levels), 0, 1, 4)
        self.temperature_group.setLayout(temp_layout)
        groups_layout.addWidget(self.temperature_group)

        layout.addLayout(groups_layout)

        # --- Charts, Battery, Controls, Terminal ---
        charts_layout = QHBoxLayout()
        self.glucose_chart = QLabel("Glikoz Grafiği\n(Placeholder)")
        self.glucose_chart.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.glucose_chart.setStyleSheet(
            "background-color: #2b2b2b; color: #e0e0e0; border: 1px solid #555555;"
        )
        self.glucose_chart.setMinimumSize(200, 200)

        self.temperature_chart = QLabel("Sıcaklık Grafiği\n(Placeholder)")
        self.temperature_chart.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.temperature_chart.setStyleSheet(
            "background-color: #2b2b2b; color: #e0e0e0; border: 1px solid #555555;"
        )
        self.temperature_chart.setMinimumSize(200, 200)

        charts_layout.addWidget(self.glucose_chart)
        charts_layout.addWidget(self.temperature_chart)
        layout.addLayout(charts_layout)

        self.battery_label = QLabel("Batarya: %61")
        layout.addWidget(self.battery_label)

        buttons_layout = QHBoxLayout()
        self.continuous_read_btn = QPushButton("SÜREKLİ OKU")
        self.stop_btn = QPushButton("DUR")
        self.export_btn = QPushButton("ÇIKTI AL")
        self.sleep_mode_btn = QPushButton("UYKU MODU")
        self.sleep_mode_btn.setStyleSheet("background-color: red; color: white; font-weight: bold;")
        buttons_layout.addWidget(self.continuous_read_btn)
        buttons_layout.addWidget(self.stop_btn)
        buttons_layout.addWidget(self.export_btn)
        buttons_layout.addWidget(self.sleep_mode_btn)
        layout.addLayout(buttons_layout)

        self.terminal = QTextEdit()
        self.terminal.setPlaceholderText("Terminal (mavi=gönderilen, bordo=gelen)")
        self.terminal.setStyleSheet("background-color: #2b2b2b;")
        layout.addWidget(self.terminal)

    # --- Placeholder methods ---
    def read_yazilim_version(self):
        self.yazilim_version_field.setText("1.0.0")
    def write_yazilim_version(self):
        print("Write Yazılım:", self.yazilim_version_field.text())
    def read_donanim_version(self):
        self.donanim_version_field.setText("HW-1.0")
    def write_donanim_version(self):
        print("Write Donanım:", self.donanim_version_field.text())

    def read_afe_all(self):
        for f in self.afe_fields.values():
            f.setText("Value")
    def write_afe_all(self):
        vals = {k: v.text() for k, v in self.afe_fields.items()}
        print("Write AFE:", vals)

    def read_calisma_suresi(self):
        self.calisma_suresi_field.setText("100")
    def write_calisma_suresi(self):
        print("Write Çalışma Süresi:", self.calisma_suresi_field.text())

    def read_glucose_levels(self):
        for f in self.glucose_fields.values():
            f.setText("123")
    def write_glucose_levels(self):
        vals = {k: v.text() for k, v in self.glucose_fields.items()}
        print("Write Glikoz:", vals)

    def read_temp_levels(self):
        for f in self.temperature_fields.values():
            f.setText("37")
    def write_temp_levels(self):
        vals = {k: v.text() for k, v in self.temperature_fields.items()}
        print("Write Sıcaklık:", vals)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WIZEPODMainWindow()
    window.show()
    sys.exit(app.exec())
