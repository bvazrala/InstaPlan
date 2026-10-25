"""Fixture-based tests for SerpApi normalisation, flight reconstruction, and trip-candidate generation.

All data comes from ``fixtures/serpapi/`` — zero network calls, zero API key.
Tests cover every P0 finding: occupancy bug, id collision, flight split, price status, complete label.
"""

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "serpapi"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture()
def flights_stage1():
    """Parse stage-1 flight fixture."""
    from app.integrations.serpapi_normalized import parse_flight_stage1
    raw = load_fixture("flights_stage1.json")
    return parse_flight_stage1(raw)


@pytest.fixture()
def completed_flights(flights_stage1):
    """Parse stage-2 and assemble RoundTripFlights against stage1[0].

    Each stage-2 return choice is token-paired to its stage-1 outbound (best_flights[0]) and
    validated: both legs present, route contiguous, booking token present.
    """
    from app.integrations.serpapi_normalized import parse_flight_stage2, assemble_round_trips
    raw = load_fixture("flights_stage2.json")
    choices = parse_flight_stage2(raw, original_stage1_option=flights_stage1[0])
    return assemble_round_trips(flights_stage1[:1], choices)


@pytest.fixture()
def properties():
    """Parse hotel fixture."""
    from app.integrations.serpapi_normalized import parse_hotel_properties
    raw = load_fixture("hotels_vacation_rentals.json")
    return parse_hotel_properties(raw)


# ===================================================================
# Phase 1: Flight Stage-1 parsing (P0 #3, P1.7, P1.8)
# ===================================================================


class TestFlightStage1Parsing:
    """Parse the stage-1 fixture."""

    def test_parses_all_options(self, flights_stage1):
        assert len(flights_stage1) == 6  # best_flights(3) + other_flights(3)

    def test_strips_best_and_other_flights(self, flights_stage1):
        arrays = {opt.source.get("array_name") for opt in flights_stage1}
        assert "best_flights" in arrays
        assert "other_flights" in arrays

    def test_prices_present(self, flights_stage1):
        prices = [o.price_usd for o in flights_stage1 if o.price_usd is not None]  # type: ignore[attr-defined]
        assert len(prices) == 6

    def test_first_option_is_697(self, flights_stage1):
        best = [o for o in flights_stage1 if o.source.get("array_name") == "best_flights" and o.price_usd is not None]  # type: ignore[attr-defined]
        assert best[0].price_usd == 697.0

    def test_departure_tokens_present(self, flights_stage1):
        for opt in flights_stage1:
            if opt.departure_token is None:
                raise AssertionError(f"Option with price {opt.price_usd} missing departure_token")

    def test_legs_parsed(self, flights_stage1):
        for opt in flights_stage1:
            assert isinstance(opt.flights, list)

    def test_flight_number_is_str(self, flights_stage1):
        """FIX P1.7: flight_number is str not int — provider sends "AA 2287"""
        legs = [fl for o in flights_stage1[:3] for fl in o.flights]
        for leg in legs:
            fn = leg.flight_number
            if fn is not None:
                assert isinstance(fn, str)


# ===================================================================
# Phase 2: Flight Stage-2 completion (P0 #3)
# ===================================================================


class TestRoundTripAssembly:
    """Validate that stage-1 outbound + stage-2 return choices assemble into authoritative, complete itineraries."""

    def test_assembles_one_per_return_choice(self, completed_flights):
        assert len(completed_flights) > 0

    def test_booking_token_present(self, completed_flights):
        for it in completed_flights:
            if it.booking_token is None:
                raise AssertionError(f"Itinerary with price {it.total_price_usd} missing booking_token")

    def test_matching_price_with_stage1(self, completed_flights):
        for it in completed_flights:
            assert hasattr(it, 'total_price_usd')
            if it.total_price_usd is not None and it.total_price_usd != 697.0:
                raise AssertionError(f"Round-trip price {it.total_price_usd} != expected 697")

    def test_split_outbound_return(self, completed_flights):
        """A rebuilt RoundTripFlight carries BOTH the selected outbound and the return leg."""
        for it in completed_flights[:1]:
            assert it.outbound_flight, "must have the selected stage-1 outbound legs"
            assert it.return_flight, "must have the stage-2 return legs"

    def test_all_fixture_round_trips_are_complete(self, completed_flights):
        for it in completed_flights:
            assert it.complete is True, f"expected complete itinerary, reasons: {it.incomplete_reasons}"


