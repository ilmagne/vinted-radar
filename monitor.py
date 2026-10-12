# -*- coding: utf-8 -*-
"""
Vinted Radar — monitor automatico di affari per collezionismo.
Uso:  python monitor.py            (scansione singola)
      python monitor.py --loop     (loop continuo, per server)
Env:  TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
"""
import os, sys, json, time, random, statistics, requests

VINTED_API = "https://api.vinted.eu/api/v2/catalog/items"
MIN_PRICE   = float(os.environ.get("MIN_PRICE", "10"))
MIN_DISCOUNT = float(os.environ.get("MIN_DISCOUNT", "0.40"))
LOOP_MIN   = int(os.environ.get("LOOP_MIN", "15"))
SEEN_FILE  = os.environ.get("SEEN_FILE", "seen.json")
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

# --- Modifica qui le tue ricerche: categoria -> lista di query Vinted ---
QUERIES = {
    "Carte": [
        "pokemon lotto carte", "pokemon evoluzioni paldea", "pokemon 151",
        "carte magic lotto", "yu gi oh lotto", "topps chrome", "carte sportive lotto",
    ],
    "Lego": [
        "lego star wars", "lego harry potter", "lego super mario",
        "lego minifigure lotto", "lego usato",
    ],
    "Action figure": [
        "action figure marvel", "funko pop lotto", "star wars black series",
        "action figure dragon ball", "gi joe figure",
    ],
    "Capi di marca": [
        "barbour", "stone island", "cp company", "ralph lauren", "carhartt wip",
    ],
}

def load_seen():
    try:
        return set(json.load(open(SEEN_FILE)))
    except Exception:
        return set()

def save_seen(seen):
    json.dump(sorted(seen)[-5000:], open(SEEN_FILE, "w"))

def vinted_search(q, per_page=48):
    r = requests.get(VINTED_API, params={
        "search_text": q, "price_from": MIN_PRICE,
        "order": "newest_first", "per_page": per_page, "page": 1,
    }, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json().get("items", [])

def reference_median(item_id, title):
    """Prezzo mediano dei pari: stessa ricerca, escluso l'annuncio stesso."""
    try:
        peers = vinted_search(title, per_page=96)
        prices = [float(p["price"]) for p in peers
                  if str(p["id"]) != str(item_id) and p.get("price")]
        if len(prices) < 5:
            return None
        return statistics.median(prices)
    except Exception:
        return None

def send_telegram(text, photo_url=None):
    token, chat = os.environ["TELEGRAM_TOKEN"], os.environ["TELEGRAM_CHAT_ID"]
    if photo_url:
        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        payload = {"chat_id": chat, "caption": text, "parse_mode": "HTML", "photo": photo_url}
    else:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": False}
    requests.post(url, data=payload, timeout=15)

def scan():
    seen = load_seen()
    fresh = set()
    for cat, queries in QUERIES.items():
        for q in queries:
            try:
                items = vinted_search(q, per_page=20)
            except Exception as e:
                print(f"[{cat}] '{q}' errore: {e}")
                time.sleep(random.uniform(4, 8)); continue
            for it in items:
                fresh.add(str(it["id"]))
                if str(it["id"]) in seen:
                    continue
                price = float(it.get("price", 0) or 0)
                if price < MIN_PRICE:
                    continue
                med = reference_median(it["id"], it.get("title", q))
                if not med or med <= 0:
                    continue
                disc = 1 - price / med
                if disc >= MIN_DISCOUNT:
                    photo = (it.get("photo") or {}).get("full_size_url", "")
                    msg = (f"🎯 <b>AFFARE {cat}</b>  −{disc*100:.0f}%\n"
                           f"{it.get('title','')}\n"
                           f"Prezzo: <b>{price:.0f} €</b> · medio pari: {med:.0f} €\n"
                           f"{it.get('url','')}")
                    try:
                        send_telegram(msg, photo or None)
                        print(f"[ALERT] {cat} {price:.0f}€ vs {med:.0f}€ - {it.get('title','')[:50]}")
                    except Exception as e:
                        print("Telegram errore:", e)
                time.sleep(random.uniform(2, 4))  # gentilezza verso l'API
            time.sleep(random.uniform(4, 8))
    save_seen(seen | fresh)
    print(f"Scan completato. Visti: {len(seen | fresh)}")

if __name__ == "__main__":
    if "--loop" in sys.argv:
        while True:
            try: scan()
            except Exception as e: print("Errore loop:", e)
            print(f"Attendo {LOOP_MIN} min..."); time.sleep(LOOP_MIN * 60)
    else:
        scan()
