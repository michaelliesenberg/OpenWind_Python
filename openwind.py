import socket
import time
import asyncio
import re
import numpy as np
from bleak import BleakClient
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

UDP_IP = "127.0.0.1"
UDP_PORT = 2000
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)



NMEA0183_Sentences = ""
fw_number = None

AWA = 0
AWS = 0
YAW = 0
PITCH = 0
ROLL = 0
CALIBRATE_STATUS = 0
HDM_SIGNALK = 0



def send_udp(msg):
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

def int16_from_bytes(high_byte, low_byte):
    value = (high_byte << 8) | low_byte
    if value >= 0x8000:  # if sign bit set
        value -= 0x10000
    return value

def WIND_DATA_CALLBACK(sender, data):

    global fw_number
    global AWA
    global AWS
    global YAW
    global PITCH
    global ROLL
    global CALIBRATE_STATUS

    AWA = float((data[2] << 8) | data[1]) * 0.1  # °
    AWS = float((data[4] << 8) | data[3]) * 0.01  # kts

    print("AWA: " + "{:3.1f}".format(AWA) + " AWS: " + "{:3.1f}".format(AWS))

    NMEA0183_WIND_Sentece = "$WIMWV," + "{:3.1f}".format(AWA) + ",R," + "{:3.1f}".format(AWS) + ",N,A*"
    cs = str(checksum(NMEA0183_WIND_Sentece))
    NMEA0183_WIND_Sentece = NMEA0183_WIND_Sentece + cs.rjust(2, '0') + "\n"
    print(NMEA0183_WIND_Sentece)
    send_udp(NMEA0183_WIND_Sentece)

    #Only if Firmware Version is same or above 1.25
    if float(fw_number) >= 1.25:
        YAW = ((data[6] << 8) | data[5]) * 1 / 16 - 90

        ROLL = int16_from_bytes(data[8], data[7]) * 1 / 16 * -1
        PITCH = int16_from_bytes(data[10], data[9]) * 1 / 16
        CALIBRATE_STATUS = data[11]

        if YAW < 0:
            YAW = 360 + YAW

        if ROLL >= 180:
            ROLL = ROLL - 360
        print("YAW: " + "{:3.1f}".format(YAW) + " PITCH: " + "{:3.1f}".format(PITCH) + " ROLL: " + "{:3.1f}".format(ROLL) + " CALIBRATION: " + str(CALIBRATE_STATUS))

        NMEA0183_HEADING_Sentece = "$WIHDM," + "{:3.1f}".format(YAW) + ",M*"
        cs = str(checksum(NMEA0183_HEADING_Sentece))
        NMEA0183_HEADING_Sentece = NMEA0183_HEADING_Sentece + cs.rjust(2, '0') + "\n"
        print(NMEA0183_HEADING_Sentece)
        send_udp(NMEA0183_HEADING_Sentece)



def ManufacturerData(data):
    print

def simple_callback(device: BLEDevice, advertisement_data: AdvertisementData):
    global deviceFound, deviceAddress

    rssi = advertisement_data.rssi
    print(device.address, "RSSI:", rssi)

    if device.name == "OpenWind":
        print("Found OpenWind")
        deviceFound = True
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

    # Register callback using modern Bleak API
    scanner = BleakScanner(detection_callback=simple_callback)

    while True:
        await scanner.start()
        await asyncio.sleep(5.0)
        await scanner.stop()
        if deviceFound:
            deviceFound = False
            break
    client = BleakClient(deviceAddress, disconnected_callback=OW_DISCONNECT_CALLBACK)

    async with client:

        deviceConnected = True
        print("Services:")
        for service in (client.services or []):
            print(service)

        fw_number = await client.read_gatt_char(OPENWIND_FW_CHARACTERISTIC_UUID)
        print("Firmware Version: {0}".format("".join(map(chr, fw_number))))

        sn_number = await client.read_gatt_char(OPENWIND_SN_CHARACTERISTIC_UUID)

        if float(fw_number) >= 1.27:
            print("Model Number (hex): {0}".format(sn_number.hex()))
        else:
            print("Model Number: {0}".format("".join(map(chr, sn_number))))


        write_value = bytearray([0x2C])
        await client.write_gatt_char(OPENWIND_MOV_ENABLE_CHARACTERISTIC_UUID, write_value)
        await asyncio.sleep(1.0)
        await client.start_notify(OPENWIND_WIND_CHARACTERISTIC_UUID, WIND_DATA_CALLBACK)

        while client.is_connected:
            await asyncio.sleep(1.0)


def main():
    while True:
        try:
            asyncio.run(run())

            # Reconnect loop
            while True:
                print("waiting...")
                time.sleep(5)
                if not deviceConnected:  # <- no parentheses
                    asyncio.run(run())

        except KeyboardInterrupt:
            print("\nStopping...")
            break

        except Exception as e:
            print("Something went wrong, retrying...", e)
            time.sleep(1)

if __name__ == "__main__":
    main()