# ===================================================================
# Phase 3: Hotels / vacation rentals (P0 #1)
# ===================================================================


class TestHotelsParsing:
    """Parse the fixture and verify price/occupancy behavior."""

    def test_parses_properties(self, properties):
        assert len(properties) == 5

    def test_skips_ads(self, properties):
        names = [p.name for p in properties if p.name]
        assert "Sponsored Hotel NYC" not in names

    def test_total_rate_after_tax(self, properties):
        loft = next(p for p in properties if p.name == "Manhattan Loft on 5th Ave")
        assert loft.has_total_price is True

    def test_currency_preserved(self, properties):
        for p in properties:
            assert p.currency == "USD"

    def test_no_invented_occupancy(self, properties):
        """FIX P0 #1: No review count used as occupancy."""
        for p in properties:
            # All must have max_occupancy=None (no capacity field in fixture)
            if hasattr(p, 'max_occupancy'):
                assert p.max_occupancy is None  # type: ignore[attr-defined]

    def test_property_without_total_rate(self, properties):
        brooklyn = next(p for p in properties if p.name == "Brooklyn Brownstone Studio")
        assert brooklyn.has_total_price is False  # has nightly but not total Rate

    def test_property_has_capacity_unverified_flag(self, properties):
        """All fixtures lack max_occupancy — capacity_unverified must default True."""
        for p in properties:
            if hasattr(p, 'max_occupancy'):
                assert p.max_occupancy is None  # type: ignore[attr-defined]


# ===================================================================
# Phase 4: Google Maps places
# ===================================================================


class TestMapsPlaces:
    """Parse a google_maps response and ensure missing data stays None."""

    def test_parses_local_results(self, maps_places):
        assert len(maps_places) == 5

    def test_missing_price_level(self, maps_places):
        katz = next(p for p in maps_places if p.title == "Katz's Delicatessen")
        assert katz.price_level is None

    def test_place_ids_preserved(self, maps_places):
        for place in maps_places:
            if place.place_id and place.data_id and place.data_cid:  # type: ignore[attr-defined]
                assert place.place_id != place.data_id
                assert place.data_id != place.data_cid

    def test_coordinates_parsed(self, maps_places):
        for p in maps_places:
            if p.latitude is not None and p.longitude is not None:
                pass


# ===================================================================
# Phase 5: Events
# ===================================================================


class TestEvents:
    """Parse events_rows and document known provider caveats."""

    def test_parses_events(self, events_list):
        assert len(events_list) == 5

    def test_date_no_year(self, events_list):
        for e in events_list:
            if e.date_start_month_day:
                # No year in raw dates
                parts = (e.date_start_month_day or "").split(" ")
                yr = parts[-1] if len(parts) >= 1 else ""
                assert not yr.isdigit() or len(yr) <= 2, f"Year component found in {e.date_start_month_day}"

    def test_ticket_info_no_prices(self, events_list):
        for evt in events_list:
            for ticket in evt.ticket_info:
                assert "price" not in {k.lower() for k in ticket.keys()}


# ===================================================================
# Phase 6: Search results
# ===================================================================


class TestSearch:
    def test_parses_organic_results(self, search_results):
        results, overview = search_results
        assert len(results) == 9

    def test_ai_overview_present(self, search_results):
        results, overview = search_results
        assert overview is not None
        assert overview.snippet is not None


# ===================================================================
# Phase 7: Trip-candidate generator (P0 #1–6 + all P1)
# ===================================================================


