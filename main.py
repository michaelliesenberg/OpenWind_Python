import socket
import time
import asyncio
from bleak import BleakClient
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

UDP_IP = "127.0.0.1"
UDP_PORT = 2000
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
NMEA0183_Sentences = ""

def socket():
    while True:
        time.sleep(1)

        try:
            sock.sendto(bytes(NMEA0183_Sentences, "utf-8"), (UDP_IP, UDP_PORT))

        except (socket.timeout, ConnectionRefusedError):
            sock.close()


OPENWIND_WIND_CHARACTERISTIC_UUID = '0000cc91-0000-1000-8000-00805f9b34fb'
OPENWIND_MOV_ENABLE_CHARACTERISTIC_UUID = '0000aa82-0000-1000-8000-00805f9b34fb'
OPENWIND_FW_CHARACTERISTIC_UUID = '00002a26-0000-1000-8000-00805f9b34fb'
OPENWIND_SN_CHARACTERISTIC_UUID = '00002a25-0000-1000-8000-00805f9b34fb'

deviceFound = False
deviceAddress = None
deviceConnected = False

def simple_callback(device: BLEDevice, advertisement_data: AdvertisementData):
    global deviceFound
    global deviceAddress
    print(device.address, "RSSI:", device.rssi, advertisement_data)

    if device.name == "OpenWind":
        print("Found OpenWind")
        deviceFound=True
        deviceAddress = device.address

def WIND_DATA_CALLBACK(sender, data):
    print("{0}: {1}".format(sender, data))
    AWA = float((data[2] << 8) | data[1]) * 0.1  # °
    AWS = float((data[4] << 8) | data[3]) * 0.01  # kts
    YAW = float((data[6] << 8) | data[5]) * 1/16 -90 #°
    PITCH = float((data[8] << 8) | data[7]) * 1 / 16  * -1 # °
    ROLL = float((data[10] << 8) | data[9]) * 1 / 16  * -1# °
    CALIBRATION = data[11] # %

    if YAW < 0:
        YAW = 360 + YAW

    if PITCH < 0:
        PITCH = PITCH * -1

    if PITCH  >= 180:
        PITCH = 360 - PITCH

    print("AWA: " + str(AWA) + " AWS: " + str(AWS))
    print("YAW: " + str(YAW) + " PITCH: " + str(PITCH) + " ROLL: " + str(ROLL) + " CALIBRATION: " + str(CALIBRATION))

def OW_DISCONNECT_CALLBACK(client):
    global deviceConnected
    deviceConnected=False
    print("OpenWind with address {} got disconnected!".format(client.address))


async def run():
    global deviceFound
    global deviceAddress
    global deviceConnected

    scanner = BleakScanner()
    scanner.register_detection_callback(simple_callback)

    while True:
        await scanner.start()
        await asyncio.sleep(5.0)
        await scanner.stop()
        if deviceFound:
            deviceFound=False
            break

    async with BleakClient(deviceAddress) as client:

        deviceConnected = True
        svcs = await client.get_services()
        print("Services:")
        for service in svcs:
            print(service)
        fw_number = await client.read_gatt_char(OPENWIND_FW_CHARACTERISTIC_UUID)
        print("Model Number: {0}".format("".join(map(chr, fw_number))))

        sn_number = await client.read_gatt_char(OPENWIND_SN_CHARACTERISTIC_UUID)
        print("Model Number: {0}".format("".join(map(chr, sn_number))))
        print("Model Number: {0}".format(sn_number.hex()))

        await client.start_notify(OPENWIND_WIND_CHARACTERISTIC_UUID, WIND_DATA_CALLBACK)
        await asyncio.sleep(5.0)
        write_value = bytearray([0x2C])
        await client.write_gatt_char(OPENWIND_MOV_ENABLE_CHARACTERISTIC_UUID, write_value)
        await asyncio.sleep(5.0)

        client.set_disconnected_callback(OW_DISCONNECT_CALLBACK)



if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())

    while True:
        print("waiting...")
        time.sleep(5)

        if not deviceConnected:
            loop.run_until_complete(run())
