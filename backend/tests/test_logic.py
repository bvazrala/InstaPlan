"""Unit tests for the pure logic in app/logic/."""

from datetime import UTC, datetime
from decimal import Decimal

from app.integrations.serpapi_normalized import (
    FlightLeg, FlightOptionComplete, FlightOptionStage1, FlightStatus,
    PriceDict, Property, RoundTripFlight, build_round_trip,
)
from app.logic.candidates import (
    FeasibilityStatus, LodgingCompliance, Participant, build_group_candidates,
)

import pytest

from app.logic.budget import Bill, default_reason, safe_to_spend
from app.logic.fit import certainty, fit_score
from app.logic.ranking import PricedOption, fairest, group_total
from app.logic.settle import equal_split, net_balances, suggest_transfers
from app.logic.trip_state import InvalidTransition, Stage, advance, has_majority


@pytest.mark.parametrize("scores, expected", [
    ([1, 1, 1, 1, 1], 75),      # all like it
    ([2, 2, 2, 2, -1], 73),     # four love it, one dislikes it
    ([0, 0, 0, 0, 0], 50),      # no opinions yet
    ([1, 1, 1, 1, -2], 48),     # one strong objection pulls it to yellow
    ([-1, -1, -1, 1, 1], 41),   # three dislike, two like
])
def test_fit_score_matches_requirements_table(scores, expected):
    assert fit_score(scores) == expected


def test_certainty_counts_who_weighed_in():
    assert certainty([1, 0, -2], 5) == "2 of 5 weighed in"


def _option(id_, travel, lodging=200.0, daily=80.0, nights=3):
    return PricedOption(id=id_, travel_cost=travel, travel_hours={m: 4.0 for m in travel},
                        lodging_share=lodging, daily=daily, nights=nights)


def test_fairest_drops_options_over_anyones_ceiling_and_ranks_the_rest():
    travel = {"a": 300.0, "b": 300.0, "c": 300.0}
    cheap, mid, pricey = _option("cheap", travel, 100), _option("mid", travel, 200), _option("pricey", travel, 600)
    kept, ranks = fairest([pricey, mid, cheap], {"a": 1000, "b": 800, "c": 2000})
    assert [o.id for o in kept] == ["mid", "cheap"]  # pricey (1140) exceeds b's 800
    assert ranks == {"cheap": 1, "mid": 2}


def test_group_total_sums_every_member():
    assert group_total(_option("x", {"a": 100.0, "b": 50.0}, lodging=10, daily=0)) == 170


def test_safe_to_spend_leaves_bills_and_cushion():
    c = safe_to_spend(1900, [Bill("Rent", 890)])
    assert c.amount == 720  # 1900 − 890 − 285 cushion, rounded down to $10
    assert "Rent" in default_reason(c)


def test_equal_split_sums_to_total():
    split = equal_split(1000, ["a", "b", "c"])
    assert sum(split.values()) == 1000 and max(split.values()) - min(split.values()) <= 1


def test_suggested_transfers_settle_everyone():
    net = net_balances([("maya", 86000, equal_split(86000, ["you", "maya", "alex", "sam"]))])
    transfers = suggest_transfers(net)
    assert {t.from_id for t in transfers} == {"you", "alex", "sam"}
    assert all(t.to_id == "maya" and t.cents == 21500 for t in transfers)


def test_stage_moves():
    assert advance("collecting", "voting") == Stage.VOTING
    with pytest.raises(InvalidTransition):
        advance("collecting", "options")
    assert has_majority(3, 4) and not has_majority(2, 4)


# Group candidates use only synthetic normalized provider data: no HTTP or database.



