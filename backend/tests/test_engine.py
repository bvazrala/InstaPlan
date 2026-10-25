"""Offline integration regressions for the live planning engine."""
import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from time import sleep

import httpx
import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.config import Settings
from app.db import engine
from app.integrations.cache import cache_key, cached
from app.integrations.serpapi_client import SerpApiClient, TravelDataError, RequestLimitError
from app.integrations.serpapi_normalized import FlightOptionStage1, FlightOptionComplete, FlightLeg, build_round_trip
from app.logic.candidates import build_group_candidates
from app.logic.fit import evaluate_fit, check_constraint
from app.logic.generation import start_run, public_status, finish_state
from app.logic.option_service import evaluate_options
from app.logic.planning import PlanningInput, Constraint, Preference, PrivateRequirements
from app.logic.ranking import rank_candidates
from app.models import ApiCache, Fact, OptionGeneration, PrivatePrefs, Trip, TripOption, TripVote
from app.privacy.crypto import encrypt_json
from app.pipeline import generate_options
from tests.conftest import as_user
from tests.test_logic import group_trip


def candidate(group_trip):
    members, flights, lodging = group_trip
    return build_group_candidates(members, flights, [lodging], checkin="2026-11-05", checkout="2026-11-09",
                                  destination_city="New York City")[0]


def settings(**updates):
    return Settings(serpapi_key="key-never-store", **updates)


def test_cache_expiry_empty_results_and_credentials(client):
    clock = [datetime(2030, 1, 1, tzinfo=UTC)]
    calls = []
    params = {"engine": "google_flights", "api_key": "secret"}
    def fetch():
        calls.append(1)
        return {"best_flights": [{"price": len(calls)}], "search_parameters": params,
                "search_metadata": {"json_endpoint": "https://host/?api_key=secret"}}
    with Session(engine) as session:
        first = cached(session, "serpapi", params, fetch, now=lambda: clock[0], ttl_seconds=900)
        assert "secret" not in json.dumps(first)
        assert cache_key("serpapi", params) == cache_key("serpapi", {"engine": "google_flights", "api_key": "different"})
        assert cache_key("serpapi", params) != cache_key("serpapi", {"engine": "google_hotels"})
        cached(session, "serpapi", params, fetch, now=lambda: clock[0])
        assert len(calls) == 1
        clock[0] += timedelta(seconds=901)
        cached(session, "serpapi", params, fetch, now=lambda: clock[0])
        assert len(calls) == 2
        empty_calls = []
        def empty():
            empty_calls.append(1)
            return {"other_flights": []}
        cached(session, "serpapi", {"empty": 1}, empty, now=lambda: clock[0])
        clock[0] += timedelta(seconds=61)
        cached(session, "serpapi", {"empty": 1}, empty, now=lambda: clock[0])
        assert len(empty_calls) == 2


@pytest.mark.parametrize("mode", ["http", "malformed", "provider", "timeout"])
def test_http_failures_are_typed_redacted_and_not_cached(client, mode, caplog):
    caplog.set_level("INFO")
    def handler(request):
        if mode == "timeout":
            raise httpx.ReadTimeout("api_key=key-never-store", request=request)
        if mode == "malformed":
            return httpx.Response(200, text="not-json")
        return httpx.Response(403 if mode == "http" else 200, json={"error": "key-never-store"})
    client_ = SerpApiClient(transport=httpx.MockTransport(handler), settings=settings(), sleep_fn=lambda _: None)
    with pytest.raises(TravelDataError) as caught:
        client_.search({"engine": "google_flights"})
    assert "key-never-store" not in str(caught.value) + caplog.text
    with Session(engine) as session:
        assert not session.exec(select(ApiCache)).all()
    assert client_.requests == (3 if mode == "timeout" else 1)


