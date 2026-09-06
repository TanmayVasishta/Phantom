"""
Surrogate data generator.

Produces realistic-looking fake replacements rather than [REDACTED] blocks:
an LLM given "[REDACTED_PERSON] emailed [REDACTED_EMAIL]" tends to comment on
the redaction instead of answering, while "Michael Chen emailed
fake_river@northgate.com" reads as an ordinary sentence.

Pure Python, no IO, no model calls (spec target: < 5ms).
"""
from __future__ import annotations

import random
import re

FIRST_NAMES = [
    "Michael", "Sarah", "David", "Emily", "James", "Jessica", "Robert", "Ashley",
    "John", "Amanda", "Daniel", "Melissa", "Christopher", "Nicole", "Matthew",
    "Elizabeth", "Andrew", "Stephanie", "Joshua", "Rachel", "Ryan", "Laura",
    "Brandon", "Megan", "Justin", "Rebecca", "William", "Katherine", "Thomas",
    "Christina", "Kevin", "Amber", "Eric", "Danielle", "Brian", "Heather",
    "Adam", "Michelle", "Nathan", "Kimberly", "Patrick", "Samantha", "Jason",
    "Lauren", "Aaron", "Vanessa", "Sean", "Natalie", "Peter", "Olivia",
]

LAST_NAMES = [
    "Chen", "Anderson", "Martinez", "Thompson", "Walker", "Robinson", "Bennett",
    "Foster", "Hayes", "Coleman", "Reed", "Sullivan", "Murphy", "Gardner",
    "Palmer", "Fletcher", "Brooks", "Warren", "Reynolds", "Fisher", "Hughes",
    "Sanders", "Bryant", "Russell", "Griffin", "Porter", "Hamilton", "Grant",
    "Wallace", "Barnes", "Ellis", "Stone", "Mercer", "Whitfield", "Lawson",
    "Quinn", "Vaughn", "Harper", "Sterling", "Nolan", "Preston", "Sheppard",
    "Ashford", "Kingsley", "Marsh", "Delgado", "Ferris", "Langley", "Osborne",
    "Winters",
]

COMPANIES = [
    "Northgate Systems", "Blue Harbor Labs", "Vertex Dynamics", "Ironwood Group",
    "Clearwater Analytics", "Redstone Partners", "Lumen Industries", "Apex Manufacturing",
    "Silverline Tech", "Copperfield Media", "Brightpath Solutions", "Stonebridge Capital",
    "Vantage Robotics", "Harborview Logistics", "Cascade Networks", "Pinnacle Foods",
    "Meridian Health", "Foxglove Design", "Riverbend Energy", "Oakhill Ventures",
    "Summit Grove", "Larkspur Digital", "Crossfield Retail", "Windmere Studios",
    "Granite Peak Co", "Everline Software", "Baywood Chemicals", "Tanglewood Press",
    "Fairlane Motors", "Kestrel Aviation", "Alderwood Bank", "Highfield Insurance",
    "Nimbus Cloud Co", "Thornton Textiles", "Belmont Pharma", "Cedarcrest Realty",
    "Ridgeline Metals", "Halcyon Gaming", "Sablewood Foods", "Trellis Education",
    "Ambervale Optics", "Foundry Lane", "Wexford Consulting", "Drayton Marine",
    "Norwood Apparel", "Beacon Hill Data", "Quarry Road Co", "Elmgate Security",
    "Sandpiper Travel", "Ashcroft Devices",
]

CITIES = [
    "Springfield", "Riverside", "Fairview", "Georgetown", "Clinton", "Madison",
    "Franklin", "Salem", "Bristol", "Oxford", "Ashland", "Burlington",
    "Manchester", "Milton", "Newport", "Dover", "Auburn", "Kingston",
]

STATES = ["CA", "TX", "NY", "FL", "WA", "CO", "IL", "OR", "MA", "AZ", "NC", "OH"]

STREETS = [
    "Maple Street", "Oak Avenue", "Cedar Lane", "Pine Road", "Elm Drive",
    "Birch Court", "Willow Way", "Aspen Boulevard", "Juniper Place", "Chestnut Row",
]

DOMAIN_WORDS = [
    "northgate", "bluharbor", "vertexlab", "ironwood", "clearwater", "redstone",
    "lumenco", "apexworks", "silverline", "copperfield",
]

EMAIL_WORDS = [
    "river", "quartz", "meadow", "cobalt", "harbor", "cedar", "ember", "lark",
    "onyx", "willow", "flint", "aspen",
]


