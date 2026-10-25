"""Pure validation and completion rules for the listening lab."""

import re
from copy import deepcopy
from datetime import datetime

USERS = (
    {"id": "u1", "name": "You", "color": "#6957d8"},
    {"id": "u2", "name": "Maya", "color": "#e17a52"},
    {"id": "u3", "name": "Alex", "color": "#3b9db9"},
    {"id": "u4", "name": "Sam", "color": "#d268a1"},
)
USER_IDS = {user["id"] for user in USERS}
TOPICS = {"Dining", "Travel", "Entertainment", "Custom"}  # Custom: the group names its own category
CUSTOM_LABEL = re.compile(r"^[\w &'/-]{2,40}$")
MEALS = {"breakfast", "lunch", "dinner", "snack", "brunch", "coffee"}
ACCOMMODATIONS = {"hotel", "airbnb", "hostel", "none"}
# Muse sometimes names a topic field loosely; map the obvious synonyms instead of dropping the update.
FIELD_ALIASES = {"transportation": "trip_type", "transport": "trip_type", "travel_mode": "trip_type",
                 "mode_of_travel": "trip_type", "travel_type": "trip_type", "lodging": "accommodation",
                 "stay": "accommodation", "activity": "activity_type", "food_type": "cuisine",
                 "event": "event_type", "event_kind": "event_type"}
TRIP_TYPES = {"flights": "flight", "fly": "flight", "plane": "flight", "airplane": "flight", "air": "flight",
              "buses": "bus", "trains": "train", "rail": "train"}
CLUSTER_FIELDS = {
    "Dining": {"meal_type", "cuisine"},
    "Travel": {"trip_type", "accommodation"},
    "Entertainment": {"activity_type"},
    "Custom": {"event_type"},  # a short description of what the custom event is
}


def new_template(title: str, topic: str, location: str = "", location_kind: str = "search_area",
                 place: dict | None = None, initiator: str = "u1", custom_label: str = "",
                 category_image: dict | None = None) -> dict:
    title = title.strip()
    if not 1 <= len(title) <= 120:
        raise ValueError("Title is required (up to 120 characters)")
    if topic not in TOPICS:
        raise ValueError("Choose Dining, Travel, Entertainment, or a custom category")
    custom_label = custom_label.strip()
    if topic == "Custom" and not CUSTOM_LABEL.match(custom_label):
        raise ValueError("Name your category (2-40 letters, numbers or spaces)")
    if location_kind not in {"destination", "search_area"}:
        raise ValueError("Invalid location type")
    if len(location) > 200:
        raise ValueError("Location is too long")
    return {
        "title": title,
        "initiator": initiator,  # who opened the planner; not an owner
        "base_location": (place or {}).get("address") or location.strip() or None,  # where the group starts from
        "topic": topic,
        "custom_label": custom_label if topic == "Custom" else None,  # what the user called their category
        "category_image": category_image,  # {url, title, source} from a photo search; display only
        "when": {"flexibility": {}, "agreed": None},
        "where": {"destination": None, "destination_hint": None, "search_area": None, "origins": {}},
        "preferences": {},
        "hard_constraints": {},
        "budget": {},
        "spoke": [],  # members who have sent a message (drives the inactive = conditional default)
        "attendance": {},  # per person: going / not_going / conditional (+ condition text)
        "cluster": {},
        "sources": {},
    } | {"where": {"destination": place if location_kind == "destination" else None, "destination_hint": None,
                   "search_area": None if location_kind == "destination" else (location.strip() or None),
                   "origins": {}}}


STATUSES = {"going", "not_going", "conditional"}


def attending(template: dict) -> set[str]:
    """Everyone who has not declined; they are the people the plan is for and who vote."""
    declined = {uid for uid, entry in template.get("attendance", {}).items() if entry["status"] == "not_going"}
    return USER_IDS - declined


