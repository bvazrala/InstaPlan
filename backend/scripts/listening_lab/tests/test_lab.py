import time

import pytest

from scripts.listening_lab.contracts import apply_updates, missing_fields, new_template
from scripts.listening_lab.engine import ListeningEngine


class FakeMuse:
    configured = True

    def predict(self, template, notes, recent, empty):
        return [], {}

    def __init__(self):
        self.calls = []

    def extract(self, template, batch, before=None, after=None, notes=""):
        self.calls.append(batch)
        updates = []
        for message in batch:
            updates.append({"field": "when.flexibility", "user_id": message["user_id"],
                            "value": None, "source_message_id": message["id"]})
        return updates, {"latency_ms": 2, "prompt_tokens": 30, "completion_tokens": 10}, {}


def wait_for(engine):
    for _ in range(100):
        state = engine.snapshot()
        if not state["processing"] and not state["queued"]:
            return state
        time.sleep(0.01)
    raise AssertionError("Listener did not finish")


def test_topic_requirements_and_explicit_flexible():
    template = new_template("Dinner", "Dining", "Austin")
    assert len(missing_fields(template)) == 1 and "availability from someone going" in missing_fields(template)[0]
    for user_id in ("u1", "u2", "u3", "u4"):
        template["when"]["flexibility"][user_id] = None
    assert missing_fields(template) == []
    # topic fields are optional: they never block confirmation
    for topic in ("Travel", "Entertainment"):
        assert not any(f in missing_fields(new_template("T", topic, "Austin")) for f in ("trip_type", "activity_type"))


def test_loose_topic_field_names_and_values_are_normalised():
    template = new_template("Trip", "Travel", "Austin")
    message = {"id": "m1", "user_id": "u1", "text": "we'll fly"}
    result, decisions = apply_updates(template, [{"field": "transportation", "user_id": None, "value": "Flights",
                                                  "source_message_id": "m1"}], [message])
    assert decisions[0]["accepted"] and result["cluster"]["trip_type"] == "flight"


def test_agreed_time_unblocks_a_plan_with_silent_members():
    template = new_template("Dinner", "Dining", "Austin")
    message = {"id": "m1", "user_id": "u1", "text": "ok sat 7:30 then"}
    result, decisions = apply_updates(template, [{"field": "when.agreed", "user_id": None,
                                                  "value": {"label": "Saturday 7:30pm", "date": "2026-10-31"},
                                                  "source_message_id": "m1"}], [message])
    assert decisions[0]["accepted"] and missing_fields(result) == []
    assert result["when"]["agreed"] == {"label": "Saturday 7:30pm", "date": "2026-10-31"}


def test_agreed_date_must_match_its_weekday_and_exist():
    template = new_template("Brunch", "Dining", "Austin")
    message = {"id": "m1", "user_id": "u1", "text": "sunday the 9th"}
    for date in ("2026-11-09", "2026-02-30"):  # a Monday, and a day that does not exist
        result, _ = apply_updates(template, [{"field": "when.agreed", "user_id": None, "source_message_id": "m1",
                                              "value": {"label": "Sunday 1:30pm", "date": date}}], [message])
        assert result["when"]["agreed"] == {"label": "Sunday 1:30pm", "date": None}


def test_availability_windows_are_deduplicated_and_cluster_prefix_is_accepted():
    template = new_template("Trip", "Travel", "Austin")
    message = {"id": "m1", "user_id": "u1", "text": "bus, friday"}
    result, decisions = apply_updates(template, [
        {"field": "when.flexibility", "user_id": "u1", "source_message_id": "m1",
         "value": [{"label": "Friday 7pm"}, {"label": "friday 7pm"}, {"label": "Saturday"}]},
        {"field": "cluster.trip_type", "user_id": None, "value": "bus", "source_message_id": "m1"},
    ], [message])
    assert all(d["accepted"] for d in decisions)
    assert result["when"]["flexibility"]["u1"] == [{"label": "Friday 7pm"}, {"label": "Saturday"}]
    assert result["cluster"]["trip_type"] == "bus"