@pytest.fixture()
def group_trip():
    members = [Participant("alice", "AUS"), Participant("bob", "BOS"), Participant("cara", "LAX")]
    timestamp = datetime(2026, 10, 25, 12, tzinfo=UTC)
    flights = {}
    for index, member in enumerate(members, 1):
        flights[member.user_id] = [RoundTripFlight(
            source={"engine": "synthetic", "quote": member.user_id},
            outbound_flight=[FlightLeg(
                flight_number=f"OUT{index}", departure_airport_id=member.origin_airport,
                arrival_airport_id="JFK", scheduled_departure="2026-11-05 06:00",
                scheduled_arrival="2026-11-05 12:00", duration_min=index * 60,
            )],
            return_flight=[FlightLeg(
                flight_number=f"RET{index}", departure_airport_id="JFK",
                arrival_airport_id=member.origin_airport, scheduled_departure="2026-11-09 12:00",
                scheduled_arrival="2026-11-09 18:00", duration_min=index * 60,
            )],
            outbound_duration_min=index * 60, inbound_duration_min=index * 60,
            total_price_usd=index * 100, currency="USD", booking_token=f"bt-{index}",
            departure_token=f"dt-{index}", origin_id=member.origin_airport, destination_id="JFK",
            retrieved_at=timestamp, complete=True,
        )]
    lodging = Property(
        source={"engine": "synthetic", "quote": "lodging"}, name="Shared apartment",
        property_token="apartment", max_occupancy=3, currency="USD",
        total_rate=PriceDict(extracted_after_taxes_fees=100.01), retrieved_at=timestamp,
    )
    return members, flights, lodging


def _group(group_trip, **kwargs):
    members, flights, lodging = group_trip
    return build_group_candidates(members, flights, [lodging], checkin="2026-11-05",
                                  checkout="2026-11-09", destination_city="New York City", **kwargs)


def test_group_costs_and_durations_are_individual_and_shared_once(group_trip):
    candidate, = _group(group_trip)
    assert [p.origin_airport for p in candidate.participants] == ["AUS", "BOS", "LAX"]
    assert [p.flight_cost for p in candidate.participants] == list(map(Decimal, [100, 200, 300]))
    assert [p.lodging_allocation for p in candidate.participants] == [Decimal("33.34"), Decimal("33.34"), Decimal("33.33")]
    assert sum(p.lodging_allocation for p in candidate.participants) == candidate.lodging_price.amount
    assert [p.estimated_subtotal for p in candidate.participants] == [Decimal("133.34"), Decimal("233.34"), Decimal("333.33")]
    assert candidate.group_total == sum(p.estimated_subtotal for p in candidate.participants) == Decimal("700.01")
    assert [p.travel_duration_min for p in candidate.participants] == [120, 240, 360]
    assert candidate.max_travel_duration_min == 360
    assert candidate.complete and candidate.feasibility == FeasibilityStatus.FEASIBLE
    assert candidate.flight_price_usd is None and candidate.total_per_person is None
    assert candidate.lodging_per_person is None  # exact allocations live on each participant
    assert candidate.participants[1].flight.source == {"engine": "synthetic", "quote": "bob"}
    assert candidate.lodging_source == {"engine": "synthetic", "quote": "lodging"}
    assert candidate.priced_at == group_trip[2].retrieved_at
    # Generation doesn't retain a mutable reference to the input itinerary.
    group_trip[1]["bob"][0].source["quote"] = "changed"
    assert candidate.participants[1].flight.source["quote"] == "bob"


def test_group_missing_flight_never_becomes_complete(group_trip):
    del group_trip[1]["bob"]
    candidate, = _group(group_trip)
    assert len(candidate.participants) == 3
    bob = candidate.participants[1]
    assert bob.flight_status == FlightStatus.MISSING
    assert bob.flight_cost is None and bob.estimated_subtotal is None
    assert bob.lodging_allocation == Decimal("33.34")
    assert candidate.group_total is None and not candidate.complete
    assert candidate.max_travel_duration_min is None
    assert candidate.feasibility == FeasibilityStatus.UNVERIFIED
    assert "flight_missing:bob" in candidate.feasibility_reasons


