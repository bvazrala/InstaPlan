"""Validated planning values shared by normalization and pure evaluation; no private I/O."""
from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel


class PlanningValue(BaseModel):
    model_config = ConfigDict(extra="forbid", alias_generator=to_camel, populate_by_name=True)


class Destination(PlanningValue):
    name: str = Field(min_length=1, max_length=120)
    airports: list[str] = Field(min_length=1, max_length=4)
    source_fact_ids: list[str] = []

    @field_validator("airports")
    @classmethod
    def airport_codes(cls, values):
        codes = [value.strip().upper() for value in values]
        if any(len(code) != 3 or not code.isalpha() or not code.isascii() for code in codes):
            raise ValueError("Use three-letter airport codes")
        return list(dict.fromkeys(codes))


class Constraint(PlanningValue):
    kind: Literal["exclude_destination", "flight_only", "available_dates", "max_duration", "max_stops", "amenity", "unsupported"]
    member_id: str | None = None
    value: str = ""
    limit: int | None = Field(default=None, ge=0)
    start: date | None = None
    end: date | None = None
    source_fact_ids: list[str] = []


class Preference(PlanningValue):
    member_id: str | None = None
    category: Literal["Destination", "Lodging", "Travel"]
    value: str = Field(min_length=1)
    score: int = Field(ge=-2, le=2)
    source_fact_ids: list[str] = []


class PlanningInput(PlanningValue):
    destinations: list[Destination] = Field(default_factory=list, max_length=6)
    checkin: date | None = None
    checkout: date | None = None
    origins: dict[str, str] = {}
    constraints: list[Constraint] = []
    preferences: list[Preference] = []

    @field_validator("origins")
    @classmethod
    def origin_codes(cls, values):
        return {uid: Destination(name="origin", airports=[code]).airports[0] for uid, code in values.items()}

    def missing(self, member_ids: list[str]) -> list[str]:
        missing = []
        if not self.destinations:
            missing.append("destinations")
        if self.checkin is None:
            missing.append("checkin")
        if self.checkout is None:
            missing.append("checkout")
        if self.checkin and self.checkout and self.checkout <= self.checkin:
            missing.append("checkout_after_checkin")
        if self.checkin and self.checkin < date.today():
            missing.append("future_checkin")
        missing.extend(f"origin:{uid}" for uid in member_ids if uid not in self.origins)
        return missing


class PrivateRequirements(PlanningValue):
    # Never serialize this object to the shared option response or shared cache.
    constraints: list[Constraint] = []
    out_of_scope: bool = False  # all supplied requirements concern meals/activities only


# Exact public facts work without a model. Ambiguous text remains unresolved.
def known_inputs(ctx) -> PlanningInput:
    import re
    known = {
        "new york": ("New York City", "JFK"), "new york city": ("New York City", "JFK"), "nyc": ("New York City", "JFK"),
        "austin": ("Austin", "AUS"), "boston": ("Boston", "BOS"), "los angeles": ("Los Angeles", "LAX"),
        "chicago": ("Chicago", "ORD"), "miami": ("Miami", "MIA"), "san francisco": ("San Francisco", "SFO"),
        "seattle": ("Seattle", "SEA"), "denver": ("Denver", "DEN"), "las vegas": ("Las Vegas", "LAS"),
    }
    inputs = PlanningInput()
    for member in ctx.members:
        if member.home_airport:
            try:
                inputs.origins[member.id] = Destination(name="origin", airports=[member.home_airport]).airports[0]
            except ValueError:
                pass
    def destination(value, source):
        if value.casefold() in known:
            name, code = known[value.casefold()]
            return Destination(name=name, airports=[code], source_fact_ids=source)
        if re.fullmatch(r"[A-Z]{3}", value):
            return Destination(name=value, airports=[value], source_fact_ids=source)
        return None
    for fact in ctx.facts:
        field, value = fact.field.casefold(), fact.value.strip()
        sources = [fact.id] if fact.id else []
        if field == "destination":
            found = destination(value, sources)
            if found and not any(d.name == found.name for d in inputs.destinations):
                inputs.destinations.append(found)
        elif field == "dates":
            inputs.checkin = inputs.checkout = None
            matches = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", value)
            if len(matches) == 2:
                try:
                    inputs.checkin, inputs.checkout = map(date.fromisoformat, matches)
                except ValueError:
                    inputs.checkin = inputs.checkout = None
        elif field == "from" and fact.by:
            inputs.origins.pop(fact.by, None)
            found = destination(value, sources)
            if found:
                inputs.origins[fact.by] = found.airports[0]
        elif field == "travel mode" and value.casefold() not in {"flight", "flights", "fly", "plane", "flight only", "flights only", "only flights"}:
            inputs.constraints.append(Constraint(kind="unsupported", member_id=fact.by, source_fact_ids=sources))
        elif field in {"max stops", "max duration"}:
            inputs.constraints.append(Constraint(kind=field.replace(" ", "_"), member_id=fact.by,
                limit=int(value) if value.isdigit() else None, source_fact_ids=sources))
        elif field == "exclude destination":
            excluded = destination(value, sources)
            inputs.constraints.append(Constraint(kind="exclude_destination", member_id=fact.by,
                                                 value=excluded.name if excluded else value, source_fact_ids=sources))
        elif field == "available dates":
            matches = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", value)
            try:
                start, end = map(date.fromisoformat, matches) if len(matches) == 2 else (None, None)
            except ValueError:
                start = end = None
            inputs.constraints.append(Constraint(kind="available_dates", member_id=fact.by,
                                                 start=start, end=end, source_fact_ids=sources))
        elif field in {"amenity", "accessibility"} or (field == "lodging" and fact.required):
            inputs.constraints.append(Constraint(kind="amenity", member_id=fact.by, value=value, source_fact_ids=sources))
        if field == "hard requirement" or (field == "lodging" and not fact.required and
                re.search(r"\b(must|need|required|never|cannot|only)\b", value, re.IGNORECASE)):
            inputs.constraints.append(Constraint(kind="unsupported", member_id=fact.by, source_fact_ids=sources))
        if fact.score is not None and fact.field in {"Destination", "Lodging", "Travel"}:
            inputs.preferences.append(Preference(category=fact.field, member_id=fact.by, value=value,
                                                 score=fact.score, source_fact_ids=sources))
    inputs.destinations = inputs.destinations[:6]
    return inputs