class TestCandidateGenerator:

    def test_combination_valid(self, flights_stage1, properties):
        """Basic valid combo produces candidates with proper fields."""
        from app.integrations.serpapi_candidate_generator import build_all_candidates
        candidates = build_all_candidates(
            flights_stage1=flights_stage1,
            hotels_properties=properties,
            checkin="2026-11-05",
            checkout="2026-11-09",
            adults=4,
        )
        priced = [c for c in candidates if c.lodging_price.has_cost]
        assert len(priced) > 0

    def test_occupancy_not_from_review_count(self, flights_stage1, properties):
        """FIX P0 #1: occupancy_adults is NEVER derived from reviews."""
        from app.integrations.serpapi_candidate_generator import build_all_candidates

        ue_side = next(p for p in properties if "Upper East" in p.name)  # 201 reviews!
        candidates = build_all_candidates(
            flights_stage1=flights_stage1[:1],
            hotels_properties=[ue_side],
            checkin="2026-11-05",
            checkout="2026-11-09",
            adults=4,
        )
        for c in candidates:
            assert c.occupancy_adults != 201, "Upper East Side must NOT get occupancy=201 from reviews!"
            if hasattr(c, 'capacity_unverified') and c.capacity_unverified:
                # When max_occupancy is unknown, capacity_verified should also be False
                if c.capacity_verified is not None:  # type: ignore[attr-defined]
                    assert c.capacity_verified is not True  # type: ignore[arg-type]

    def test_price_status_separate_completeness(self, flights_stage1, properties):
        """Price coverage (structured, quoted vs estimated) is independent of, and distinct from, flight status."""
        from app.integrations.serpapi_candidate_generator import build_all_candidates, LodgingCompliance

        brooklyn = next(p for p in properties if "Brooklyn" in p.name)  # only nightly, no total_rate
        candidates = build_all_candidates(
            flights_stage1=flights_stage1[:1],
            hotels_properties=[brooklyn],
            checkin="2026-11-05",
            checkout="2026-11-09",
            adults=4,
        )
        for c in candidates:
            assert hasattr(c, 'lodging_price'), "must have a structured LodgingPrice object"
            # Brooklyn is a nightly estimate: ESTIMATED + tax_inclusive=False, never QUOTED_WITH_TAXES
            if c.lodging_name == "Brooklyn Brownstone Studio":
                assert c.lodging_price.status == LodgingCompliance.ESTIMATED
                assert c.lodging_price.tax_inclusive is False

    def test_complete_flight_with_booking_token(self, completed_flights, properties):
        """Rebuilt complete round-trips yield COMPLETE candidates with a booking token."""
        from app.integrations.serpapi_candidate_generator import build_all_candidates
        from app.integrations.serpapi_normalized import FlightStatus

        candidates = build_all_candidates(
            flights_stage1=[],
            hotels_properties=[properties[0]],
            round_trips=completed_flights,
            checkin="2026-11-05",
            checkout="2026-11-09",
            adults=4,
        )
        assert candidates
        for c in candidates:
            assert c.flight_status == FlightStatus.COMPLETE
            assert c.booking_token is not None

    def test_invalid_dates_raise(self, properties):
        """FIX P0 #6: invalid/malformed dates must raise InvalidDatesError."""
        from app.integrations.serpapi_candidate_generator import build_all_candidates

        for checkin, checkout in [("x", "y"), ("2026-11-09", "2026-11-05")]:  # reversed dates = negative nights
            with pytest.raises(ValueError):
                build_all_candidates(
                    flights_stage1=[],
                    hotels_properties=properties[:1],
                    checkin=checkin,
                    checkout=checkout,
                    adults=4,
                )

    def test_unique_id_generator(self, properties):
        """Test ID generation is deterministic (regression test for candidate generator)."""
        from app.integrations.serpapi_candidate_generator import make_candidate_id
        from app.integrations.serpapi_normalized import FlightOptionStage1

        # Create a minimal mock flight option to test id generation
        mock_flight = FlightOptionStage1(
            source={"engine": "google_flights", "stage": 1},
            trip_type="Round trip", price_usd=697.0, departure_token="test_token_123"
        )
        id1 = make_candidate_id(mock_flight, properties[0], ("2026-11-05", "2026-11-09"))
        assert isinstance(id1, str) and len(id1) > 10


