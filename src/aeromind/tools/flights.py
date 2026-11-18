from __future__ import annotations

from typing import Any


AIRPORT_CODES = (
    "LHR", "DXB", "CAI", "DOH", "IST", "CDG", "AMM",
    "KWI", "JED", "MED", "BEY", "TUN", "JFK", "SIN", "BKK",
)

# Searchable airports include the Saudi departure hubs as well as the 15
# advertised destinations.  Keeping AIRPORT_CODES stable preserves the public
# destination catalogue while allowing a user to search in either direction.
SEARCH_AIRPORT_CODES = tuple(dict.fromkeys(("RUH", "DMM", *AIRPORT_CODES)))

DESTINATION_NAMES = {
    "london": "LHR", "lhr": "LHR", "lon": "LHR", "لندن": "LHR",
    "dubai": "DXB", "dxb": "DXB", "دبي": "DXB",
    "cairo": "CAI", "cai": "CAI", "القاهرة": "CAI",
    "doha": "DOH", "doh": "DOH", "الدوحة": "DOH",
    "istanbul": "IST", "ist": "IST", "إسطنبول": "IST", "اسطنبول": "IST",
    "paris": "CDG", "cdg": "CDG", "باريس": "CDG",
    "amman": "AMM", "amm": "AMM", "عمان": "AMM",
    "kuwait": "KWI", "kwi": "KWI", "الكويت": "KWI",
    "jeddah": "JED", "jed": "JED", "جدة": "JED",
    "medina": "MED", "med": "MED", "المدينة": "MED",
    "beirut": "BEY", "bey": "BEY", "بيروت": "BEY",
    "tunis": "TUN", "tun": "TUN", "تونس": "TUN",
    "new york": "JFK", "jfk": "JFK", "nyc": "JFK", "نيويورك": "JFK",
    "singapore": "SIN", "sin": "SIN", "سنغافورة": "SIN",
    "bangkok": "BKK", "bkk": "BKK", "بانكوك": "BKK",
    "riyadh": "RUH", "ruh": "RUH", "الرياض": "RUH",
    "dammam": "DMM", "dmm": "DMM", "الدمام": "DMM",
}

AIRLINES = (
    "Saudia", "Qatar Airways", "British Airways", "Emirates",
    "flynas", "Gulf Air", "EgyptAir", "Turkish Airlines",
)

ORIGINS = SEARCH_AIRPORT_CODES
REGIONAL_HUBS = {
    "Middle East": ("DOH", "DXB", "AMM"),
    "Europe": ("IST", "LHR", "CDG"),
    "Africa": ("CAI", "JED", "AMM"),
    "Asia": ("DOH", "DXB", "SIN", "BKK"),
    "North America": ("LHR", "IST", "CDG"),
}

REGION_BY_AIRPORT = {
    "RUH":"Middle East", "JED":"Middle East", "DMM":"Middle East", "MED":"Middle East",
    "DOH":"Middle East", "DXB":"Middle East", "AMM":"Middle East", "KWI":"Middle East",
    "LHR":"Europe", "CDG":"Europe", "IST":"Europe",
    "CAI":"Africa", "BEY":"Middle East", "TUN":"Africa",
    "JFK":"North America", "SIN":"Asia", "BKK":"Asia",
}

STOPOVER_AIRPORTS = tuple(dict.fromkeys(hub for hubs in REGIONAL_HUBS.values() for hub in hubs))


