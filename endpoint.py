from flask import Flask, send_file, request
from flask_cors import CORS
import random
app = Flask(__name__)

CORS(app, origins=[
    "http://localhost:5173",
    "http://127.0.0.1:5173"
])

COUNTER = 10

sensor_state = [
    {
        "temps": [0.0 for _ in range(100)],
        "counter": 0
    }
    for _ in range(COUNTER)
]

ProblemsAfterTry = 3

@app.route("/data")
def data():
    global sensor_state

    sensor = request.args.get("sensor", default=0, type=int)
    
    if sensor == 2:
        if sensor_state[sensor]["counter"] >= ProblemsAfterTry:
            # Тестируем ошибку
            raise Exception("Sensor not responding after 3 attempts")
        else:
            sensor_state[sensor]["counter"] += 1
        
        


    state = sensor_state[sensor]

    current = state["temps"][-1]

    # Переключение режима
    if current >= 99:
        state["heating"] = False

    if current <= 0:
        state["heating"] = True
        state["counter"] = 0

    # Изменение скорости
    state["counter"] += 1

    delta = state["counter"] * 0.9

    # Лёгкий шум
    noise = random.uniform(-10, 10)

    if state["heating"]:
        temp = current + delta + noise
    else:
        temp = current - delta + noise

    # Ограничение диапазона
    temp = max(0, min(100, temp))

    state["temps"].pop(0)
    state["temps"].append(round(temp, 2))

    return {"data": state["temps"]}


@app.route("/count_sensors")
def counter():
    return {"count": COUNTER}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)