def test_declined_and_inactive_members_do_not_block_the_plan():
    from scripts.listening_lab.contracts import effective_attendance
    template = new_template("Concert", "Entertainment", "Austin")
    template["spoke"] = ["u1", "u2", "u3"]  # Sam (u4) has not said anything
    msgs = [{"id": "m1", "user_id": "u1"}, {"id": "m2", "user_id": "u2"}, {"id": "m3", "user_id": "u3"}]
    result, decisions = apply_updates(template, [
        {"field": "when.flexibility", "user_id": "u1", "value": [{"label": "Saturday"}], "source_message_id": "m1"},
        {"field": "when.flexibility", "user_id": "u2", "value": [{"label": "Saturday"}], "source_message_id": "m2"},
        {"field": "attendance", "user_id": "u3", "value": {"status": "not_going"}, "source_message_id": "m3"},
    ], msgs)
    assert all(d["accepted"] for d in decisions)
    eff = effective_attendance(result)
    assert eff["u3"]["status"] == "not_going" and eff["u4"]["status"] == "conditional" and eff["u1"]["status"] == "going"
    assert missing_fields(result) == []  # Alex declined, Sam is conditional: neither holds the plan up


def test_a_decline_replaces_earlier_availability_and_empty_availability_is_rejected():
    template = new_template("Concert", "Entertainment", "Austin")
    template["when"]["flexibility"]["u2"] = [{"label": "next Saturday"}]
    msg = [{"id": "m1", "user_id": "u2"}]
    result, decisions = apply_updates(template, [
        {"field": "when.flexibility", "user_id": "u2", "value": [], "source_message_id": "m1"},
        {"field": "attendance", "user_id": "u2", "value": {"status": "not_going"}, "source_message_id": "m1"},
    ], msg)
    assert [d["accepted"] for d in decisions] == [False, True]
    assert "u2" not in result["when"]["flexibility"]


def test_voting_counts_only_people_who_have_not_declined():
    engine = ListeningEngine(muse=FakeMuse(), debounce_seconds=0.02)
    engine.start("Concert", "Entertainment", "Austin")
    for user_id in ("u1", "u2", "u3", "u4"):
        engine.add_message(user_id, "flexible")
    wait_for(engine)
    engine.template["attendance"]["u3"] = {"status": "not_going", "condition": None}
    poll = engine.snapshot()["poll"]
    assert poll["total"] == 3 and poll["needed"] == 2 and "u3" not in poll["voters"]
    with pytest.raises(ValueError, match="can't go"):
        engine.vote("u3", True)
    engine.vote("u1", True)
    assert engine.vote("u2", True)["confirmed"]  # 2 of the 3 who are going


def test_burst_is_one_call_and_confirmation_waits_for_all_people():
    fake = FakeMuse()
    engine = ListeningEngine(muse=fake, debounce_seconds=0.02)
    engine.start("Dinner", "Dining", "Austin")
    for user_id in ("u1", "u2", "u3", "u4"):
        engine.add_message(user_id, "I am flexible")
    state = wait_for(engine)
    assert len(fake.calls) == 1
    assert state["ready"] and state["metrics"]["calls"] == 2  # one listen + one final prediction
    assert engine.confirm()["confirmed"]


def test_rejects_cross_person_and_private_model_updates():
    template = new_template("Dinner", "Dining", "Austin")
    message = {"id": "m1", "user_id": "u1", "text": "I'm free Friday"}
    updates = [
        {"field": "when.flexibility", "user_id": "u2", "value": None, "source_message_id": "m1"},
        {"field": "when.flexibility", "user_id": "u1", "value": [{"label": "Friday"}], "source_message_id": "m1"},
    ]
    result, decisions = apply_updates(template, updates, [message])
    assert [item["accepted"] for item in decisions] == [False, True]
    assert "u2" not in result["when"]["flexibility"]



def test_destination_and_origins_are_never_taken_from_chat():
    template = new_template("Dinner", "Dining", "Austin")
    message = {"id": "m1", "user_id": "u1", "text": "lets go to cabo bobs"}
    updates = [
        {"field": "where.destination", "user_id": None, "value": "Cabo Bobs", "source_message_id": "m1"},
        {"field": "where.origins", "user_id": "u1", "value": "Austin", "source_message_id": "m1"},
        {"field": "where.destination_hint", "user_id": None, "value": "Cabo Bobs", "source_message_id": "m1"},
    ]
    result, decisions = apply_updates(template, updates, [message])
    assert [item["accepted"] for item in decisions] == [False, False, True]
    assert result["where"]["destination"] is None and result["where"]["origins"] == {}
    assert result["where"]["destination_hint"] == "Cabo Bobs"


