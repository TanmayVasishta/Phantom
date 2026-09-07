"""
Public-place allowlist for LOCATION/GPE PII detection.

Presidio and spaCy both tag ordinary country/city names as PII the same way
they'd tag a home address — "what is the capital of Japan" redacts to
"what is the capital of [PII_LOCATION_1]" and the model can no longer see
what's being asked, so it refuses to answer. Countries, capitals, and
well-known cities are public information; only redact a place name when it is
functioning as someone's PERSONAL location.

Shared between sentinel/pii_engine.py (Phantom 1.0) and
agent_v2/privacy/redactor.py (Phantom 2.0) rather than duplicated — both
tiered PII cascades hit the exact same false positive.

A name-only allowlist cannot work on its own: "my hometown is Paris" and
"the Eiffel Tower is in Paris" contain the identical entity string and need
OPPOSITE verdicts. Matching a known place makes an entity ELIGIBLE for the
skip; a personal-context cue nearby (my/I live/hometown/reside/address/from)
then overrides it back to PII regardless of how famous the place is — that's
what keeps "I live at 42 MG Road Bengaluru" and "my hometown is Paris"
redacted while "what is the capital of Japan" and "the Eiffel Tower is in
Paris" pass through untouched.
"""
from __future__ import annotations

import re

COUNTRIES = {
    "afghanistan", "albania", "algeria", "andorra", "angola",
    "antigua and barbuda", "argentina", "armenia", "australia", "austria",
    "azerbaijan", "bahamas", "bahrain", "bangladesh", "barbados", "belarus",
    "belgium", "belize", "benin", "bhutan", "bolivia",
    "bosnia and herzegovina", "botswana", "brazil", "brunei", "bulgaria",
    "burkina faso", "burundi", "cabo verde", "cambodia", "cameroon",
    "canada", "central african republic", "chad", "chile", "china",
    "colombia", "comoros", "costa rica", "croatia", "cuba", "cyprus",
    "czechia", "czech republic", "denmark", "djibouti", "dominica",
    "dominican republic", "ecuador", "egypt", "el salvador",
    "equatorial guinea", "eritrea", "estonia", "eswatini", "ethiopia",
    "fiji", "finland", "france", "gabon", "gambia", "georgia", "germany",
    "ghana", "greece", "grenada", "guatemala", "guinea", "guinea-bissau",
    "guyana", "haiti", "honduras", "hungary", "iceland", "india",
    "indonesia", "iran", "iraq", "ireland", "israel", "italy",
    "ivory coast", "cote d'ivoire", "jamaica", "japan", "jordan",
    "kazakhstan", "kenya", "kiribati", "kosovo", "kuwait", "kyrgyzstan",
    "laos", "latvia", "lebanon", "lesotho", "liberia", "libya",
    "liechtenstein", "lithuania", "luxembourg", "madagascar", "malawi",
    "malaysia", "maldives", "mali", "malta", "marshall islands",
    "mauritania", "mauritius", "mexico", "micronesia", "moldova", "monaco",
    "mongolia", "montenegro", "morocco", "mozambique", "myanmar",
    "namibia", "nauru", "nepal", "netherlands", "new zealand", "nicaragua",
    "niger", "nigeria", "north korea", "north macedonia", "norway", "oman",
    "pakistan", "palau", "palestine", "panama", "papua new guinea",
    "paraguay", "peru", "philippines", "poland", "portugal", "qatar",
    "romania", "russia", "rwanda", "saint kitts and nevis", "saint lucia",
    "saint vincent and the grenadines", "samoa", "san marino",
    "sao tome and principe", "saudi arabia", "senegal", "serbia",
    "seychelles", "sierra leone", "singapore", "slovakia", "slovenia",
    "solomon islands", "somalia", "south africa", "south korea",
    "south sudan", "spain", "sri lanka", "sudan", "suriname", "sweden",
    "switzerland", "syria", "taiwan", "tajikistan", "tanzania", "thailand",
    "timor-leste", "togo", "tonga", "trinidad and tobago", "tunisia",
    "turkey", "turkmenistan", "tuvalu", "uganda", "ukraine",
    "united arab emirates", "united kingdom", "united states",
    "united states of america", "uruguay", "uzbekistan", "vanuatu",
    "vatican city", "venezuela", "vietnam", "yemen", "zambia", "zimbabwe",
}