def test_http_retry_and_request_limit(client):
    calls = []
    def handler(request):
        calls.append(1)
        return httpx.Response(429 if len(calls) < 3 else 200, json={"other_flights": []})
    api = SerpApiClient(transport=httpx.MockTransport(handler), settings=settings(), sleep_fn=lambda _: None)
    assert api.search({"engine": "google_flights"}) == {"other_flights": []}
    assert api.requests == 3
    api = SerpApiClient(transport=httpx.MockTransport(lambda _: httpx.Response(503)),
                        settings=settings(serpapi_request_limit=1), sleep_fn=lambda _: None)
    with pytest.raises(RequestLimitError):
        api.search({"engine": "google_hotels"})
    assert api.requests == 1


def test_concurrency_and_cache_insert_races_are_bounded(tmp_path):
    database = create_engine(f"sqlite:///{tmp_path / 'cache.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(database)
    active, maximum = 0, 0
    lock = Lock()
    def handler(request):
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        sleep(0.02)
        with lock:
            active -= 1
        return httpx.Response(200, json={"properties": [{"name": "Shared"}]})
    api = SerpApiClient(transport=httpx.MockTransport(handler), session_factory=lambda: Session(database),
                        settings=settings(serpapi_concurrency=2), sleep_fn=lambda _: None)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: api.search({"engine": "google_hotels", "q": "same"}), range(8)))
    assert all(result == results[0] for result in results)
    assert maximum <= 2
    with Session(database) as session:
        assert len(session.exec(select(ApiCache)).all()) == 1
    database.dispose()


def test_two_stage_calls_bound_returns_and_preserve_connections(client):
    calls = []
    def leg(origin, destination, number):
        return {"flight_number": number, "departure_airport": {"id": origin}, "arrival_airport": {"id": destination}, "duration": 60}
    def handler(request):
        params = dict(request.url.params)
        calls.append(params)
        if "departure_token" not in params:
            return httpx.Response(200, json={"search_parameters": params, "best_flights": [
                {"departure_token": f"out-{i}", "price": 100 + i, "total_duration": 60 + i,
                 "flights": [leg("AUS", "JFK", f"O{i}")]} for i in range(10)]})
        return httpx.Response(200, json={"other_flights": [
            {"booking_token": f"{params['departure_token']}-return-{i}", "price": 200 + i, "total_duration": 180,
             "flights": [leg("JFK", "ORD", "R1"), leg("ORD", "AUS", "R2")]} for i in range(6)]})
    api = SerpApiClient(transport=httpx.MockTransport(handler), settings=settings())
    trips = api.round_trips("AUS", "JFK", "2030-11-05", "2030-11-09")
    assert len(calls) == 3 and len(trips) == 6
    assert all(flight.complete and len(flight.return_flight) == 2 and flight.inbound_duration_min == 180 for flight in trips)


@pytest.mark.parametrize("constraint,expected", [
    (Constraint(kind="exclude_destination", value="New York City"), "violated"),
    (Constraint(kind="flight_only"), "verified"),
    (Constraint(kind="max_duration", limit=200), "violated"),
    (Constraint(kind="max_duration", limit=400), "verified"),
    (Constraint(kind="max_stops", limit=0), "verified"),
    (Constraint(kind="amenity", value="wheelchair accessible"), "unknown"),
    (Constraint(kind="available_dates", start=date(2026, 11, 5), end=date(2026, 11, 9)), "verified"),
    (Constraint(kind="available_dates", start=date(2026, 11, 6), end=date(2026, 11, 9)), "violated"),
    (Constraint(kind="unsupported"), "unknown"),
])
def test_hard_constraint_evidence(group_trip, constraint, expected):
    assert check_constraint(candidate(group_trip), constraint) == expected


def test_fit_aggregate_and_unknown_categories(group_trip):
    option = candidate(group_trip)
    preferences = [Preference(member_id="alice", category="Destination", value="New York City", score=2)]
    fit = evaluate_fit(option, preferences)
    assert 0 <= fit.fit <= 100 and fit.cats["Destination"] > 50
    assert fit.cats["Food"] is None and fit.cats["Activities"] is None
    assert fit.certainty == "1 of 3 weighed in"
    assert evaluate_fit(option).fit == 50
    assert not evaluate_fit(option, constraints=[Constraint(kind="unsupported")]).pick_eligible
    group_trip[2].amenities = ["Wheelchair accessible"]
    assert evaluate_fit(candidate(group_trip), constraints=[Constraint(kind="amenity", value="wheelchair accessible")]).pick_eligible


