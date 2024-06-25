import requests
import json
import time
from openpyxl import Workbook
from bs4 import BeautifulSoup
import re

need_vehicle_types = ["pc"]
need_years = [2024]
timeout = 7

car_finder_link = "https://api.varta-automotive.com/api/batterySearch/en_GB"
html_link = "https://www.varta-automotive.com/en-gb/battery-finder"


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

get_processed = 0

def get_batteries(link_json: str, save_to_json = False) -> list:
    global get_processed

    try:
        response = requests.get(link_json, headers=headers, timeout=timeout)
        response.raise_for_status()
        json_keys = response.json()

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

            html_info = requests.get(html_link, headers=headers, params=payload, timeout=timeout)
            html_info.raise_for_status()

            # with open("data/test.html", "w") as file:
            #     file.write(html_info.text)
            soup = BeautifulSoup(html_info.text, "lxml")
            bat_results = soup.find_all("div", class_="single-product-result")

            batteries = []

            print(vehicle_info)
            print(payload)

            for battery in bat_results:
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

                    bat_dict = {
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
                    batteries.append(bat_dict)
                except Exception as e:
                    print("\n")
                    print(e)
                    print("\n\n\n")
            
            get_processed += len(batteries)
            print(f"get_processed: {get_processed}")
            return batteries
        else:
            batteries = []
            for key in entry_list:
                search_key = key["key"]

                next_json_link = link_json + f"/{search_key}"
                #time.sleep(0.1)
            
                batteries += get_batteries(next_json_link)

                if save_to_json == True:
                    with open("data/batteries.json", "w") as file:
                        file.write(json.dumps(batteries, indent=4))

            return batteries
    except Exception as e:
        print("\n")
        print(e)
        print("\n\n\n")
        return []
        
        
def get_data():
    batteries = []

    for vech_type in need_vehicle_types:
        for year in need_years:
            json_man_link = f"{car_finder_link}/{vech_type}/{year}"
            
            batteries += get_batteries(json_man_link, True)
    
    #print(row_batteries)
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
        ws.append([
            battery["vehicleInfo"]["year"], battery["vehicleInfo"]["manufacturer"], battery["vehicleInfo"]["modelLine"], battery["vehicleInfo"]["modelType"],
            battery["productline"], battery["etn"], 
            battery["capacity"], battery["cca"], battery["width"], battery["length"], battery["height"],
            battery["shortcode"], battery["ukcode"], 0
        ])
        write_processed += 1
        print(f"write_processed: {write_processed}")

    wb.save("data/output.xlsx")




# def get_data():
#     base_link = "https://api.varta-automotive.com/api/batterySearch/en_GB"
#     vehicle_types = ["pc"]

#     for type in vehicle_types:
#         for year in range(2022, 2024):
#             json_man_link = f"{base_link}/{type}/{year}"
#             json_manufactures = requests.get(json_man_link)

#             for manufacturer in json_manufactures["dataSet"]["entry"]:
#                 man_key = manufacturer["key"]

#                 json_modellines_link = json_man_link + f"/{man_key}"
#                 json_modellines = requests.get(json_modellines_link)

#                 for modelline in json_modellines["dataSet"]["entry"]:
#                     ml_key = modelline["key"]

#                     json_modeltypes_link = json_modellines_link + f"/{ml_key}"
#                     json_modeltypes = requests.get(json_modeltypes_link)

#                     for modeltype in json_modeltypes["dataSet"]["entry"]:
#                         mt_key = modeltype["key"]

#                         json_batteries_link = json_modeltypes_link + f"/{mt_key}"
#                         json_batteries = requests.get(json_batteries_link)




if __name__ == "__main__":
    get_data()
    write_data()


