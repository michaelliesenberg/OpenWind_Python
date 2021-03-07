import socket
import time
import asyncio
import re
from bleak import BleakClient
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

UDP_IP = "127.0.0.1"
UDP_PORT = 2000
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
NMEA0183_Sentences = ""
fw_number = None

def socket(msg):
    try:
        sock.sendto(bytes(msg, "utf-8"), (UDP_IP, UDP_PORT))

    except (socket.timeout, ConnectionRefusedError):
        sock.close()


OPENWIND_WIND_CHARACTERISTIC_UUID = '0000cc91-0000-1000-8000-00805f9b34fb'
OPENWIND_MOV_ENABLE_CHARACTERISTIC_UUID = '0000aa82-0000-1000-8000-00805f9b34fb'
OPENWIND_FW_CHARACTERISTIC_UUID = '00002a26-0000-1000-8000-00805f9b34fb'
OPENWIND_SN_CHARACTERISTIC_UUID = '00002a25-0000-1000-8000-00805f9b34fb'

deviceFound = False
deviceAddress = None
deviceConnected = False

def checksum( msg ):

    # Find the start of the NMEA sentence
    startchars = "!$"
    for c in startchars:
        i = msg.find(c)
        if i >= 0: break
    else:
        return (False, None, None)

    # Calculate the checksum on the message
    sum1 = 0
    for c in msg[i+1:]:
        if c == '*':
            break
        sum1 = sum1 ^ ord(c)

    sum1 = sum1 & 0xFF

    return '{:x}'.format(int(sum1))

def WIND_DATA_CALLBACK(sender, data):

    global fw_number

    AWA = float((data[2] << 8) | data[1]) * 0.1  # °
    AWS = float((data[4] << 8) | data[3]) * 0.01  # kts

    print("AWA: " + "{:3.1f}".format(AWA) + " AWS: " + "{:3.1f}".format(AWS))

    NMEA0183_WIND_Sentece = "$WIMWV," + "{:3.1f}".format(AWA) + ",R," + "{:3.1f}".format(AWS) + ",N,A*"
    cs = checksum(NMEA0183_WIND_Sentece)
    NMEA0183_WIND_Sentece = NMEA0183_WIND_Sentece + str(cs) + "\n"
    print(NMEA0183_WIND_Sentece)
    socket(NMEA0183_WIND_Sentece)

    #Only if Firmware Version is same or above 1.25
    if float(fw_number) >= 1.25:
        YAW = float((data[6] << 8) | data[5]) * 1/16 -90 #°
        PITCH = float((data[8] << 8) | data[7]) * 1 / 16  * -1 # °
        ROLL = float((data[10] << 8) | data[9]) * 1 / 16  * -1# °
        CALIBRATION = data[11] # %

        if YAW < 0:
            YAW = 360 + YAW

        if PITCH < 0:
            PITCH = PITCH * -1

        if PITCH >= 180:
            PITCH = 360 - PITCH


        print("YAW: " + "{:3.1f}".format(YAW) + " PITCH: " + "{:3.1f}".format(PITCH) + " ROLL: " + "{:3.1f}".format(ROLL) + " CALIBRATION: " + str(CALIBRATION))

def simple_callback(device: BLEDevice, advertisement_data: AdvertisementData):
    global deviceFound
    global deviceAddress
    print(device.address, "RSSI:", device.rssi, advertisement_data)

    if device.name == "OpenWind":
        print("Found OpenWind")
        deviceFound=True
        deviceAddress = device.address

def OW_DISCONNECT_CALLBACK(client):
    global deviceConnected
    deviceConnected=False
    print("OpenWind with address {} got disconnected!".format(client.address))


async def run():
    global deviceFound
    global deviceAddress
    global deviceConnected
    global fw_number

    scanner = BleakScanner()
    scanner.register_detection_callback(simple_callback)

    while True:
        await scanner.start()
        await asyncio.sleep(5.0)
        await scanner.stop()
        if deviceFound:
            deviceFound = False
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

        client.set_disconnected_callback(OW_DISCONNECT_CALLBACK)

        write_value = bytearray([0x2C])
        await client.write_gatt_char(OPENWIND_MOV_ENABLE_CHARACTERISTIC_UUID, write_value)
        await asyncio.sleep(1.0)
        await client.start_notify(OPENWIND_WIND_CHARACTERISTIC_UUID, WIND_DATA_CALLBACK)

        while await client.is_connected():
            await asyncio.sleep(5.0)





if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())

    while True:
        print("waiting...")
        time.sleep(5)

        if not deviceConnected:
            loop.run_until_complete(run())

