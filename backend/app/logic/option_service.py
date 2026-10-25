"""The private boundary: DB decryption and budget/requirement evaluation stay here.

Only validated OptionOut values and opaque revision digests leave this service.
"""
import hashlib
import json
from decimal import Decimal

from sqlmodel import Session, select
from app.config import get_settings
from app.integrations import muse_private
from app.logic.candidates import TripCandidate
from app.logic.fit import evaluate_fit
from app.logic.planning import Constraint, PlanningInput, Preference
from app.logic.ranking import rank_candidates, within_ceilings
from app.models import PrivatePrefs
from app.privacy.access import private_budgets_allowed
from app.privacy.context import PrivateContext
from app.privacy.crypto import decrypt_json
from app.schemas import OptionOut, PrivatePrefsData, TravelLeg


class EvaluationUnavailable(Exception):
    def __init__(self):
        super().__init__("Requirements could not be evaluated")


def private_revision(session: Session, trip_id: str) -> str:
    rows = session.exec(select(PrivatePrefs).where(PrivatePrefs.trip_id == trip_id)).all()
    value = sorted((row.user_id, row.data_encrypted) for row in rows)
    return hashlib.sha256(json.dumps(value).encode()).hexdigest()


def evaluate_options(session: Session, trip_id: str, candidates: list[TripCandidate], planning: PlanningInput, *, include_private=True, public_ceilings=None) -> list[OptionOut]:
    if not candidates:
        return []
    ids = {person.user_id for candidate in candidates for person in candidate.participants}
    rows = session.exec(select(PrivatePrefs).where(PrivatePrefs.trip_id == trip_id)).all() if include_private else []
    preferences = list(planning.preferences)
    constraints = list(planning.constraints)
    ceilings = {uid:Decimal(str(value)) for uid,value in (public_ceilings or {}).items() if value is not None}
    for row in rows:
        if row.user_id not in ids:
            continue
        try:
            prefs = PrivatePrefsData.model_validate(decrypt_json(row.data_encrypted))
        except Exception:
            raise EvaluationUnavailable() from None
        if private_budgets_allowed(len(ids)) and prefs.budget_cap is not None:
            cap = Decimal(str(prefs.budget_cap))
            if not cap.is_finite() or cap < 0:
                raise EvaluationUnavailable()
            ceilings[row.user_id] = cap
        for item, score in prefs.private_scores.items():
            if type(score) is int and -2 <= score <= 2:
                preferences.append(Preference(member_id=row.user_id, category="Destination", value=item, score=score))
        if prefs.accessibility or prefs.no_gos.strip():
            try:
                if not get_settings().muse_api_key:
                    raise EvaluationUnavailable()
                normalized = muse_private.normalize_requirements(PrivateContext(
                    trip_id=trip_id, user_id=row.user_id, first_name="Member", prefs=prefs))
                if not normalized.constraints and not normalized.out_of_scope:
                    # Nonempty free text cannot silently become "no restrictions".
                    raise EvaluationUnavailable()
                constraints.extend(rule.model_copy(update={"member_id": row.user_id, "source_fact_ids": []})
                                   for rule in normalized.constraints)
            except Exception:
                # Do not surface the model's response, values, owner, or failure detail.
                constraints.append(Constraint(kind="unsupported", member_id=row.user_id))
    evaluated = {}
    kept = []
    for candidate in candidates:
        if candidate.group_total is None or not candidate.currency or not within_ceilings(candidate, ceilings):
            continue
        fit = evaluate_fit(candidate, preferences, constraints)
        if fit.violated:
            continue
        evaluated[candidate.id] = fit
        kept.append(candidate)
    order = rank_candidates(kept, "balanced", ceilings=ceilings)
    order = sorted(order, key=lambda candidate: not evaluated[candidate.id].pick_eligible)[:12]
    fairest = {candidate.id: index + 1 for index, candidate in enumerate(rank_candidates(order, "fairest", ceilings=ceilings))}
    result = []
    for recommendation_rank,candidate in enumerate(order,1):
        fit = evaluated[candidate.id]
        # Namespace IDs by trip, preventing identical itineraries in different trips colliding.
        option_id = "opt-" + hashlib.sha256(f"{trip_id}:{candidate.id}".encode()).hexdigest()[:24]
        result.append(OptionOut(
            recommendation_rank=recommendation_rank,id=option_id, title=candidate.title, place=candidate.place, dates=candidate.dates,
            nights=candidate.nights, lodging=candidate.lodging_name,
            lodging_share=float(candidate.lodging_price.amount / len(candidate.participants)), daily=0,
            fit=fit.fit, certainty=fit.certainty, cats=fit.cats, fairest_rank=fairest[candidate.id],
            people=[TravelLeg(id=person.user_id, origin=person.origin_airport, mode="Flight",
                              hours=person.travel_duration_min / 60 if person.travel_duration_min is not None else None,
                              cost=float(person.flight_cost) if person.flight_cost is not None else None,
                              lodging_allocation=float(person.lodging_allocation) if person.lodging_allocation is not None else None,
                              subtotal=float(person.estimated_subtotal) if person.estimated_subtotal is not None else None)
                    for person in candidate.participants],
            currency=candidate.currency, group_total=float(candidate.group_total),
            lodging_total=float(candidate.lodging_price.amount),
            max_travel_hours=candidate.max_travel_duration_min / 60 if candidate.max_travel_duration_min is not None else None,
            price_coverage=candidate.lodging_price.status.value, feasibility=fit.feasibility,
            pick_eligible=fit.pick_eligible, capacity_ack_required=fit.capacity_ack_required,
            warnings=list(fit.warnings), priced_at=candidate.priced_at,
            image_url=candidate.lodging_image_url if candidate.lodging_image_url and candidate.lodging_image_url.startswith(('https://','http://')) else None,
            lodging_rating=candidate.lodging_rating, lodging_review_count=candidate.lodging_review_count,
            lodging_amenities=list(candidate.lodging_amenities)[:3],
            listing_url=candidate.listing_url if candidate.listing_url and candidate.listing_url.startswith(("https://", "http://")) else None,
        ))
    return result