def test_group_all_missing_flights_still_retains_every_person(group_trip):
    group_trip[1].clear()
    candidate, = _group(group_trip)
    assert candidate.flight_status == FlightStatus.MISSING
    assert candidate.group_total is None and not candidate.complete
    assert len(candidate.participants) == 3


@pytest.mark.parametrize("capacity,status", [(None, FeasibilityStatus.UNVERIFIED), (2, FeasibilityStatus.INFEASIBLE)])
def test_group_capacity_is_never_inferred_from_reviews(group_trip, capacity, status):
    group_trip[2].max_occupancy = capacity
    group_trip[2].review_count = 1000
    candidate, = _group(group_trip)
    assert candidate.feasibility == status
    assert candidate.capacity_verified == (capacity is not None)
    assert candidate.capacity_unverified == (capacity is None)


@pytest.mark.parametrize("currency", ["EUR", None])
def test_group_currency_mismatch_or_unknown_prevents_aggregation(group_trip, currency):
    group_trip[1]["bob"][0].currency = currency
    candidate, = _group(group_trip)
    assert candidate.group_total is None and not candidate.complete
    assert candidate.participants[1].estimated_subtotal is None
    assert candidate.currency is None
    assert candidate.feasibility == (FeasibilityStatus.INFEASIBLE if currency else FeasibilityStatus.UNVERIFIED)


def test_group_lodging_unknown_currency_not_inferred(group_trip):
    group_trip[2].currency = None
    candidate, = _group(group_trip)
    assert candidate.group_total is None
    assert "lodging_currency_unknown" in candidate.feasibility_reasons


def test_group_non_usd_matching_currency_is_preserved(group_trip):
    group_trip[2].currency = "EUR"
    for flights in group_trip[1].values():
        flights[0].currency = "EUR"
    candidate, = _group(group_trip)
    assert candidate.currency == "EUR" and candidate.group_total == Decimal("700.01")
    assert candidate.flight_price_usd is None


@pytest.mark.parametrize("missing_price", [False, True])
def test_group_estimated_and_missing_lodging_prices_remain_explicit(group_trip, missing_price):
    group_trip[2].total_rate = None
    group_trip[2].rate_per_night = None if missing_price else PriceDict(extracted_before_taxes_fees=25)
    candidate, = _group(group_trip)
    assert not candidate.complete and not candidate.lodging_price.tax_inclusive
    assert candidate.lodging_price.status == (LodgingCompliance.MISSING if missing_price else LodgingCompliance.ESTIMATED)
    assert candidate.group_total == (None if missing_price else Decimal("700.00"))


@pytest.mark.parametrize("field,value,reason", [
    ("scheduled_arrival", "2026-11-06 12:00", "dates_incompatible:alice"),
    ("scheduled_arrival", None, "dates_unverified:alice"),
    ("departure_airport_id", "DFW", "origin_mismatch:alice"),
    ("arrival_airport_id", "LHR", "destination_mismatch"),
])
def test_group_date_and_route_evidence_is_explicit(group_trip, field, value, reason):
    setattr(group_trip[1]["alice"][0].outbound_flight[0], field, value)
    candidate, = _group(group_trip)
    assert reason in candidate.feasibility_reasons
    assert candidate.feasibility == (FeasibilityStatus.UNVERIFIED if value is None else FeasibilityStatus.INFEASIBLE)


def test_group_overnight_outbound_and_multiple_destination_airports(group_trip):
    flight = group_trip[1]["cara"][0]
    flight.outbound_flight[0].scheduled_departure = "2026-11-04 23:00"
    flight.outbound_flight[0].arrival_airport_id = "EWR"
    flight.return_flight[0].departure_airport_id = "EWR"
    flight.destination_id = "EWR"
    candidate, = _group(group_trip, destination_airports=["JFK", "EWR"])
    assert candidate.feasibility == FeasibilityStatus.FEASIBLE


def test_group_unknown_duration_never_uses_partial_max(group_trip):
    group_trip[1]["cara"][0].inbound_duration_min = None
    candidate, = _group(group_trip)
    assert candidate.max_travel_duration_min is None
    assert "travel_duration_unknown:cara" in candidate.feasibility_reasons


