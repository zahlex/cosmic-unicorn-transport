import time
import ntptime
import uasyncio as asyncio
import urequests as requests
from cosmic import CosmicUnicorn
from picographics import PicoGraphics, DISPLAY_COSMIC_UNICORN as DISPLAY
from breakout_bme68x import BreakoutBME68X
from pimoroni_i2c import PimoroniI2C
from pimoroni import BREAKOUT_GARDEN_I2C_PINS

from networking import networking_task
from brightness import brightness_task

from secrets import REQEST_URLS

STATE_PRE_SCROLL = 0
STATE_SCROLLING = 1
STATE_POST_SCROLL = 2

state = STATE_PRE_SCROLL
data = []

def local_time():
    # get current time in seconds since epoch
    time_seconds = time.mktime(time.gmtime()) + 3600
    # Set timezone offset to Berlin respecting daylight saving time after last sunday in march at 1:00 UTC until last sunday in october at 1:00 UTC
    year, month, day, hour, minute, second, weekday, yearday = time.gmtime()
    # check if we are past last sunday of march 1:00 UTC and before last sunday of october 1:00 UTC
    if (month > 3 or (month == 3 and day > 31 - (weekday + 1) % 7 and hour >= 1)) and (month < 10 or (month == 10 and day < 31 - (weekday + 1) % 7 and hour < 1)):
        time_seconds += 3600
    # get time_seconds as tuple
    return time.gmtime(time_seconds)

async def requests_task():
    global data

    while True:
        # Don't perform blocking request while scrolling
        if state != STATE_PRE_SCROLL:
            await asyncio.sleep(0.1)
            continue

        try:
            ntptime.settime()
        except Exception as e:
            print(e)

        new_data = []

        # Perform requests
        for url in REQEST_URLS:

            try:
                r = requests.get(url)
                response = r.json()
                r.close()

                now_tuple = [int(element) for element in time.gmtime()[3:5]]

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

    i2c = PimoroniI2C(**BREAKOUT_GARDEN_I2C_PINS)
    bme = BreakoutBME68X(i2c)

    shift = 0
    page = 4
    temperature = 0
    pressure = 0
    humidity = 0
    gas_resistance = 0

    graphics = PicoGraphics(DISPLAY)
    width = CosmicUnicorn.WIDTH
    height = CosmicUnicorn.HEIGHT

    graphics.set_font("bitmap8")
    last_time = time.ticks_ms()
    last_time_page = time.ticks_ms()

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
            temperature, pressure, humidity, gas_resistance, status, gas_index, meas_index = bme.read()
            if msg_width >= width:
                state = STATE_SCROLLING
            last_time = time_ms
            continue

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

        # draw footer
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.rectangle(0, height - 8, width, height)
        graphics.set_pen(graphics.create_pen(200, 200, 200))
        if page == 0:
            graphics.text("{:.1f}".format(temperature), 0, height - 7, -1, 1)
            graphics.text("°C", 24, height - 7, -1, 1)
        elif page == 1:
            graphics.text("{:.0f}".format(pressure / 100), 0, height - 7, -1, 1)
            graphics.text("h", 21, height - 7, -1, 1)
            graphics.text("P", 25, height - 7, -1, 1)
            graphics.text("a", 28, height - 7, -1, 1)
        elif page == 2:
            graphics.text("{:.1f}".format(humidity), 0, height - 7, -1, 1)
            graphics.text("°", 25, height - 7, -1, 1)
            graphics.line(24, height, 32, height - 8)
            graphics.text("°", 29, height - 3, -1, 1)
        elif page == 3:
            graphics.text("{:.0f}".format(gas_resistance / 100), 0, height - 7, -1, 1)
            graphics.text("k", 23, height - 7, -1, 1)
            graphics.line(27, height - 1, 29, height - 1)
            graphics.line(28, height - 1, 28, height - 2)
            graphics.line(27, height - 2, 27, height - 6)
            graphics.line(30, height - 1, 32, height - 1)
            graphics.line(30, height - 1, 30, height - 2)
            graphics.line(31, height - 2, 31, height - 6)
            graphics.line(28, height - 7, 31, height - 7)
        elif page == 4 or page == 5:
            # display time in center of footer
            time_tuple = [int(element) for element in local_time()[3:5]]
            time_str = "{:02d}:{:02d}".format(time_tuple[0], time_tuple[1])
            time_width = graphics.measure_text(time_str, 1)
            graphics.text(time_str, ((width - time_width) // 2) + 1, height - 7, -1, 1)

        # iterate page after HOLD_TIME
        if time_ms - last_time_page > HOLD_TIME * 6 * 1000:
            page = (page + 1) % 6
            last_time_page = time_ms

        # update the display
        device.update(graphics)

        await asyncio.sleep(0.1)

async def main():
    try:
        cu = CosmicUnicorn()
        # Create and start both tasks
        await asyncio.gather(
            networking_task(),
            brightness_task(cu),
            display_task(cu),
            requests_task(),
        )

    except Exception as e:
        print(e)

    # run main again if something goes wrong
    finally:
        main()

# Run the main event loop
loop = asyncio.get_event_loop()
loop.create_task(main())
loop.run_forever()