def effective_attendance(template: dict) -> dict[str, dict]:
    """Stated status per person. Without one: someone who has spoken is treated as going, and someone who has not
    spoken yet is conditional ('hasn't responded yet'), so inactive members never block the plan."""
    spoke = set(template.get("spoke", []))
    result = {}
    for uid in sorted(USER_IDS):
        entry = template.get("attendance", {}).get(uid)
        if entry:
            result[uid] = {**entry, "inferred": False}
        elif uid in spoke:
            result[uid] = {"status": "going", "condition": None, "inferred": True}
        else:
            result[uid] = {"status": "conditional", "condition": "hasn't responded yet", "inferred": True}
    return result


def _attendance(value: object) -> tuple[dict | None, str | None]:
    status = value.get("status") if isinstance(value, dict) else value
    condition = value.get("condition") if isinstance(value, dict) else None
    status = status.strip().lower().replace(" ", "_").replace("-", "_") if isinstance(status, str) else None
    status = {"no": "not_going", "cant_go": "not_going", "declined": "not_going", "yes": "going", "maybe": "conditional"}.get(status, status)
    if status not in STATUSES:
        return None, "attendance must be going, not_going or conditional"
    if condition is not None and (not isinstance(condition, str) or len(condition.strip()) > 120):
        return None, "attendance condition must be a short string"
    return {"status": status, "condition": (condition or "").strip() or None if status == "conditional" else None}, None


def missing_fields(template: dict) -> list[str]:
    missing = []
    if not template["title"]:
        missing.append("title")
    # A time is settled once the chat converged on one (when.agreed), or the people who are actively going have
    # each given theirs. Declined and conditional (including not-yet-heard-from) members never hold the plan up.
    if not attending(template):
        missing.append("at least one person attending")
    eff = effective_attendance(template)
    waiting = [user["name"] for user in USERS if eff[user["id"]]["status"] == "going"
               and user["id"] not in template["when"]["flexibility"]]
    if not template["when"].get("agreed") and (waiting or not template["when"]["flexibility"]):
        missing.append("when.agreed (or availability from " + (", ".join(waiting) or "someone going") + ")")
    if not (template["where"]["destination"] or template["where"]["search_area"]):
        missing.append("where.destination or where.search_area")
    return missing  # topic (cluster) fields are all optional


def _dedupe_windows(value: list[dict] | None) -> list[dict] | None:
    """Keep each distinct window once (case-insensitive), in the order given."""
    if value is None:
        return None
    seen, windows = set(), []
    for window in value:
        label = window["label"].strip()
        if label.lower() not in seen:
            seen.add(label.lower())
            windows.append({"label": label})
    return windows


WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _agreed(value: object) -> tuple[dict | None, str | None]:
    """The group's settled time: a label plus an ISO date only when it is a real date on the named weekday."""
    label, date = (value, None) if isinstance(value, str) else (
        (value.get("label"), value.get("date")) if isinstance(value, dict) else (None, None))
    if not isinstance(label, str) or not 0 < len(label.strip()) <= 120:
        return None, "agreed time needs a short label"
    parsed = None
    if isinstance(date, str):
        try:
            parsed = datetime.strptime(date.strip(), "%Y-%m-%d").date()
        except ValueError:
            parsed = None  # an impossible date (Feb 30) is dropped, the label stays
    if parsed:
        named = [day for day in WEEKDAYS if day in label.lower() or day[:3] in label.lower().split()]
        if named and WEEKDAYS[parsed.weekday()] not in named:
            parsed = None  # "Sunday" labelled with a Monday date: keep the words, not the wrong date
    return {"label": label.strip(), "date": parsed.isoformat() if parsed else None}, None


def _strings(value: object) -> list[str] | None:
    if not isinstance(value, list) or len(value) > 20:
        return None
    if not all(isinstance(item, str) and 0 < len(item.strip()) <= 160 for item in value):
        return None
    return [item.strip() for item in value]