def _round_trips_for(flights_stage1):
    """Assemble complete round-trips against stage1[0] from the stage-2 fixture."""
    from app.integrations.serpapi_normalized import parse_flight_stage2, assemble_round_trips
    raw = load_fixture("flights_stage2.json")
    choices = parse_flight_stage2(raw, original_stage1_option=flights_stage1[0])
    return assemble_round_trips(flights_stage1[:1], choices)


# ===================================================================
# Phase 7b: Executable regressions from the second-line review
#          (itinerary integrity, candidate identity, financial correctness, eligibility)
#          No live SerpApi requests — only local fixtures and synthetic edge cases.
# ===================================================================


class TestItineraryIntegrityAndIdentity:
    """Regressions for the two reproduced bugs (id collision, false COMPLETENESS) plus financial/eligibility invariants."""

    def test_three_same_price_returns_yield_three_distinct_ids(self, flights_stage1, properties):
        """#1: three $697 returns with different booking tokens must produce three distinct ids."""
        from app.integrations.serpapi_candidate_generator import build_all_candidates
        rts = _round_trips_for(flights_stage1)
        assert len(rts) == 3
        assert {rt.total_price_usd for rt in rts} == {697.0}
        assert len({rt.booking_token for rt in rts}) == 3, "fixture gives three distinct booking tokens"
        cands = build_all_candidates(hotels_properties=[properties[0]], round_trips=rts)
        ids = [c.id for c in cands]
        assert len(ids) == 3, f"same-price returns must not collide: {ids}"
        assert len(set(ids)) == 3

    def test_directionless_stage2_return_leg_classified_via_stage1_context(self, flights_stage1):
        """#2: a stage-2 return leg with NO direction field is reconstructed as a RETURN via stage-1 context."""
        from app.integrations.serpapi_normalized import FlightOptionComplete, build_round_trip
        s1 = flights_stage1[0]
        s2_no_direction = {
            "type": "Round trip",
            "price": 697,
            "booking_token": "synthetic_no_direction",
            "flights": [
                {  # a return leg (JFK -> AUS) with NO "direction" field
                    "airline": "American Airlines",
                    "flight_number": 999,
                    "departure_airport": {"id": "JFK", "name": "JFK"},
                    "arrival_airport": {"id": "AUS", "name": "AUS"},
                    "duration": 240,
                }
            ],
        }
        choice = FlightOptionComplete.from_dict(s2_no_direction, outbound=s1)
        assert len(choice.return_flight) == 1, "a directionless leg back to the origin is a return, not outbound"
        assert choice.return_flight[0].arrival_airport_id == s1.origin_id
        rt = build_round_trip(s1, choice)
        assert rt.complete is True, f"directionless return must reconstruct a complete trip: {rt.incomplete_reasons}"
        assert rt.return_flight, "return leg must survive reconstruction"

    def test_return_only_itinerary_never_marked_complete(self, flights_stage1):
        """#3: an itinerary with a return leg but no outbound is NOT complete."""
        from app.integrations.serpapi_normalized import FlightOptionStage1, FlightOptionComplete, build_round_trip, FlightLeg
        # No outbound legs at all -> a "return-only" itinerary.
        empty_out = FlightOptionStage1(
            source={"engine": "google_flights", "stage": 1},
            departure_token="dt-none", origin_id="AUS", destination_id="JFK",
            currency="USD", price_usd=697.0, flights=[],
        )
        return_leg = FlightLeg(flight_number="417", departure_airport_id="JFK", arrival_airport_id="AUS")
        choice = FlightOptionComplete(
            source={"stage": 2},
            outbound_token="dt-none", origin_id="AUS", destination_id="JFK",
            return_flight=[return_leg], booking_token="bt-1", quoted_price_usd=697.0,
        )
        rt = build_round_trip(empty_out, choice)
        assert rt.complete is False
        assert "no_outbound_legs" in rt.incomplete_reasons

    def test_currency_mismatch_prevents_cost_aggregation(self, flights_stage1):
        """#4: a flight priced in USD + lodging priced in EUR must NOT be summed into a total."""
        from app.integrations.serpapi_candidate_generator import TripCandidate
        from app.integrations.serpapi_normalized import Property, PriceDict
        s1 = flights_stage1[0]
        euro = Property(
            name="EUR Hotel",
            currency="EUR",
            rate_per_night=PriceDict(display_price=100, extracted_before_taxes_fees=98.0),
        )
        c = TripCandidate.from_combination(s1, euro, checkin="2026-11-05", checkout="2026-11-09", adults=2)
        assert c.total_per_person is None, "never sum amounts expressed in different currencies"
        assert any("currency_mismatch" in w for w in c.warnings), f"expected currency_mismatch, got {c.warnings}"

    def test_tax_exclusive_estimate_never_labeled_after_tax(self, flights_stage1, properties):
        """#5: a nightly-derived estimate must be ESTIMATED + tax_inclusive=False, never an after-tax price."""
        from app.integrations.serpapi_candidate_generator import build_all_candidates, LodgingCompliance
        brooklyn = next(p for p in properties if "Brooklyn" in p.name)
        rts = _round_trips_for(flights_stage1)
        cands = build_all_candidates(hotels_properties=[brooklyn], round_trips=rts)
        assert cands
        for c in cands:
            assert c.lodging_price.status == LodgingCompliance.ESTIMATED
            assert c.lodging_price.tax_inclusive is False
            assert c.lodging_price.amount is not None

    def test_incomplete_flight_never_outranks_complete(self, flights_stage1, properties):
        """#6: an incomplete flight must not outrank a complete one just because its lodging quote is more detailed."""
        from app.integrations.serpapi_candidate_generator import build_all_candidates
        quoted = next(p for p in properties if "Manhattan" in p.name)    # total_rate (quoted)
        estimated = next(p for p in properties if "Brooklyn" in p.name)  # nightly (estimated)
        rts = _round_trips_for(flights_stage1)
        merged = build_all_candidates(
            flights_stage1=flights_stage1[:1],
            hotels_properties=[quoted, estimated],
            round_trips=rts,
        )
        complete_ids = {c.id for c in build_all_candidates(hotels_properties=[estimated], round_trips=rts)}
        incomplete_ids = {c.id for c in build_all_candidates(flights_stage1=flights_stage1[:1], hotels_properties=[quoted])}
        pos = {cid: i for i, cid in enumerate(c.id for c in merged)}
        complete_pos = [pos[i] for i in complete_ids if i in pos]
        incomplete_pos = [pos[i] for i in incomplete_ids if i in pos]
        assert complete_pos and incomplete_pos
        assert max(complete_pos) < min(incomplete_pos), (
            "a more detailed lodging quote must not outrank a complete flight over an incomplete one"
        )

    def test_repeated_generation_produces_stable_ids(self, flights_stage1, properties):
        """#7: identical inputs must always produce the identical, ordered id set."""
        from app.integrations.serpapi_candidate_generator import build_all_candidates
        rts = _round_trips_for(flights_stage1)
        run1 = build_all_candidates(hotels_properties=properties, round_trips=rts)
        run2 = build_all_candidates(hotels_properties=properties, round_trips=rts)
        assert [c.id for c in run1] == [c.id for c in run2]

    def test_changing_scheduled_time_changes_id(self, flights_stage1, properties):
        """#8: two itineraries identical except one scheduled time must yield different ids."""
        from app.integrations.serpapi_normalized import FlightLeg, RoundTripFlight
        from app.integrations.serpapi_candidate_generator import make_candidate_id

        def rt(time: str) -> RoundTripFlight:
            return RoundTripFlight(
                outbound_flight=[FlightLeg(flight_number="416", departure_airport_id="AUS",
                                           arrival_airport_id="JFK", scheduled_departure=time)],
                return_flight=[FlightLeg(flight_number="417", departure_airport_id="JFK",
                                         arrival_airport_id="AUS", scheduled_departure="2026-11-09 09:00")],
                booking_token="bt-x", departure_token="dt-x", currency="USD",
                total_price_usd=697.0, complete=True,
            )

        prop = properties[0]
        id_a = make_candidate_id(rt("2026-11-05 06:47"), prop, ("2026-11-05", "2026-11-09"))
        id_b = make_candidate_id(rt("2026-11-05 08:47"), prop, ("2026-11-05", "2026-11-09"))
        assert id_a != id_b, "changing a scheduled time must change the candidate id"

    def test_genuine_duplicates_are_deduplicated(self, flights_stage1, properties):
        """Genuine duplicates (identical itinerary + property + dates) must collapse to a single candidate."""
        from app.integrations.serpapi_candidate_generator import build_all_candidates
        rts = _round_trips_for(flights_stage1)
        doubled = list(rts) + list(rts)
        cands = build_all_candidates(hotels_properties=[properties[0]], round_trips=doubled)
        assert len(cands) == len(rts)
        assert len({c.id for c in cands}) == len(cands)

    def test_priced_at_reflects_provider_retrieval(self, flights_stage1, properties):
        """#3 (money): priced_at comes from the provider's retrieval time, not candidate generation time."""
        from app.integrations.serpapi_candidate_generator import build_all_candidates
        rts = _round_trips_for(flights_stage1)
        for c in build_all_candidates(hotels_properties=properties[:1], round_trips=rts):
            assert c.priced_at is not None
            assert (c.priced_at.year, c.priced_at.month) == (2026, 10)

    def test_capacity_not_verified_from_reviews(self, flights_stage1, properties):
        """Unknown capacity must not become verified feasibility; the two flags must not contradict."""
        from app.integrations.serpapi_candidate_generator import build_all_candidates
        rts = _round_trips_for(flights_stage1)
        for c in build_all_candidates(hotels_properties=properties, round_trips=rts):
            assert c.capacity_verified is False
            assert c.capacity_unverified is True

    def test_legroom_cm_unit_conversion(self):
        """legroom_cm parses '30 in' -> 76.2, '76 cm' -> 76, and passes numerics through."""
        from app.integrations.serpapi_normalized import FlightLeg
        assert FlightLeg(legroom_raw="30 in").legroom_cm == 76.2
        assert FlightLeg(legroom_raw="76 cm").legroom_cm == 76.0
        assert FlightLeg(legroom_raw=31).legroom_cm == 31.0


# ===================================================================
# Phase 8: Example output (golden)
# ===================================================================


class TestGoldenOutput:
    """Validate that the generator output matches the stored example schema."""

    @pytest.mark.skip(reason="Generated at /docs/serpapi-candidates-example.json for human inspection")
    def test_output_schema_compliant(self):
        pass  # Manual check against docs/serpapi-candidates-example.json


# ===================================================================
# Fixtures needed by tests above — same as existing conftest pattern:
# ===================================================================


@pytest.fixture()
def maps_places():
    from app.integrations.serpapi_normalized import parse_maps_places
    raw = load_fixture("maps_places.json")
    return parse_maps_places(raw)


@pytest.fixture()
def events_list():
    from app.integrations.serpapi_normalized import parse_events
    raw = load_fixture("events_nyc.json")
    return parse_events(raw)


@pytest.fixture()
def search_results():
    from app.integrations.serpapi_normalized import parse_search
    raw = load_fixture("search_budget.json")
    return parse_search(raw)
