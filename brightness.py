import uasyncio as asyncio
from cosmic import CosmicUnicorn

TRANSITION = 1.0 / 72.0

cu = CosmicUnicorn()


def map_range(x):
    min_input = 10
    max_input = 130
    min_output = 0.1
    max_output = 1

    return (x - min_input) * (max_output - min_output) / (max_input - min_input) + min_output


def calculate_brightness(prev_brightness_val):
    current_lsv = cu.light()
    current_brightness_val = map_range(current_lsv)

    brightness_diff = current_brightness_val - prev_brightness_val
    brightness_val = prev_brightness_val + (brightness_diff * TRANSITION)
    if brightness_val > 1:
        brightness_val = 1
    elif brightness_val < 0.1:
        brightness_val = 0.1

    return brightness_val

async def brightness_task(device):
    brightness_val = 0.1
    while True:
        brightness_val = calculate_brightness(brightness_val)
        device.set_brightness(brightness_val)
        await asyncio.sleep(0.1)
