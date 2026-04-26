"""
Football Match Search Telegram Bot
Finds football matches (free & paid, all categories) near the user's location.
Uses:
  - Overpass API (OpenStreetMap) – free, finds football venues/pitches nearby
  - API-Football via RapidAPI    – professional/amateur fixture schedules
  - Nominatim (OpenStreetMap)    – reverse-geocoding & city search (free)
"""

import os
import math
import logging
import datetime
from typing import Optional

import requests
from dotenv import load_dotenv
from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")  # API-Football via RapidAPI

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM_URL = "https://nominatim.openstreetmap.org"
API_FOOTBALL_BASE = "https://api-football-v1.p.rapidapi.com/v3"
SEARCH_RADIUS_M = 25_000   # 25 km default radius for venue search
MAX_VENUES = 15
MAX_FIXTURES = 20
DAYS_AHEAD = 30            # look this many days ahead for fixtures

HEADERS_RAPIDAPI = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in kilometres between two lat/lon points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def geocode_city(city: str) -> Optional[tuple[float, float, str]]:
    """Return (lat, lon, display_name) for a city string, or None."""
    try:
        r = requests.get(
            f"{NOMINATIM_URL}/search",
            params={"q": city, "format": "json", "limit": 1},
            headers={"User-Agent": "FootballSearchBot/1.0"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"]), data[0]["display_name"]
    except Exception as exc:
        logger.warning("Geocoding failed for %s: %s", city, exc)
    return None


def reverse_geocode(lat: float, lon: float) -> str:
    """Return a human-readable address for a lat/lon pair."""
    try:
        r = requests.get(
            f"{NOMINATIM_URL}/reverse",
            params={"lat": lat, "lon": lon, "format": "json"},
            headers={"User-Agent": "FootballSearchBot/1.0"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("display_name", f"{lat:.5f}, {lon:.5f}")
    except Exception:
        return f"{lat:.5f}, {lon:.5f}"


def find_football_venues(lat: float, lon: float, radius_m: int = SEARCH_RADIUS_M) -> list[dict]:
    """
    Query Overpass for football pitches, stadiums and sport centres near lat/lon.
    Returns list of venue dicts with name, address, lat, lon, type, distance_km.
    """
    query = f"""
    [out:json][timeout:25];
    (
      node["sport"="football"](around:{radius_m},{lat},{lon});
      way["sport"="football"](around:{radius_m},{lat},{lon});
      node["leisure"="stadium"]["sport"="football"](around:{radius_m},{lat},{lon});
      way["leisure"="stadium"]["sport"="football"](around:{radius_m},{lat},{lon});
      node["amenity"="sports_centre"]["sport"="football"](around:{radius_m},{lat},{lon});
      way["amenity"="sports_centre"]["sport"="football"](around:{radius_m},{lat},{lon});
      node["leisure"="pitch"]["sport"="football"](around:{radius_m},{lat},{lon});
      way["leisure"="pitch"]["sport"="football"](around:{radius_m},{lat},{lon});
    );
    out center tags;
    """
    try:
        resp = requests.post(OVERPASS_URL, data=query, timeout=30)
        resp.raise_for_status()
        elements = resp.json().get("elements", [])
    except Exception as exc:
        logger.warning("Overpass query failed: %s", exc)
        return []

    venues = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name") or tags.get("description") or "Football venue"
        # node vs way (way has a 'center')
        if el["type"] == "node":
            vlat, vlon = el.get("lat", lat), el.get("lon", lon)
        else:
            center = el.get("center", {})
            vlat, vlon = center.get("lat", lat), center.get("lon", lon)

        access = tags.get("access", "")
        fee = tags.get("fee", "")
        if fee.lower() in ("yes", "true"):
            entry = "💰 Paid"
        elif fee.lower() in ("no", "false", "free"):
            entry = "🆓 Free"
        elif access.lower() == "private":
            entry = "🔒 Private"
        else:
            entry = "❓ Unknown"

        surface = tags.get("surface", "")
        lit = tags.get("lit", "")
        leisure = tags.get("leisure", tags.get("amenity", "pitch"))

        dist = haversine(lat, lon, vlat, vlon)
        venues.append(
            {
                "name": name,
                "lat": vlat,
                "lon": vlon,
                "distance_km": round(dist, 2),
                "entry": entry,
                "surface": surface,
                "lit": lit,
                "type": leisure,
                "osm_id": el.get("id"),
                "tags": tags,
            }
        )

    venues.sort(key=lambda v: v["distance_km"])
    return venues[:MAX_VENUES]


def get_nearby_fixtures(lat: float, lon: float) -> list[dict]:
    """
    Find fixtures near a location using API-Football.
    Searches leagues associated with the city country/timezone.
    Returns list of fixture dicts.
    """
    if not RAPIDAPI_KEY:
        return []

    today = datetime.date.today()
    future = today + datetime.timedelta(days=DAYS_AHEAD)

    # Step 1: find timezone from Nominatim to get country code
    country_code = _country_from_coords(lat, lon)
    if not country_code:
        return []

    # Step 2: get leagues for that country
    try:
        r = requests.get(
            f"{API_FOOTBALL_BASE}/leagues",
            headers=HEADERS_RAPIDAPI,
            params={"country": country_code, "current": "true"},
            timeout=15,
        )
        r.raise_for_status()
        leagues = r.json().get("response", [])
    except Exception as exc:
        logger.warning("API-Football leagues failed: %s", exc)
        return []

    # Collect fixtures from each league (up to first 5 leagues to avoid rate limits)
    fixtures = []
    for league_obj in leagues[:5]:
        league_id = league_obj["league"]["id"]
        season = league_obj["seasons"][0]["year"] if league_obj.get("seasons") and len(league_obj["seasons"]) > 0 else today.year
        try:
            r = requests.get(
                f"{API_FOOTBALL_BASE}/fixtures",
                headers=HEADERS_RAPIDAPI,
                params={
                    "league": league_id,
                    "season": season,
                    "from": today.isoformat(),
                    "to": future.isoformat(),
                    "timezone": "UTC",
                },
                timeout=15,
            )
            r.raise_for_status()
            for fix in r.json().get("response", []):
                venue = fix.get("fixture", {}).get("venue", {})
                status = fix.get("fixture", {}).get("status", {}).get("long", "")
                date_str = fix.get("fixture", {}).get("date", "")
                home = fix.get("teams", {}).get("home", {}).get("name", "?")
                away = fix.get("teams", {}).get("away", {}).get("name", "?")
                league_name = fix.get("league", {}).get("name", "")
                league_logo = fix.get("league", {}).get("logo", "")
                venue_name = venue.get("name", "Unknown venue")
                venue_city = venue.get("city", "")
                venue_lat = None
                venue_lon = None

                # try to geocode the venue city for distance
                if venue_city:
                    geo = geocode_city(f"{venue_name}, {venue_city}")
                    if geo:
                        venue_lat, venue_lon, _ = geo

                dist = (
                    haversine(lat, lon, venue_lat, venue_lon)
                    if venue_lat is not None
                    else None
                )

                fixtures.append(
                    {
                        "home": home,
                        "away": away,
                        "league": league_name,
                        "league_logo": league_logo,
                        "venue": venue_name,
                        "city": venue_city,
                        "date": date_str,
                        "status": status,
                        "distance_km": dist,
                        "lat": venue_lat,
                        "lon": venue_lon,
                    }
                )
        except Exception as exc:
            logger.warning("Fixtures fetch failed for league %s: %s", league_id, exc)

    # Sort by distance (unknown distance last), then date
    fixtures.sort(
        key=lambda f: (
            f["distance_km"] if f["distance_km"] is not None else 9999,
            f["date"],
        )
    )
    return fixtures[:MAX_FIXTURES]


def _country_from_coords(lat: float, lon: float) -> Optional[str]:
    """Return ISO-2 country code for coordinates via Nominatim."""
    try:
        r = requests.get(
            f"{NOMINATIM_URL}/reverse",
            params={"lat": lat, "lon": lon, "format": "json"},
            headers={"User-Agent": "FootballSearchBot/1.0"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("address", {}).get("country_code", "").upper() or None
    except Exception:
        return None


def format_venue_message(venues: list[dict], origin_address: str) -> str:
    if not venues:
        return "⚠️ No football venues found within 25 km of your location."

    address_display = origin_address if len(origin_address) <= 60 else origin_address[:60] + "…"
    lines = [
        f"📍 *Nearby Football Venues*\n_(within 25 km of {address_display})_\n"
    ]
    for i, v in enumerate(venues, 1):
        surface_txt = f" | Surface: {v['surface']}" if v["surface"] else ""
        lit_txt = " | 🌙 Floodlit" if v["lit"].lower() in ("yes", "true") else ""
        maps_link = f"https://www.openstreetmap.org/?mlat={v['lat']}&mlon={v['lon']}&zoom=17"
        lines.append(
            f"*{i}. {v['name']}*\n"
            f"   📏 {v['distance_km']} km away\n"
            f"   🏟️ Type: {v['type'].capitalize()}{surface_txt}{lit_txt}\n"
            f"   💳 Entry: {v['entry']}\n"
            f"   🗺️ [Open on Map]({maps_link})\n"
        )
    return "\n".join(lines)


def format_fixture_message(fixtures: list[dict]) -> str:
    if not fixtures:
        if not RAPIDAPI_KEY:
            return (
                "ℹ️ *Match Schedule Search*\n"
                "To search for professional/amateur fixture schedules set the "
                "`RAPIDAPI_KEY` environment variable (get a free key at "
                "https://rapidapi.com/api-sports/api/api-football)."
            )
        return "⚠️ No upcoming fixtures found in your area in the next 30 days."

    lines = ["📅 *Upcoming Football Matches Near You*\n"]
    for f in fixtures:
        try:
            dt = datetime.datetime.fromisoformat(f["date"].replace("Z", "+00:00"))
            date_fmt = dt.strftime("%a %d %b %Y, %H:%M UTC")
        except Exception:
            date_fmt = f["date"]

        dist_txt = f"{f['distance_km']:.1f} km away" if f["distance_km"] is not None else "distance unknown"
        maps_txt = ""
        if f["lat"] and f["lon"]:
            maps_url = f"https://www.openstreetmap.org/?mlat={f['lat']}&mlon={f['lon']}&zoom=14"
            maps_txt = f"   🗺️ [Venue on Map]({maps_url})\n"

        lines.append(
            f"⚽ *{f['home']}* vs *{f['away']}*\n"
            f"   🏆 {f['league']}\n"
            f"   📍 {f['venue']}, {f['city']} ({dist_txt})\n"
            f"   🕐 {date_fmt}\n"
            f"   📊 Status: {f['status']}\n"
            f"{maps_txt}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Telegram handlers
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [[KeyboardButton("📍 Share My Location", request_location=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        "👋 *Football Match Finder Bot*\n\n"
        "I can find football venues and upcoming matches near you – "
        "free, paid, amateur, and professional! ⚽\n\n"
        "*How to use:*\n"
        "• Tap *Share My Location* below to search around you\n"
        "• Or type `/search <city name>` to search any city\n\n"
        "I'll show you:\n"
        "🏟️ Nearby football pitches & stadiums\n"
        "📅 Upcoming fixture schedules\n"
        "🆓💰 Free and paid venues\n"
        "🗺️ Precise map links for every location",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "*Football Match Finder – Help*\n\n"
        "*/start* – Welcome message & location button\n"
        "*/search <city>* – Search for football venues and matches in a city\n"
        "*/help* – Show this help message\n\n"
        "*Location sharing*\n"
        "Tap the 📍 button to share your live location and get results "
        "personalised to where you are right now.\n\n"
        "*Data sources*\n"
        "• Venues: OpenStreetMap (Overpass API) – always free\n"
        "• Fixtures: API-Football (RapidAPI) – requires a free API key\n\n"
        "*Tip:* Set the `RAPIDAPI_KEY` env variable to enable fixture search.",
        parse_mode="Markdown",
    )


async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    loc = update.message.location
    lat, lon = loc.latitude, loc.longitude
    await _run_search(update, context, lat, lon)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text(
            "Please provide a city name: `/search London`", parse_mode="Markdown"
        )
        return
    await update.message.reply_text(f"🔍 Searching for football near *{query}*…", parse_mode="Markdown")
    result = geocode_city(query)
    if not result:
        await update.message.reply_text(
            f"❌ Could not find location for *{query}*. Try a different city name.",
            parse_mode="Markdown",
        )
        return
    lat, lon, display = result
    await _run_search(update, context, lat, lon, location_label=display)


async def _run_search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    lat: float,
    lon: float,
    location_label: Optional[str] = None,
) -> None:
    if location_label is None:
        location_label = reverse_geocode(lat, lon)

    short_label = location_label.split(",")[0]

    # Let the user know we're working
    status_msg = await update.message.reply_text(
        f"⚽ Searching for football near *{short_label}*…\n"
        "_(This may take a few seconds)_",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )

    # --- venues (Overpass) ---
    venues = find_football_venues(lat, lon)
    venue_text = format_venue_message(venues, short_label)

    # --- fixtures (API-Football) ---
    fixtures = get_nearby_fixtures(lat, lon)
    fixture_text = format_fixture_message(fixtures)

    # Edit the status message and send results
    await status_msg.delete()

    # Send venue results
    await update.message.reply_text(venue_text, parse_mode="Markdown", disable_web_page_preview=True)

    # Send fixture results
    await update.message.reply_text(fixture_text, parse_mode="Markdown", disable_web_page_preview=True)

    # Offer to search again
    keyboard = [[KeyboardButton("📍 Search Again (My Location)", request_location=True)]]
    await update.message.reply_text(
        "🔁 Want to search again? Share your location or use `/search <city>`.",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True),
    )


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "I didn't understand that. Use /start to begin or /help for instructions."
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not TELEGRAM_TOKEN:
        raise ValueError(
            "TELEGRAM_TOKEN environment variable is not set. "
            "Get a token from @BotFather on Telegram."
        )

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))

    logger.info("Bot is running…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