def test_vote_confirms_at_threshold_and_resets_when_plan_changes():
    engine = ListeningEngine(muse=FakeMuse(), debounce_seconds=0.02)
    engine.start("Dinner", "Dining", "Austin")
    for user_id in ("u1", "u2", "u3", "u4"):
        engine.add_message(user_id, "I am flexible")
    wait_for(engine)
    assert engine.snapshot()["poll"]["open"]
    engine.vote("u1", True)
    assert not engine.snapshot()["confirmed"]
    engine.template["where"]["search_area"] = "Dallas"
    engine._reset_votes_if_changed_locked({**engine.template, "where": {**engine.template["where"], "search_area": "Austin"}})
    assert engine.snapshot()["poll"]["yes"] == 0
    engine.vote("u1", True)
    assert engine.vote("u2", True)["confirmed"]  # 50% of 4 people = 2 yes votes


def test_budget_is_a_public_per_person_number():
    template = new_template("Dinner", "Dining", "Austin")
    message = {"id": "m1", "user_id": "u1", "text": "i can do 40"}
    updates = [
        {"field": "budget", "user_id": "u1", "value": 40, "source_message_id": "m1"},
        {"field": "budget", "user_id": "u1", "value": "lots", "source_message_id": "m1"},
    ]
    result, decisions = apply_updates(template, updates, [message])
    assert [item["accepted"] for item in decisions] == [True, False]
    assert result["budget"] == {"u1": 40}


def test_prediction_fills_only_empty_topic_fields_and_is_labelled():
    class Predicting(FakeMuse):
        def predict(self, template, notes, recent, empty):
            return [{"field": "cuisine", "value": ["Mexican"]}, {"field": "meal_type", "value": "dinner"}], {}

    engine = ListeningEngine(muse=Predicting(), debounce_seconds=0.02)
    engine.start("Dinner", "Dining", "Austin")
    engine.template["cluster"]["meal_type"] = "lunch"
    for user_id in ("u1", "u2", "u3", "u4"):
        engine.add_message(user_id, "I am flexible")
    state = wait_for(engine)
    assert state["template"]["cluster"] == {"meal_type": "lunch", "cuisine": ["Mexican"]}
    assert state["template"]["sources"]["cuisine:group"] == "predicted"
    assert state["poll"]["open"]


def test_vote_requires_a_complete_plan():
    engine = ListeningEngine(muse=FakeMuse())
    engine.start("Dinner", "Dining", "Austin")
    with pytest.raises(ValueError, match="Voting opens"):
        engine.vote("u1", True)


def test_custom_category_needs_a_name_and_has_an_event_type_field():
    with pytest.raises(ValueError, match="Name your category"):
        new_template("Night", "Custom", "Austin")
    with pytest.raises(ValueError, match="Name your category"):
        new_template("Night", "Custom", "Austin", custom_label="<script>")
    template = new_template("Night in", "Custom", "Austin", custom_label="Game night")
    assert template["custom_label"] == "Game night" and new_template("T", "Dining", "x")["custom_label"] is None
    result, decisions = apply_updates(template, [{"field": "event", "user_id": None, "value": "Board Games",
                                                  "source_message_id": "m1"}], [{"id": "m1", "user_id": "u1"}])
    assert decisions[0]["accepted"] and result["cluster"]["event_type"] == "board games"
    assert missing_fields(template) == missing_fields(new_template("T", "Dining", "Austin"))  # custom never adds requirements


def test_category_photos_are_looked_up_once_and_cached(tmp_path, monkeypatch):
    from scripts.listening_lab import serp
    calls = []
    monkeypatch.setattr(serp, "CACHE", tmp_path / "images.json")
    monkeypatch.setattr(serp, "configured", lambda: True)
    monkeypatch.setattr(serp, "_fetch", lambda q: calls.append(q) or {"url": "https://x/y.jpg", "title": "t", "source": "s"})
    real = serp.REAL_CATEGORY_IMAGE
    assert real("  Game   Night ") == real("game night")
    assert calls == ["game night"] and real("ab") is None  # too short: no request