def test_rankings_trade_cost_time_and_individual_burden(group_trip):
    option = candidate(group_trip)
    a = replace(option, id="a", group_total=Decimal(650), max_travel_duration_min=600,
                participants=(replace(option.participants[0], estimated_subtotal=Decimal(350)),
                              replace(option.participants[1], estimated_subtotal=Decimal(150)),
                              replace(option.participants[2], estimated_subtotal=Decimal(150))))
    b = replace(option, id="b", max_travel_duration_min=120)
    assert rank_candidates([b, a], "cheapest")[0].id == "a"
    assert rank_candidates([a, b], "fastest")[0].id == "b"
    assert rank_candidates([a, b], "balanced", weight=0)[0].id == "b"
    assert rank_candidates([a, b], "balanced", weight=1)[0].id == "a"
    assert rank_candidates([a, b], "fairest", ceilings={"alice": Decimal(400), "bob": Decimal(1000), "cara": Decimal(1000)})[0].id == "b"
    assert rank_candidates([b, a], "fairest")[0].id == "a"
    assert rank_candidates([a, b], ceilings={"alice": Decimal(0)}) == []
    unknown = replace(a, id="unknown", group_total=None, max_travel_duration_min=None)
    assert rank_candidates([unknown, b], "balanced")[-1].id == "unknown"
    assert rank_candidates([replace(b, id="z"), b], "fastest")[0].id == "b"


def save_private(session, trip_id, uid, **prefs):
    session.merge(PrivatePrefs(trip_id=trip_id, user_id=uid, data_encrypted=encrypt_json(prefs)))
    session.commit()


def test_private_service_filters_without_exposing_values(world, group_trip, caplog):
    option = candidate(group_trip)
    with Session(engine) as session:
        save_private(session, world["trip_id"], "alice", budget_cap=120, no_gos="SENSITIVE-RESTRICTION")
        assert evaluate_options(session, world["trip_id"], [option], PlanningInput()) == []
        # Two participants: private budgets must not influence the output.
        two = replace(option, participants=option.participants[:2])
        safe = evaluate_options(session, world["trip_id"], [two], PlanningInput())
        assert safe and not safe[0].pick_eligible  # hard text remains unverified
        serialized = safe[0].model_dump_json() + caplog.text
        assert "SENSITIVE" not in serialized and "120" not in safe[0].model_dump_json()


def test_private_model_requests_are_one_member_and_omit_budgets(world, group_trip, monkeypatch):
    from app.integrations import muse_private
    import app.logic.option_service as service
    monkeypatch.setattr(service, "get_settings", lambda: SimpleNamespace(muse_api_key="test"))
    requests = []
    def ask(system, user):
        payload = json.loads(user)
        requests.append(payload)
        return {"constraints": [{"kind": "amenity", "value": "wheelchair accessible"}]}
    monkeypatch.setattr(muse_private, "ask_json", ask)
    with Session(engine) as session:
        save_private(session, world["trip_id"], "alice", budget_cap=1000, accessibility=["ALICE-ONLY"])
        save_private(session, world["trip_id"], "bob", budget_cap=2000, accessibility=["BOB-ONLY"])
        results = evaluate_options(session, world["trip_id"], [candidate(group_trip)], PlanningInput())
    assert len(requests) == 2
    assert all("budget" not in json.dumps(payload) and "1000" not in json.dumps(payload) and "2000" not in json.dumps(payload) for payload in requests)
    assert all(not ("ALICE-ONLY" in json.dumps(payload) and "BOB-ONLY" in json.dumps(payload)) for payload in requests)
    assert "ONLY" not in results[0].model_dump_json()


def seed_plan(session, world, group_trip):
    start = date.today() + timedelta(days=30)
    end = start + timedelta(days=4)
    for flights in group_trip[1].values():
        for flight in flights:
            flight.outbound_flight[0].scheduled_arrival = f"{start} 12:00"
            flight.return_flight[0].scheduled_departure = f"{end} 12:00"
    session.add(Fact(trip_id=world["trip_id"], field="Destination", value="New York City"))
    session.add(Fact(trip_id=world["trip_id"], field="Dates", value=f"{start}..{end}"))
    for member in group_trip[0]:
        session.add(Fact(trip_id=world["trip_id"], member_id=member.user_id, field="From", value=member.origin_airport))
    session.commit()


