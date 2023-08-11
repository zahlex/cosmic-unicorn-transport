import uasyncio as asyncio
import network
import time

from secrets import NETWORK_CREDENTIALS

network_iterator = 0
wlan = network.WLAN(network.STA_IF)

def connect_to_network():
    global network_iterator

    print('[WLAN] trying to connect to network', list(NETWORK_CREDENTIALS)[network_iterator], '...')

    wlan.active(True)
    wlan.config(pm=0xa11140)  # Disable power-save mode
    wlan.connect(list(NETWORK_CREDENTIALS)[network_iterator], list(NETWORK_CREDENTIALS.values())[network_iterator])

    max_wait = 10
    while max_wait > 0:
        if wlan.status() < 0 or wlan.status() >= 3:
            break
        max_wait -= 1
        print('[WLAN] waiting for connection...')
        time.sleep(1)

    if wlan.status() != 3:
        network_iterator = (network_iterator + 1) % len(NETWORK_CREDENTIALS)
        raise RuntimeError('network connection could not be established')

    network_iterator = 0
    print('[WLAN] connected:', wlan.ifconfig())

async def networking_task():
    while True:
        if wlan.status() != 3:
            connect_to_network()
        await asyncio.sleep(1)