def apply_updates(template: dict, updates: object, messages: list[dict]) -> tuple[dict, list[dict]]:
    """Apply only grounded, group-safe fields. One source message must support each update."""
    result = deepcopy(template)
    by_id = {message["id"]: message for message in messages}
    decisions = []
    if not isinstance(updates, list):
        return result, [{"accepted": False, "reason": "updates must be a list"}]
    for item in updates[:30]:
        if not isinstance(item, dict):
            decisions.append({"accepted": False, "reason": "invalid update"})
            continue
        field, value = item.get("field"), item.get("value")
        if isinstance(field, str):
            field = field.strip()
            for prefix in ("cluster.", "template."):  # Muse often prefixes topic fields
                if field.startswith(prefix):
                    field = field[len(prefix):]
            field = FIELD_ALIASES.get(field, field)
        if field == "trip_type" and isinstance(value, str):
            value = TRIP_TYPES.get(value.strip().lower(), value)
        source_id, user_id = item.get("source_message_id"), item.get("user_id")
        source = by_id.get(source_id)
        reason = None
        if not source:
            reason = "source message is not in this batch"
        elif field == "where.origins":
            reason = "origins come from each member's device location, not the chat"
        elif field == "where.destination":
            reason = "the exact destination must be picked from Google Maps, not extracted from chat"
        elif field == "where.destination_hint":
            if not isinstance(value, str) or not 0 < len(value.strip()) <= 120:
                reason = "hint must be a short place name"
            else:
                result["where"]["destination_hint"] = value.strip()
        elif field == "when.agreed":
            agreed, reason = _agreed(value)
            if reason is None:
                result["when"]["agreed"] = agreed
        elif field in {"when.flexibility", "preferences", "hard_constraints", "budget", "attendance"}:
            if user_id not in USER_IDS or user_id != source["user_id"]:
                reason = "personal field must belong to the speaker"
            elif field == "attendance":
                entry, reason = _attendance(value)
                if reason is None:
                    result["attendance"][user_id] = entry
                    if entry["status"] == "not_going":
                        result["when"]["flexibility"].pop(user_id, None)  # a decline replaces any earlier availability
            elif field == "when.flexibility":
                if value == []:
                    reason = "an empty availability is not accepted; use attendance not_going for 'can't go'"
                elif value is not None and (not isinstance(value, list) or not value or len(value) > 10 or
                                          not all(isinstance(window, dict) and
                                                  isinstance(window.get("label"), str) and
                                                  0 < len(window["label"].strip()) <= 160 for window in value)):
                    reason = "availability must be explicit flexible (null) or time windows with labels"
                else:
                    result["when"]["flexibility"][user_id] = _dedupe_windows(value)
            elif field == "budget":
                if value is not None and (isinstance(value, bool) or not isinstance(value, int | float)
                                          or not 0 <= value <= 10_000_000):
                    reason = "budget must be a number or null"
                else:
                    result["budget"][user_id] = value
            else:
                cleaned = _strings(value)
                if cleaned is None:
                    reason = "expected a list of short strings"
                else:
                    result[field][user_id] = cleaned
        elif field == "where.search_area":
            if not isinstance(value, str) or not 0 < len(value.strip()) <= 200:
                reason = "search area must be a nonempty label"
            elif result["where"]["destination"]:
                reason = "an exact destination is already chosen"
            else:
                result["where"]["search_area"] = value.strip()
        elif field in CLUSTER_FIELDS[result["topic"]]:
            if field == "cuisine":
                cleaned = _strings(value)
                if cleaned is None:
                    reason = "cuisine must be a list of strings"
                else:
                    result["cluster"][field] = cleaned
            elif not isinstance(value, str) or not 0 < len(value.strip()) <= 120:
                reason = "topic field must be a nonempty string"
            elif field == "meal_type" and value.strip().lower() not in MEALS:
                reason = "invalid meal type"
            elif field == "accommodation" and value.strip().lower() not in ACCOMMODATIONS:
                reason = "invalid accommodation"
            else:
                result["cluster"][field] = value.strip().lower()
        else:
            reason = "unknown or inactive topic field"
        accepted = reason is None
        if accepted:
            result["sources"][f"{field}:{user_id or 'group'}"] = source_id
        decisions.append({"accepted": accepted, "field": field, "user_id": user_id,
                          "value": value, "source_message_id": source_id, "reason": reason})
    return result, decisions
