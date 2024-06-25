import requests
import json
from openpyxl import Workbook
from bs4 import BeautifulSoup
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue

max_workers = 8
need_vehicle_types = ["truck"]
need_years = [2022]
timeout = 7

html_link = "https://www.varta-automotive.com/en-gb/battery-finder"
car_finder_link = "https://api.varta-automotive.com/api/batterySearch/en_GB"
            

headers = {
    'accept': 'application/json, text/javascript, */*; q=0.01',
    'accept-language': 'en-US,en;q=0.9',
    'origin': 'https://www.varta-automotive.com',
    'priority': 'u=1, i',
    'referer': 'https://www.varta-automotive.com/',
    'requester': 'website',
    'sec-ch-ua': '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Linux"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-site',
    'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
}

result_queue = Queue()

def fetch_json(link_json: str):
    response = requests.get(link_json, headers=headers, timeout=7)
    response.raise_for_status()
    return response.json()

def parse_battery_data(battery, vehicle_info):
    try:
        specs = battery.find("div", class_="product-specs")

        pre_shortcode = specs.find("div", text="Short Code:")
        pre_ukcode = specs.find("div", text="UK Code:")

        if pre_shortcode:
            shortcode = pre_shortcode.parent.find("div", class_="description").text.strip()
        else:
            shortcode = "None"

        if pre_ukcode:
            ukcode = pre_ukcode.parent.find("div", class_="description").text.strip()
        else:
            ukcode = "None"
    
        return {
            "productline": battery.find("div", class_="product-header").find("a").text.strip(),
            "etn": specs.find("div", text="Model:").parent.find("a").text.strip(),
            "capacity": re.sub(r'\D', '', specs.find("div", text="Capacity:").parent.find("div", class_="description").text.strip()),
            "cca": re.sub(r'\D', '', specs.find("div", text="CCA:").parent.find("div", class_="description").text.strip()),
            "width": re.sub(r'\D', '', specs.find("div", text="Width:").parent.find("div", class_="description").text.strip()),
            "length": re.sub(r'\D', '', specs.find("div", text="Length:").parent.find("div", class_="description").text.strip()),
            "height": re.sub(r'\D', '', specs.find("div", text="Height:").parent.find("div", class_="description").text.strip()),
            "shortcode": shortcode,
            "ukcode": ukcode,
            "vehicleInfo": vehicle_info
        }
    except Exception as e:
        print("\n")
        print(e)
        print("\n\n\n")
        return None

def get_batteries(link_json: str) -> None:
    try:
        json_keys = fetch_json(link_json)
        entry_list = json_keys["dataSet"]["entry"]

        if json_keys["dataSet"]["type"] == "battery":
            vehicle_info = {}
            vehicle_payload = {}

            for info in json_keys["selections"]["selection"]:
                vehicle_payload[info["key"]] = info["value"]
                if info["key"] in ["vehicleType", "year"]:
                    vehicle_info[info["key"]] = info["value"]
                elif info["key"] in ["manufacturer", "modelLine", "modelType"]:
                    vehicle_info[info["key"]] = info["name"]

            etn_payload_str = ""

            for battery in entry_list:
                etn_payload_str += f"{battery['batteryDetail']['orderInformation']['etn']}|"

            payload = {
                "type": vehicle_payload["vehicleType"],
                "year": vehicle_payload["year"],
                "make": vehicle_payload["manufacturer"],
                "model": vehicle_payload["modelLine"],
                "engine": vehicle_payload["modelType"],
                "etn": etn_payload_str
            }

            html_info = requests.get(html_link, headers=headers, params=payload, timeout=7)
            html_info.raise_for_status()

            soup = BeautifulSoup(html_info.text, "lxml")
            bat_results = soup.find_all("div", class_="single-product-result")

            print(vehicle_info)
            print(payload)

            batteries = [parse_battery_data(battery, vehicle_info) for battery in bat_results]

            print(f"new_processed_batteries {len(batteries)}")

            for battery in batteries:
                result_queue.put(battery)
         
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(get_batteries, link_json + f"/{key['key']}") for key in entry_list]
                for future in as_completed(futures):
                    future.result()  

    except Exception as e:
        print("\n")
        print(e)
        print("\n\n\n")
        return []

def get_data():
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for vech_type in need_vehicle_types:
            for year in need_years:
                json_man_link = f"{car_finder_link}/{vech_type}/{year}"
                futures.append(executor.submit(get_batteries, json_man_link))

        for future in as_completed(futures):
            future.result()  

    batteries = []
    while not result_queue.empty():
        batteries.append(result_queue.get())

    with open("data/batteries.json", "w") as file:
        file.write(json.dumps(batteries, indent=4))

def write_data():
    with open("data/batteries.json", "r") as file:
        batteries = json.load(file)

    wb = Workbook()
    ws = wb.active

    ws.append(["Год", "Производитель", "Модель", "Модификация", "Наименование", "ETN код:", "Емкость:", "Ток холодной прокрутки:", 
               "Ширина:", "Длина:", "Высота:", "Короткий код:", "UK Code:", "Mounting angle"])

    write_processed = 0

    for battery in batteries:
        if battery != None:
            ws.append([
                battery["vehicleInfo"]["year"], battery["vehicleInfo"]["manufacturer"], battery["vehicleInfo"]["modelLine"], battery["vehicleInfo"]["modelType"],
                battery["productline"], battery["etn"], 
                battery["capacity"], battery["cca"], battery["width"], battery["length"], battery["height"],
                battery["shortcode"], battery["ukcode"], 0
            ])
            write_processed += 1
            print(f"write_processed: {write_processed}")

    wb.save("data/output.xlsx")

if __name__ == "__main__":
    get_data()
    write_data()