CAPITALS = {
    "kabul", "tirana", "algiers", "andorra la vella", "luanda",
    "st. john's", "buenos aires", "yerevan", "canberra", "vienna",
    "baku", "nassau", "manama", "dhaka", "bridgetown", "minsk", "brussels",
    "belmopan", "porto-novo", "thimphu", "sucre", "la paz", "sarajevo",
    "gaborone", "brasilia", "bandar seri begawan", "sofia", "ouagadougou",
    "gitega", "praia", "phnom penh", "yaounde", "ottawa", "bangui",
    "n'djamena", "santiago", "beijing", "bogota", "moroni", "san jose",
    "zagreb", "havana", "nicosia", "prague", "copenhagen", "djibouti",
    "roseau", "santo domingo", "quito", "cairo", "san salvador", "malabo",
    "asmara", "tallinn", "mbabane", "addis ababa", "suva", "helsinki",
    "paris", "libreville", "banjul", "tbilisi", "berlin", "accra",
    "athens", "st. george's", "guatemala city", "conakry", "bissau",
    "georgetown", "port-au-prince", "tegucigalpa", "budapest", "reykjavik",
    "new delhi", "jakarta", "tehran", "baghdad", "dublin", "jerusalem",
    "rome", "yamoussoukro", "kingston", "tokyo", "amman", "astana",
    "nairobi", "tarawa", "pristina", "kuwait city", "bishkek",
    "vientiane", "riga", "beirut", "maseru", "monrovia", "tripoli",
    "vaduz", "vilnius", "luxembourg city", "antananarivo", "lilongwe",
    "kuala lumpur", "male", "bamako", "valletta", "majuro", "nouakchott",
    "port louis", "mexico city", "palikir", "chisinau", "monaco",
    "ulaanbaatar", "podgorica", "rabat", "maputo", "naypyidaw", "windhoek",
    "yaren", "kathmandu", "amsterdam", "wellington", "managua", "niamey",
    "abuja", "pyongyang", "skopje", "oslo", "muscat", "islamabad",
    "ngerulmud", "ramallah", "panama city", "port moresby", "asuncion",
    "lima", "manila", "warsaw", "lisbon", "doha", "bucharest", "moscow",
    "kigali", "basseterre", "castries", "kingstown", "apia",
    "san marino city", "riyadh", "dakar", "belgrade", "victoria",
    "freetown", "singapore city", "bratislava", "ljubljana", "honiara",
    "mogadishu", "pretoria", "cape town", "bloemfontein", "seoul", "juba",
    "madrid", "colombo", "khartoum", "paramaribo", "stockholm", "bern",
    "damascus", "taipei", "dushanbe", "dodoma", "bangkok", "dili", "lome",
    "nuku'alofa", "port of spain", "tunis", "ankara", "ashgabat",
    "funafuti", "kampala", "kyiv", "abu dhabi", "london", "washington",
    "washington dc", "washington d.c.", "montevideo", "tashkent",
    "port vila", "vatican city", "caracas", "hanoi", "sana'a", "lusaka",
    "harare",
}

# A handful of globally landmark-associated cities that are not national
# capitals but come up constantly in factual/geographic questions.
MAJOR_CITIES = {
    "new york", "new york city", "los angeles", "chicago", "sydney",
    "melbourne", "toronto", "vancouver", "shanghai", "hong kong",
    "dubai", "mumbai", "bengaluru", "bangalore", "barcelona", "milan",
    "istanbul", "st. petersburg", "saint petersburg", "rio de janeiro",
    "sao paulo", "osaka", "kyoto", "shenzhen", "guangzhou",
}

KNOWN_PLACES = COUNTRIES | CAPITALS | MAJOR_CITIES

PERSONAL_LOCATION_CONTEXT = re.compile(
    r"\b(my|i'?m|i\s+am)\s+(home\s*town|hometown)\b"
    r"|\bi\s+(live|reside|stay)\b"
    r"|\bmy\s+(home|address|residence|house|apartment|flat)\b"
    r"|\bi'?m\s+from\b|\bi\s+am\s+from\b"
    r"|\bmy\s+(city|town|neighborhood|neighbourhood)\b",
    re.IGNORECASE,
)


def is_public_place_mention(text: str, value: str) -> bool:
    """
    True if `value` should be left alone as a public/factual place reference
    rather than redacted as personal location PII.

    Only meaningful for a value that is itself a recognised LOCATION/GPE
    entity — this decides whether a place that has already been identified
    is being used personally or factually in `text`, not whether something
    is a place at all.
    """
    normalized = value.strip().lower().strip(".,!?;:")
    if normalized not in KNOWN_PLACES:
        return False
    return not PERSONAL_LOCATION_CONTEXT.search(text)