def _build_mock_catalog() -> list[dict[str, Any]]:
    catalog: list[dict[str, Any]] = []
    route_index = 0

    for origin in ORIGINS:
        for destination in SEARCH_AIRPORT_CODES:
            if origin == destination:
                continue

            airline = AIRLINES[(route_index) % len(AIRLINES)]
            base_price = 420.0 + ((route_index * 137) % 2850)
            duration_hours = 2 + ((route_index * 5) % 11)
            duration_minutes = (route_index * 13) % 60
            catalog.append({
                "flight_id": f"{airline[:2].upper()}-{100 + route_index}",
                "airline": airline,
                "origin": origin,
                "destination": destination,
                "base_price_sar": float(base_price),
                "stops": 0,
                "stopover_airport": None,
                "duration": f"{duration_hours}h {duration_minutes:02d}m",
            })

            if route_index % 2 == 0:
                destination_region = REGION_BY_AIRPORT.get(destination, "Middle East")
                stopover_candidates = REGIONAL_HUBS[destination_region]
                stopover = next(
                    (hub for hub in stopover_candidates if hub not in {origin, destination}),
                    next((hub for hub in STOPOVER_AIRPORTS if hub not in {origin, destination}), None),
                )
                if stopover:
                    catalog.append({
                        "flight_id": f"{AIRLINES[(route_index + 3) % len(AIRLINES)][:2].upper()}-{300 + route_index}",
                        "airline": AIRLINES[(route_index + 3) % len(AIRLINES)],
                        "origin": origin,
                        "destination": destination,
                        "base_price_sar": float(base_price + 260.0),
                        "stops": 1,
                        "stopover_airport": stopover,
                        "duration": f"{duration_hours + 4}h {duration_minutes:02d}m",
                    })

            route_index += 1

    common_routes = (
        ("RUH", "DXB", "Saudia", 0, None, "2h 00m", 850.0),
        ("IST", "RUH", "Turkish Airlines", 0, None, "3h 52m", 733.7),
        ("KWI", "JFK", "EgyptAir", 0, None, "10h 18m", 1242.0),
        ("KWI", "JFK", "Qatar Airways", 1, "DOH", "16h 45m", 4380.0),
        ("JFK", "KWI", "Qatar Airways", 1, "DOH", "16h 45m", 4380.0),
    )
    for airline_route_index, (origin, destination, airline, stops, stopover, duration, base_price) in enumerate(common_routes):
        catalog.append({
            "flight_id": f"{airline[:2].upper()}-{400 + airline_route_index}",
            "airline": airline,
            "origin": origin,
            "destination": destination,
            "base_price_sar": float(base_price),
            "stops": stops,
            "stopover_airport": stopover,
            "duration": duration,
        })

    return catalog


MOCK_FLIGHTS = _build_mock_catalog()


def search_mock_flights(origin: str, destination: str, direct_only: bool = False, allow_stopovers: bool = True, require_stopover: bool = False) -> list[dict[str, Any]]:
    origin = origin.strip().upper()
    destination = destination.strip().upper()
    if not origin or not destination:
        raise ValueError("Origin and destination are required")

    matches = [
        flight.copy()
        for flight in MOCK_FLIGHTS
        if flight["origin"] == origin
        and flight["destination"] == destination
        and (not direct_only or flight["stops"] == 0)
        and (allow_stopovers or flight["stops"] == 0)
        and (not require_stopover or flight["stops"] > 0)
    ]
    return matches


def calculate_total_cost(base_price_sar: float, extra_bags: int = 0) -> dict[str, float]:
    if base_price_sar <= 0:
        raise ValueError("Base price must be positive")
    if extra_bags < 0:
        raise ValueError("Extra bags cannot be negative")

    tax = round(base_price_sar * 0.15, 2)
    # The first paid bag costs 150 SAR; each additional bag costs 250 SAR.
    baggage_fee = 0.0 if extra_bags == 0 else round(150.0 + ((extra_bags - 1) * 250.0), 2)
    total = round(base_price_sar + tax + baggage_fee, 2)
    return {
        "tax_sar": tax,
        "baggage_fee_sar": baggage_fee,
        "total_price_sar": total,
    }


def search_and_price(origin: str, destination: str, extra_bags: int = 0, direct_only: bool = False, allow_stopovers: bool = True, require_stopover: bool = False) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    for flight in search_mock_flights(origin, destination, direct_only, allow_stopovers, require_stopover):
        cost = calculate_total_cost(flight["base_price_sar"], extra_bags)
        options.append({**flight, **cost})
    return sorted(options, key=lambda option: option["total_price_sar"])
