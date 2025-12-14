import requests
import time
import re
import hashlib
from bs4 import BeautifulSoup
from config import HEADERS, BASE_URL


def extract_data(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = []

    for tr in soup.find_all("tr"):
        if not tr.get("id", "").startswith("tr_"):
            continue
        try:
            tds = tr.find_all("td")
            if len(tds) >= 8:
                model = tds[3].get_text(strip=True)
                year = tds[4].get_text(strip=True)
                engine_text = tds[5].get_text(strip=True)
                mileage_text = re.sub(r'\D', '', tds[6].get_text(strip=True))
                price = re.sub(r'\D', '', tds[7].get_text(strip=True))
                link = BASE_URL + tr.find("a", href=True).get("href")

                rows.append([model, year, engine_text, mileage_text, price, link])
        except (IndexError, AttributeError):
            continue

    return rows


def parse_all_pages(brand, max_pages=100):
    seen_hashes = set()
    all_ads = []
    page = 1

    while page <= max_pages:
        url = f"{BASE_URL}/lv/transport/cars/{brand}/page{page}.html"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
        except requests.RequestException:
            break

        html = resp.text
        hash_value = hashlib.md5(html.encode("utf-8")).hexdigest()

        if hash_value in seen_hashes:
            break

        seen_hashes.add(hash_value)

        ads = extract_data(html)
        if not ads:
            break

        all_ads.extend(ads)
        page += 1
        time.sleep(0.1)

    return all_ads


def filter_ads(ads, filters):
    result = []

    for ad in ads:
        model, year, engine_text, mileage_text, price, link = ad

        # model
        if filters.get("model"):
            model_filter = filters["model"].lower()
            if filters["brand"] == "bmw" and model_filter.isdigit() and len(model_filter) == 1:
                if not model or not model[0].isdigit() or model[0] != model_filter:
                    continue
            else:
                if model_filter not in model.lower():
                    continue

        # year
        try:
            year_val = int(year)
        except:
            year_val = 0

        if filters["min_year"] and year_val < filters["min_year"]:
            continue
        if filters["max_year"] and year_val > filters["max_year"]:
            continue

        # engine
        try:
            engine_size = float(re.sub(r'[^0-9.,]', '', engine_text).replace(',', '.'))
        except:
            engine_size = 0.0

        if filters["min_engine"] and engine_size < filters["min_engine"]:
            continue
        if filters["max_engine"] and engine_size > filters["max_engine"]:
            continue

        # mileage
        try:
            mileage = int(mileage_text)
        except:
            mileage = 0

        if filters["max_mileage"] and mileage > filters["max_mileage"]:
            continue

        # price
        try:
            price_val = int(price)
        except:
            price_val = 0

        if filters["min_price"] and price_val < filters["min_price"]:
            continue
        if filters["max_price"] and price_val > filters["max_price"]:
            continue

        result.append(ad)

    return result