class FakeTravel:
    def __init__(self, group_trip, *, failed=False, mutate=None):
        self.group_trip = group_trip
        self.requests = 0
        self.settings = SimpleNamespace(serpapi_request_limit=100)
        self.failed, self.mutate = failed, mutate
    def collect(self, origins, destination, checkin, checkout, adults):
        if self.mutate:
            self.mutate()
        if self.failed:
            return {}, [], True
        assert len(set(origins)) == 3 and adults == 3
        return {member.origin_airport: self.group_trip[1][member.user_id] for member in self.group_trip[0]}, [self.group_trip[2]], False


def test_generation_pipeline_publishes_exact_options_and_status(world, group_trip):
    with Session(engine) as session:
        seed_plan(session, world, group_trip)
        trip = session.get(Trip, world["trip_id"])
        assert generate_options(session, trip, client=FakeTravel(group_trip))
        rows = session.exec(select(TripOption)).all()
        assert len(rows) == 1 and rows[0].data["group_total"] == 700.01
        assert sum(p["subtotal"] for p in rows[0].data["people"]) == 700.01
        assert rows[0].data["priced_at"].startswith("2026-10-25")
        assert session.get(Trip, trip.id).stage == "options"
        assert public_status(session.get(OptionGeneration, trip.id)).status == "ready"
        old_ids = [row.id for row in rows]
        assert not generate_options(session, trip, client=FakeTravel(group_trip, failed=True))
        assert [row.id for row in session.exec(select(TripOption)).all()] == old_ids
        assert public_status(session.get(OptionGeneration, trip.id)).status == "failed"


def test_generation_needs_input_makes_no_travel_calls(world):
    with Session(engine) as session:
        trip = session.get(Trip, world["trip_id"])
        class NoTravel:
            def collect(self, *args):
                pytest.fail("Unresolved inputs must not incur provider calls")
        assert not generate_options(session, trip, client=NoTravel())
        result = public_status(session.get(OptionGeneration, trip.id))
        assert result.status == "needs_input" and "destinations" in result.missing


def test_generation_stale_revision_cannot_publish(world, group_trip):
    with Session(engine) as session:
        seed_plan(session, world, group_trip)
        def mutate():
            session.add(Fact(trip_id=world["trip_id"], field="Destination", value="Boston"))
            session.commit()
        assert not generate_options(session, session.get(Trip, world["trip_id"]), client=FakeTravel(group_trip, mutate=mutate))
        assert not session.exec(select(TripOption)).all()
        assert session.get(OptionGeneration, world["trip_id"]).status == "failed"


def test_generation_duplicate_and_stale_worker_protection(world):
    with Session(engine) as session:
        trip = session.get(Trip, world["trip_id"])
        first, started = start_run(session, trip)
        first_id = first.run_id
        assert started
        second, started = start_run(session, trip)
        assert not started and second.run_id == first_id
        first.started_at = datetime.now(UTC) - timedelta(minutes=6)
        session.add(first)
        session.commit()
        assert public_status(first).status == "failed"
        new, started = start_run(session, trip)
        assert started and new.run_id != first_id
        assert not finish_state(session, trip.id, first_id, "ready", {})
        assert session.get(OptionGeneration, trip.id).run_id == new.run_id


