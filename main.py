import time
import uasyncio as asyncio
import urequests as requests
from cosmic import CosmicUnicorn
from picographics import PicoGraphics, DISPLAY_COSMIC_UNICORN as DISPLAY

from networking import networking_task
from brightness import brightness_task

from secrets import REQEST_URLS

STATE_PRE_SCROLL = 0
STATE_SCROLLING = 1
STATE_POST_SCROLL = 2

state = STATE_PRE_SCROLL
data = []

async def requests_task():
    global data

    while True:
        # Don't perform blocking request while scrolling
        if state != STATE_PRE_SCROLL:
            await asyncio.sleep(0.1)
            continue

        new_data = []

        # Perform requests
        for url in REQEST_URLS:

            try:
                r = requests.get(url)
                response = r.json()
                r.close()

                now_tuple = [int(element) for element in time.gmtime(response["realtimeDataUpdatedAt"])[3:5]]

                for d in response["departures"]:
                    name = d["direction"]
                    name = name.replace("(Berlin)", "")
                    name = name.replace("S+U ", "").replace("S ", "").replace("U ", "")
                    name = name.replace(", Bahnhof", "").replace("Bhf", "")
                    name = name.replace("ä", "a").replace("ö", "o").replace("ü", "u")

                    line = d["line"]["name"]
                    
                    when = d["when"]
                    if when == None and "prognosedWhen" in d:
                        when = d["prognosedWhen"]
                    if when == None and "plannedWhen" in d:
                        when = d["plannedWhen"]

                    when_tuple = [int(element) for element in when.split("T")[1].split("+")[0][:-3].split(":")[:2]]
                    offset = int(when.split("T")[1].split("+")[1][:2])
                    when = str((when_tuple[0] - ((now_tuple[0] + offset) % 24)) * 60 + (when_tuple[1] - now_tuple[1]))
                
                    color = d["line"]["color"]["bg"].replace("#", "")

                    print(d["line"]["name"], d["line"]["color"]["bg"], d["direction"], d["when"])
                    new_data.append({"color": tuple(int(color[i:i+2], 16) for i in (0, 2, 4)), "line": line, "destination": name, "departing": when})
            
            except Exception as e:
                print(e)

        data = new_data
        await asyncio.sleep(60)

async def display_task(device):
    global state
    
    HOLD_TIME = 0.5
    STEP_TIME = 0.05

    shift = 0

    graphics = PicoGraphics(DISPLAY)
    width = CosmicUnicorn.WIDTH
    height = CosmicUnicorn.HEIGHT

    graphics.set_font("bitmap8")
    last_time = time.ticks_ms()

    while True:
        # Find most wide destination in data
        msg_width = 0
        for d in data:
            msg_width = max(msg_width, graphics.measure_text(d["destination"], 1) + graphics.measure_text(d["departing"], 1))
        # Find most wide line in data
        line_width = 0
        for d in data:
            line_width = max(line_width, graphics.measure_text(d["line"], 1))
        msg_width = msg_width + line_width
        time_ms = time.ticks_ms()

        if state == STATE_PRE_SCROLL and time_ms - last_time > HOLD_TIME * 3 * 1000:
            if msg_width >= width:
                state = STATE_SCROLLING
            last_time = time_ms

        if state == STATE_SCROLLING and time_ms - last_time > STEP_TIME * 1000:
            shift += 1
            if shift >= msg_width - width - 1:
                state = STATE_POST_SCROLL
            last_time = time_ms

        if state == STATE_POST_SCROLL and time_ms - last_time > HOLD_TIME * 1000:
            state = STATE_PRE_SCROLL
            shift = 0
            last_time = time_ms

        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()

        # iterate data 
        for i, d in enumerate(data):

            graphics.set_pen(graphics.create_pen(d["color"][0], d["color"][1], d["color"][2]))
            graphics.text(d["line"], 0 - shift, 8*i, -1, 1)
            graphics.set_pen(graphics.create_pen(100, 100, 100))
            graphics.text(d["destination"], 0 - shift + line_width, 8*i, -1, 1)

            time_width = graphics.measure_text(d["departing"], 1)
            graphics.set_pen(graphics.create_pen(0, 0, 0))
            graphics.rectangle(width - time_width, 8*i, time_width, 8*i+8)
            graphics.set_pen(graphics.create_pen(200, 200, 200))
            graphics.text(d["departing"], width - time_width + 1, 8*i, -1, 1)

        # update the display
        device.update(graphics)

        await asyncio.sleep(0.1)

async def main():
    cu = CosmicUnicorn()
    # Create and start both tasks
    await asyncio.gather(
        networking_task(),
        brightness_task(cu),
        display_task(cu),
        requests_task(),
    )

# Run the main event loop
loop = asyncio.get_event_loop()
loop.create_task(main())
loop.run_forever()