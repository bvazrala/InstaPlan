"""Opt-in bounded provider smoke test. Uses a scratch cache, never the application's DB."""
import argparse
from pathlib import Path
from tempfile import TemporaryDirectory
from sqlmodel import Session, create_engine

from app.config import get_settings
from app.integrations.serpapi_client import SerpApiClient
from app.logic.candidates import Participant, build_group_candidates, _validate_nights
from app.logic.planning import Destination
from app.models import ApiCache


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Explicitly authorize paid SerpApi requests")
    parser.add_argument("--origins", default="AUS,BOS,LAX")
    parser.add_argument("--destination", default="JFK")
    parser.add_argument("--city", default="New York City")
    parser.add_argument("--checkin", required=True)
    parser.add_argument("--checkout", required=True)
    parser.add_argument("--request-limit", type=int, default=12)
    args = parser.parse_args()
    if not args.live:
        parser.error("Pass --live to make provider requests; ordinary tests never require it")
    if not 1 <= args.request_limit <= 20:
        parser.error("request-limit must be between 1 and 20")
    if not get_settings().serpapi_key:
        parser.error("Set SERPAPI_KEY on the backend")
    _validate_nights(args.checkin, args.checkout)
    members = [Participant(f"member-{i}", origin) for i, origin in enumerate(args.origins.split(","), 1)]
    destination = Destination(name=args.city, airports=[args.destination])
    with TemporaryDirectory(prefix="instaplan-smoke-") as directory:
        cache_engine = create_engine(f"sqlite:///{Path(directory) / 'cache.db'}", connect_args={"check_same_thread": False})
        ApiCache.__table__.create(cache_engine)
        try:
            api = SerpApiClient(session_factory=lambda: Session(cache_engine), settings=get_settings().model_copy(
                update={"serpapi_request_limit": args.request_limit}))
            flights, properties, partial = api.collect([member.origin_airport for member in members], destination,
                                                       args.checkin, args.checkout, len(members))
            options = build_group_candidates(members, {member.user_id: flights.get(member.origin_airport, []) for member in members},
                properties, checkin=args.checkin, checkout=args.checkout, destination_city=args.city,
                destination_airports=destination.airports)
            print(f"requests={api.requests} candidates={len(options)} partial={partial}")
            for option in options:
                print(f"{option.id} complete={option.complete} feasibility={option.feasibility.value} coverage={option.lodging_price.status.value}")
            return 0 if options else 1
        finally:
            cache_engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