def test_live_routes_and_server_capacity_ack(client, world, group_trip, monkeypatch):
    import app.routers.options as routes
    group_trip[2].max_occupancy = None
    with Session(engine) as session:
        seed_plan(session, world, group_trip)
    monkeypatch.setattr(routes, "generate_options", lambda session, trip, **kwargs:
                        generate_options(session, trip, client=FakeTravel(group_trip), **kwargs))
    tid = world["trip_id"]
    assert client.get(f"/chats/{world['chat_id']}/trips/active", headers=as_user("bob")).json()["id"] == tid
    assert client.post(f"/trips/{tid}/options/generate", headers=as_user("dan")).status_code == 404
    assert client.get(f"/trips/{tid}/options/status", headers=as_user("dan")).status_code == 404
    response = client.post(f"/trips/{tid}/options/generate", headers=as_user("alice"))
    assert response.status_code == 202
    status = client.get(f"/trips/{tid}/options/status", headers=as_user("bob")).json()
    assert status["status"] == "ready"
    options = client.get(f"/trips/{tid}/options", headers=as_user("bob")).json()
    assert options[0]["capacityAckRequired"] and options[0]["pickEligible"]
    option_id = options[0]["id"]
    assert client.post(f"/trips/{tid}/pick", headers=as_user("alice"), json={"optionId": option_id}).status_code == 409
    picked = client.post(f"/trips/{tid}/pick", headers=as_user("alice"), json={"optionId": option_id, "acknowledgeCapacity": True})
    assert picked.status_code == 200 and picked.json()["pickedOptionId"] == option_id
    assert client.post(f"/trips/{tid}/options/generate", headers=as_user("alice")).status_code == 409


def test_server_rejects_unverified_hard_requirement(client, world, group_trip, monkeypatch):
    import app.routers.options as routes
    with Session(engine) as session:
        seed_plan(session, world, group_trip)
        save_private(session, world["trip_id"], "alice", accessibility=["PRIVATE-ACCESS-REQUIREMENT"])
    monkeypatch.setattr(routes, "generate_options", lambda session, trip, **kwargs:
                        generate_options(session, trip, client=FakeTravel(group_trip), **kwargs))
    tid = world["trip_id"]
    client.post(f"/trips/{tid}/options/generate", headers=as_user("alice"))
    options = client.get(f"/trips/{tid}/options", headers=as_user("bob"))
    assert "PRIVATE-ACCESS" not in options.text
    option = options.json()[0]
    assert not option["pickEligible"]
    assert client.post(f"/trips/{tid}/pick", headers=as_user("bob"), json={"optionId": option["id"], "acknowledgeCapacity": True}).status_code == 409



def test_private_budget_revision_after_failed_refresh_cannot_pick_old_results(client, world, group_trip, monkeypatch):
    import app.routers.options as routes
    with Session(engine) as session:
        seed_plan(session, world, group_trip)
        assert generate_options(session, session.get(Trip, world["trip_id"]), client=FakeTravel(group_trip))
        old_id = session.exec(select(TripOption.id)).one()
        save_private(session, world["trip_id"], "alice", budget_cap=500)
        assert not generate_options(session, session.get(Trip, world["trip_id"]), client=FakeTravel(group_trip, failed=True))
    response = client.post(f"/trips/{world['trip_id']}/pick", headers=as_user("bob"), json={"optionId": old_id})
    assert response.status_code == 409
    assert "Generate options again" in response.text
    assert "500" not in response.text


def test_generation_successful_empty_is_ready_and_declines_are_excluded(world, group_trip):
    with Session(engine) as session:
        seed_plan(session, world, group_trip)
        session.add(TripVote(trip_id=world["trip_id"], user_id="cara", going=False))
        session.commit()
        class EmptyTravel(FakeTravel):
            def collect(self, origins, destination, checkin, checkout, adults):
                assert adults == 2 and "LAX" not in origins
                return {}, [], False
        assert generate_options(session, session.get(Trip, world["trip_id"]), client=EmptyTravel(group_trip))
        status = public_status(session.get(OptionGeneration, world["trip_id"]))
        assert status.status == "ready" and status.option_count == 0 and not status.partial


def test_confirmed_public_inputs_are_retained_without_overriding_constraints(world, group_trip):
    from app.logic.planning import Destination
    with Session(engine) as session:
        seed_plan(session, world, group_trip)
        trip = session.get(Trip, world["trip_id"])
        run, started = start_run(session, trip, PlanningInput(destinations=[Destination(name="NYC confirmed", airports=["JFK"]) ]))
        assert started
        assert generate_options(session, trip, run_id=run.run_id, client=FakeTravel(group_trip))
        next_run, started = start_run(session, trip)
        assert started and next_run.result["inputs"]["destinations"][0]["name"] == "NYC confirmed"