def test_group_partial_flight_preserves_reasons_without_total(group_trip):
    group_trip[1]["bob"][0].complete = False
    group_trip[1]["bob"][0].incomplete_reasons = ["no_booking_token"]
    candidate, = _group(group_trip)
    assert candidate.flight_status == FlightStatus.PARTIAL
    assert candidate.group_total is None and not candidate.complete
    assert "flight_incomplete:bob:no_booking_token" in candidate.feasibility_reasons


def test_group_deterministic_bounded_distinct_combinations(group_trip, monkeypatch):
    import app.logic.candidates as engine
    members, flights, lodging = group_trip
    for uid, choices in flights.items():
        choices[:] = [choices[0].model_copy(update={"booking_token": f"{uid}-{index}"}, deep=True) for index in range(40)]
        choices.append(choices[0].model_copy(deep=True))
    lodgings = [lodging.model_copy(update={"property_token": f"stay-{index}"}) for index in range(20)]
    calls = []
    original = engine._group_combination
    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(engine, "_group_combination", counted)
    def run():
        return engine.build_group_candidates(members, flights, lodgings, checkin="2026-11-05",
                                             checkout="2026-11-09", destination_city="NYC",
                                             max_candidates=7, max_flights_per_participant=3, max_lodgings=4)
    first = run()
    assert len(calls) <= 7 * 4  # never visits 40**3 * 20 combinations
    assert len(first) == len({c.id for c in first}) == 7
    members.reverse()
    lodgings.reverse()
    for choices in flights.values():
        choices.reverse()
    assert first == run()
    assert len({tuple(p.flight.booking_token for p in c.participants) for c in first}) > 1
    assert len({c.lodging_name for c in first}) == 1  # distinct provider tokens still yield distinct IDs


def test_group_ids_depend_on_itineraries_not_prices(group_trip):
    before, = _group(group_trip)
    group_trip[1]["bob"][0].total_price_usd += 1
    after, = _group(group_trip)
    assert before.id == after.id and before.group_total != after.group_total
    group_trip[1]["bob"][0].return_flight[0].scheduled_departure = "2026-11-09 13:00"
    changed, = _group(group_trip)
    assert after.id != changed.id


@pytest.mark.parametrize("limit", [0, -1, True, 1.5])
def test_group_rejects_invalid_selection_limits(group_trip, limit):
    with pytest.raises(ValueError):
        _group(group_trip, max_candidates=limit)


def test_group_validates_members_and_dates(group_trip):
    members, flights, lodging = group_trip
    with pytest.raises(ValueError, match="unique"):
        build_group_candidates([members[0], members[0]], {}, [lodging], checkin="2026-11-05", checkout="2026-11-09", destination_city="NYC")
    with pytest.raises(ValueError, match="Non-positive"):
        build_group_candidates(members, flights, [lodging], checkin="2026-11-05", checkout="2026-11-05", destination_city="NYC")
    with pytest.raises(ValueError, match="non-participant"):
        build_group_candidates(members[:1], flights, [lodging], checkin="2026-11-05", checkout="2026-11-09", destination_city="NYC")
    with pytest.raises(ValueError):
        Participant("alice", "")


def test_connected_return_duration_includes_legs_and_layover():
    outbound = FlightOptionStage1(
        departure_token="dt", origin_id="AUS", destination_id="JFK", total_duration_min=200,
        flights=[FlightLeg(departure_airport_id="AUS", arrival_airport_id="JFK")],
    )
    choice = FlightOptionComplete(
        outbound_token="dt", booking_token="bt", total_duration_min=330,
        return_flight=[FlightLeg(departure_airport_id="JFK", arrival_airport_id="ORD", duration_min=120),
                       FlightLeg(departure_airport_id="ORD", arrival_airport_id="AUS", duration_min=150)],
    )
    assert build_round_trip(outbound, choice).inbound_duration_min == 330
    choice.total_duration_min = None
    assert build_round_trip(outbound, choice).inbound_duration_min is None


