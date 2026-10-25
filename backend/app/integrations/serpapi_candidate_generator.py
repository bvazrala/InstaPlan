"""Compatibility imports for the pure candidate engine in app.logic.candidates."""

from app.logic.candidates import (
    FeasibilityStatus,
    InvalidDatesError,
    LodgingCompliance,
    LodgingPrice,
    Participant,
    ParticipantTravel,
    TripCandidate,
    build_all_candidates,
    build_group_candidates,
    make_candidate_id,
)

__all__ = [
    "FeasibilityStatus", "InvalidDatesError", "LodgingCompliance", "LodgingPrice",
    "Participant", "ParticipantTravel", "TripCandidate", "build_all_candidates",
    "build_group_candidates", "make_candidate_id",
]