class SurrogateGenerator:
    """
    Seeded per session so the same session produces stable surrogates —
    "Michael Chen" stays "Michael Chen" for every turn of one conversation
    instead of becoming a different person on each message.
    """

    def __init__(self, session_id: str):
        self._rng = random.Random(session_id)

    # ── individual generators ────────────────────────────────────────────
    def person(self) -> str:
        return f"{self._rng.choice(FIRST_NAMES)} {self._rng.choice(LAST_NAMES)}"

    def email(self) -> str:
        return (f"fake_{self._rng.choice(EMAIL_WORDS)}"
                f"{self._rng.randint(10, 99)}@{self._rng.choice(DOMAIN_WORDS)}.com")

    def phone(self) -> str:
        # 555 is the reserved fictional US area code.
        return f"(555) {self._rng.randint(100, 999)}-{self._rng.randint(1000, 9999)}"

    def ssn(self) -> str:
        # 999 is never issued as a real SSN prefix.
        return f"999-{self._rng.randint(10, 99)}-{self._rng.randint(1000, 9999)}"

    def credit(self) -> str:
        # 4000-0000-0000-xxxx is the Visa test-card range.
        return f"4000-0000-0000-{self._rng.randint(1000, 9999)}"

    def address(self) -> str:
        return (f"{self._rng.randint(10, 9999)} {self._rng.choice(STREETS)}, "
                f"{self._rng.choice(CITIES)}, {self._rng.choice(STATES)}")

    def organization(self) -> str:
        return self._rng.choice(COMPANIES)

    def location(self) -> str:
        return f"{self._rng.choice(CITIES)}, {self._rng.choice(STATES)}"

    def date(self, original: str) -> str:
        """Shift a real date by 15-45 days, preserving its written format."""
        from datetime import datetime, timedelta
        shift = timedelta(days=self._rng.randint(15, 45))
        for fmt in ("%m/%d/%Y", "%m/%d/%y", "%d-%m-%Y", "%m-%d-%Y", "%Y-%m-%d"):
            try:
                return (datetime.strptime(original.strip(), fmt) + shift).strftime(fmt)
            except ValueError:
                continue
        return (datetime.now() + shift).strftime("%m/%d/%Y")

    def money(self, original: str) -> str:
        """Round to the nearest $1000 so the magnitude survives but the figure doesn't."""
        digits = re.sub(r"[^\d.]", "", original)
        try:
            value = float(digits)
        except ValueError:
            return "$5,000"
        rounded = max(1000, round(value / 1000) * 1000)
        return f"${rounded:,.0f}"

    def ip(self) -> str:
        # 203.0.113.0/24 is the TEST-NET-3 documentation range.
        return f"203.0.113.{self._rng.randint(1, 254)}"

    def url(self) -> str:
        return f"https://{self._rng.choice(DOMAIN_WORDS)}.example.com/page"

    def zipcode(self) -> str:
        return f"{self._rng.randint(10000, 99999)}"

    def age(self) -> str:
        return str(self._rng.randint(25, 65))

    # ── dispatch ─────────────────────────────────────────────────────────
    def generate(self, entity_type: str, original: str) -> str:
        et = (entity_type or "").upper()

        if et in ("PERSON", "TITLE", "NRP"):
            return self.person()
        if et in ("EMAIL", "EMAIL_ADDRESS"):
            return self.email()
        if et in ("PHONE", "PHONE_NUMBER"):
            return self.phone()
        if et in ("SSN", "US_SSN", "US_ITIN"):
            return self.ssn()
        if et in ("CREDIT", "CREDIT_CARD", "US_BANK_NUMBER", "IBAN_CODE", "CRYPTO"):
            return self.credit()
        if et in ("ORG", "ORGANIZATION"):
            return self.organization()
        if et in ("LOCATION", "GPE", "LOC", "FAC", "ADDRESS"):
            return self.address() if any(c.isdigit() for c in original) else self.location()
        if et in ("DATE", "DATE_TIME"):
            return self.date(original)
        if et == "MONEY":
            return self.money(original)
        if et in ("IP", "IP_ADDRESS"):
            return self.ip()
        if et == "URL":
            return self.url()
        if et == "ZIP":
            return self.zipcode()
        if et == "AGE":
            return self.age()
        if et in ("US_PASSPORT", "US_DRIVER_LICENSE", "MEDICAL_LICENSE", "ID"):
            return f"{self._rng.choice('ABCDEFGHJKLMN')}{self._rng.randint(1000000, 9999999)}"
        if et in ("PRODUCT", "EVENT"):
            return self.organization()
        return f"[REDACTED_{et or 'UNKNOWN'}]"