@pytest.mark.parametrize("bad_price", [None, -10, float("nan"), float("inf")])
def test_group_invalid_flight_prices_do_not_become_totals(group_trip, bad_price):
    group_trip[1]["alice"][0].total_price_usd = bad_price
    candidate, = _group(group_trip)
    assert candidate.group_total is None
    assert candidate.participants[0].flight_cost is None
    assert "flight_price_missing:alice" in candidate.feasibility_reasons


def test_group_retains_separate_quote_timestamps(group_trip):
    older = datetime(2026, 10, 24, 12, tzinfo=UTC)
    group_trip[1]["alice"][0].retrieved_at = older
    candidate, = _group(group_trip)
    assert candidate.priced_at == older
    assert candidate.lodging_priced_at == group_trip[2].retrieved_at
    assert candidate.participants[0].flight.retrieved_at == older
    group_trip[2].retrieved_at = None
    candidate, = _group(group_trip)
    assert candidate.priced_at is None and candidate.lodging_priced_at is None


def test_group_bounded_selection_prefers_supported_candidates(group_trip):
    members, flights, lodging = group_trip
    flights["alice"].insert(0, flights["alice"][0].model_copy(update={"complete": False, "booking_token": "bad"}))
    unknown = lodging.model_copy(update={"max_occupancy": None, "property_token": "unknown"})
    too_small = lodging.model_copy(update={"max_occupancy": 2, "property_token": "small"})
    candidates = build_group_candidates(
        members, flights, [unknown, too_small, lodging], checkin="2026-11-05", checkout="2026-11-09",
        destination_city="NYC", max_candidates=1, max_flights_per_participant=1, max_lodgings=1,
    )
    assert len(candidates) == 1 and candidates[0].feasibility == FeasibilityStatus.FEASIBLE


def test_group_rejects_unvalidated_flight_types(group_trip):
    group_trip[1]["alice"] = [FlightOptionStage1()]
    with pytest.raises(TypeError, match="RoundTripFlight"):
        _group(group_trip)


def test_mixed_direction_provider_duration_is_not_counted_as_return_only():
    outbound = FlightOptionStage1(
        departure_token="dt", origin_id="AUS", destination_id="JFK", total_duration_min=200,
        flights=[FlightLeg(departure_airport_id="AUS", arrival_airport_id="JFK")],
    )
    raw = {"booking_token": "bt", "total_duration": 1200, "flights": [
        {"direction": "outbound", "departure_airport": {"id": "AUS"},
         "arrival_airport": {"id": "JFK"}, "duration": 200},
        {"direction": "return", "departure_airport": {"id": "JFK"},
         "arrival_airport": {"id": "AUS"}, "duration": 230},
    ]}
    choice = FlightOptionComplete.from_dict(raw, outbound=outbound)
    assert choice.total_duration_min is None
    assert build_round_trip(outbound, choice).inbound_duration_min == 230
    raw["flights"] = raw["flights"][1:]
    raw["total_duration"] = 230
    choice = FlightOptionComplete.from_dict(raw, outbound=outbound)
    assert choice.total_duration_min == 230


def test_public_planner_dates_use_local_day_and_leave_ambiguity_unresolved():
    from app.logic.listening import ground_timing
    update={'field':'when.agreed','value':{'label':'Tomorrow at dinner','date':'2099-01-01'},'source_message_id':'m'}
    result=ground_timing([update],[{'id':'m','text':'Tomorrow at dinner works'}],'2026-10-25')
    assert result[0]['value']['date']=='2026-10-26'
    result=ground_timing([update],[{'id':'m','text':'Maybe next weekend'}],'2026-10-25')
    assert result[0]['value']['date'] is None
    result=ground_timing([update],[{'id':'m','text':'2026-11-03 or 2026-11-04'}],'2026-10-25')
    assert result[0]['value']['date'] is None
    result=ground_timing([update],[{'id':'m','text':'Friday works'}],'2026-10-25')
    assert result[0]['value']['date']=='2026-10-30'