def test_start_attaches_a_photo_and_custom_label(monkeypatch):
    from scripts.listening_lab import serp
    monkeypatch.setattr(serp, "category_image", lambda q: {"url": "https://x/y.jpg", "title": "", "source": "s"})
    engine = ListeningEngine(muse=FakeMuse())
    state = engine.start("Night in", "Custom", "Austin", custom_label="Game night")
    assert state["template"]["custom_label"] == "Game night" and state["template"]["category_image"]["source"] == "s"


# ---- Paying for the confirmed plan (Capital One Nessie, faked here: no network) ----

def confirmed_engine(monkeypatch, yes=("u1", "u2", "u3")):
    from scripts.listening_lab import nessie
    transfers = []
    monkeypatch.setattr(nessie, "accounts", lambda users: {u["id"]: f"acct-{u['id']}" for u in users})
    monkeypatch.setattr(nessie, "transfer", lambda src, dst, amount, desc: transfers.append((src, dst, amount)) or {"id": f"t{len(transfers)}", "status": "pending"})
    engine = ListeningEngine(FakeMuse())
    engine.template = new_template("Dinner", "Dining", "Austin")  # initiator u1
    engine.votes = {uid: True for uid in yes} | {"u4": False}
    engine.confirmed = True
    return engine, transfers


def test_split_needs_a_confirmed_plan_and_the_initiator(monkeypatch):
    engine, _ = confirmed_engine(monkeypatch)
    with pytest.raises(ValueError, match="Only the person who started"):
        engine.set_split("u2", 90)
    engine.confirmed = False
    with pytest.raises(ValueError, match="Confirm the plan"):
        engine.set_split("u1", 90)


def test_split_is_even_between_yes_voters_and_the_initiator(monkeypatch):
    engine, _ = confirmed_engine(monkeypatch)
    split = engine.set_split("u1", 100)["split"]
    assert split["payee"] == "u1" and split["total_cents"] == 10000
    assert split["shares"] == {"u2": 3300, "u3": 3300}  # whole dollars; u1 absorbs the extra $1; u4 voted no


def test_pay_sends_one_transfer_to_the_initiator(monkeypatch):
    engine, transfers = confirmed_engine(monkeypatch)
    engine.set_split("u1", 90)
    state = engine.pay("u2")
    assert transfers == [("acct-u2", "acct-u1", 30.0)]
    assert state["split"]["paid"]["u2"]["id"] == "t1"
    with pytest.raises(ValueError, match="already paid"):
        engine.pay("u2")
    with pytest.raises(ValueError, match="doesn't owe"):
        engine.pay("u4")
    with pytest.raises(ValueError, match="Payments have started"):
        engine.set_split("u1", 120)


def test_new_session_clears_the_split(monkeypatch):
    engine, _ = confirmed_engine(monkeypatch)
    engine.set_split("u1", 90)
    assert engine.start("Movie night", "Entertainment", "Austin")["split"] is None


def test_balance_reflects_payments_even_if_the_sandbox_balance_does_not_move(monkeypatch):
    from scripts.listening_lab import nessie
    engine, _ = confirmed_engine(monkeypatch)
    monkeypatch.setattr(nessie, "balance", lambda account: 1500.0)
    engine.set_split("u1", 90)
    assert engine.balance("u2")["balance"] == 1500.0
    engine.pay("u2")
    assert engine.balance("u2")["balance"] == 1470.0
    assert engine.balance("u1")["balance"] == 1530.0


def test_payment_is_a_withdrawal_plus_a_deposit_and_adapts_to_the_schema(monkeypatch):
    from scripts.listening_lab import nessie
    calls = []

    def fake_call(method, path, body=None):
        calls.append((path, dict(body or {})))
        if "medium" in (body or {}):
            raise RuntimeError('Nessie returned 400: "medium extra fields not permitted"')
        return {"objectCreated": {"_id": f"id{len(calls)}", "status": body["status"]}}

    monkeypatch.setattr(nessie, "_call", fake_call)
    record = nessie.transfer("A", "B", 33.4, "InstaPlan: Dinner")
    paths = [path for path, body in calls if "medium" not in body]
    assert paths == ["/accounts/A/withdrawals", "/accounts/B/deposits"]
    assert all(body["amount"] == 33 for path, body in calls)
    assert record["status"] == "completed" and record["id"] and record["deposit_id"]