def test_option_ids_are_namespaced_per_trip(world, group_trip):
    with Session(engine) as session:
        one = evaluate_options(session, "trip-one", [candidate(group_trip)], PlanningInput())[0]
        two = evaluate_options(session, "trip-two", [candidate(group_trip)], PlanningInput())[0]
    assert one.id != two.id


def test_partial_results_preserve_safe_options(world, group_trip):
    with Session(engine) as session:
        seed_plan(session, world, group_trip)
        class PartialTravel(FakeTravel):
            def collect(self, *args):
                flights, properties, _ = super().collect(*args)
                return flights, properties, True
        assert generate_options(session, session.get(Trip, world["trip_id"]), client=PartialTravel(group_trip))
        assert public_status(session.get(OptionGeneration, world["trip_id"])).partial
        assert len(session.exec(select(TripOption)).all()) == 1


def test_public_resolution_never_receives_private_data(world, group_trip, monkeypatch):
    import app.pipeline as pipeline
    from app.logic.planning import known_inputs
    seen = []
    monkeypatch.setattr(pipeline, "get_settings", lambda: SimpleNamespace(muse_api_key="configured"))
    def resolve(ctx):
        serialized = ctx.model_dump_json()
        assert "PRIVATE-MARKER" not in serialized and "budget_cap" not in serialized
        seen.append(serialized)
        return known_inputs(ctx)
    monkeypatch.setattr(pipeline.muse_group, "resolve_planning", resolve)
    with Session(engine) as session:
        seed_plan(session, world, group_trip)
        save_private(session, world["trip_id"], "alice", no_gos="PRIVATE-MARKER")
        generate_options(session, session.get(Trip, world["trip_id"]), client=FakeTravel(group_trip))
    assert len(seen) == 1


def test_failed_worker_does_not_log_private_exception_values(world, caplog, monkeypatch):
    import app.routers.options as routes
    with Session(engine) as session:
        run, _ = start_run(session, session.get(Trip, world["trip_id"]))
        run_id = run.run_id
    def fail(*args, **kwargs):
        raise ValueError("PRIVATE-EXCEPTION-CONTENT")
    monkeypatch.setattr(routes, "generate_options", fail)
    assert routes._worker(world["trip_id"], run_id) is None
    assert "PRIVATE-EXCEPTION" not in caplog.text
    with Session(engine) as session:
        assert "PRIVATE-EXCEPTION" not in public_status(session.get(OptionGeneration, world["trip_id"])).model_dump_json()


def test_availability_covers_overnight_departure_from_origin(group_trip):
    value = candidate(group_trip)
    flight = value.participants[0].flight
    flight.outbound_flight[0].scheduled_departure = "2026-11-04 23:00"
    rule = Constraint(kind="available_dates", member_id="alice", start=date(2026, 11, 5), end=date(2026, 11, 9))
    assert check_constraint(value, rule) == "violated"



def test_stage_endpoint_cannot_bypass_pick_validation(client, world):
    with Session(engine) as session:
        trip = session.get(Trip, world["trip_id"])
        trip.stage = "options"
        session.add(trip)
        session.commit()
    response = client.post(f"/trips/{world['trip_id']}/stage", json={"stage": "picked"}, headers=as_user("alice"))
    assert response.status_code == 409


def test_exact_public_normalization_preserves_unresolved_hard_limits():
    from app.logic.planning import known_inputs
    from app.privacy.context import GroupContext, GroupFact, GroupMember
    ctx = GroupContext(trip_id="trip", members=(GroupMember(id="a", name="A", home_airport="AUS"),), recent_messages=(),
        facts=(GroupFact(id="f", field="From", value="somewhere near my parents", by="a"),
               GroupFact(id="g", field="Hard requirement", value="Must be near a hospital", by="a")))
    resolved = known_inputs(ctx)
    assert "origin:a" in resolved.missing(["a"])
    assert resolved.constraints[0].kind == "unsupported"