def test_public_planner_semantics_ignore_speaking_and_provenance_only_changes():
    from copy import deepcopy
    from app.logic.listening import new_template, semantic_signature
    template=new_template('Dinner','Dining',members=('alice','bob'))
    changed=deepcopy(template);changed['spoke']=['alice'];changed['sources']={'cuisine:group':'suggested'}
    assert semantic_signature(template)==semantic_signature(changed)
    changed['attendance']['alice']={'status':'going','condition':None}
    assert semantic_signature(template)!=semantic_signature(changed)


def test_widgets_require_matching_event_evidence_and_never_make_up_tickets():
    from app.logic.widget_evidence import event_for_venue, public_url
    stamp=datetime(2026,10,25,tzinfo=UTC)
    event={'title':'Artist live in Austin','venue':{'name':'Moody Center'},'date':{'when':'Saturday, November 7'},
           'image':'https://images.example/concert.jpg','ticket_info':[{'link':'https://tickets.example/event'}]}
    assert event_for_venue([event],'Another venue','concert',retrieved_at=stamp) is None
    special=event_for_venue([event],'Moody Center','concert',retrieved_at=stamp)
    assert special and special.kind=='concert' and special.choices==[]
    assert event_for_venue([event],'Moody Center','concert',retrieved_at=stamp,exact_date='2026-11-07') is None
    assert event_for_venue([event],'Moody Center','college_football',retrieved_at=stamp) is None
    event['title']='Texas college football vs Oklahoma'
    assert event_for_venue([event],'Moody Center','college_football',retrieved_at=stamp)
    assert event_for_venue([event],'Moody Center','college_football',retrieved_at=stamp,venue_address='1401 Trinity Street, Austin, TX') is None
    event['ticket_info']=[]
    assert event_for_venue([event],'Moody Center','concert',retrieved_at=stamp) is None
    assert public_url('https://site.example/photo?api_key=secret') is None
    assert public_url('https://user:secret@site.example/photo') is None


def test_widget_provider_images_and_reviews_survive_normalization(group_trip):
    from app.integrations.serpapi_normalized import Place, Property
    place=Place.from_dict({'title':'Cafe','thumbnail':'https://images.example/cafe.jpg','reviews':42})
    assert place.image_url=='https://images.example/cafe.jpg' and place.review_count==42
    property=Property.from_dict({'name':'Stay','images':[{'original_image':'https://images.example/stay.jpg'}]})
    assert property.image_url=='https://images.example/stay.jpg'
    group_trip[2].image_url=property.image_url
    group_trip[2].overall_rating=4.6
    group_trip[2].review_count=42
    candidate,=_group(group_trip)
    assert candidate.lodging_image_url==property.image_url and candidate.lodging_review_count==42


def test_public_conversation_template_accepts_only_speakers_volunteered_budget():
    from app.logic.listening import new_template,safe_updates,listener_text
    template=new_template('Dinner','Dining',members=('alice','bob'));template['budget']={}
    message={'id':'m','user_id':'alice','text':'My budget is $250'}
    updates=[{'field':'budget','value':250,'user_id':'alice','source_message_id':'m'},
             {'field':'budget','value':800,'user_id':'bob','source_message_id':'m'}]
    result,_=safe_updates(template,updates,[message])
    assert result['budget']=={'alice':250}
    invented,_=safe_updates(template,[{**updates[0],'value':999}],[message])
    assert invented['budget']=={}
    assert listener_text(message['text'],public_budget=True)==message['text']
    euro,_=safe_updates(template,[updates[0]],[{**message,'text':'My budget is EUR 250'}])
    assert euro['budget']=={}
    assert '887766' not in listener_text('My bank account is 887766 and my budget is 250',public_budget=True)
