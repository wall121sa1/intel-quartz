import json
import math
from datetime import datetime
from typing import Iterable, List

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderServiceError

from app.models import db, LocationResolution


class GeoResolver:
    geolocator = Nominatim(user_agent="obsidian_ingest_geo_resolver")

    @staticmethod
    def _geocode_candidates(name: str, limit: int = 3) -> List[dict]:
        try:
            results = GeoResolver.geolocator.geocode(
                name, exactly_one=False, limit=limit, timeout=10
            )
        except GeocoderServiceError:
            return []
        except Exception:
            return []

        candidates = []
        for result in results or []:
            candidates.append(
                {
                    "label": getattr(result, "address", name),
                    "latitude": result.latitude,
                    "longitude": result.longitude,
                }
            )
        return candidates

    @staticmethod
    def _is_conflict(record: LocationResolution, suggestion: dict, threshold_km: float = 20.0) -> bool:
        if record.latitude is None or record.longitude is None:
            return False

        def haversine(lat1, lon1, lat2, lon2):
            r = 6371
            phi1, phi2 = math.radians(lat1), math.radians(lat2)
            d_phi = math.radians(lat2 - lat1)
            d_lambda = math.radians(lon2 - lon1)

            a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            return r * c

        distance = haversine(
            record.latitude,
            record.longitude,
            suggestion.get("latitude"),
            suggestion.get("longitude"),
        )
        return distance > threshold_km

    @staticmethod
    def _upsert_location(name: str) -> bool:
        clean_name = (name or "").strip()
        if not clean_name:
            return False

        record = LocationResolution.query.filter_by(name=clean_name).first()
        created = False
        changed = False
        if not record:
            record = LocationResolution(name=clean_name)
            db.session.add(record)
            created = True
            changed = True

        candidates = GeoResolver._geocode_candidates(clean_name)
        primary = candidates[0] if candidates else None
        candidates_json = json.dumps(candidates, ensure_ascii=False)
        if record.candidates_json != candidates_json:
            record.candidates_json = candidates_json
            changed = True
        record.updated_at = datetime.utcnow()

        if primary and record.source != "manual":
            if record.latitude != primary["latitude"] or record.longitude != primary["longitude"]:
                changed = True
            record.latitude = primary["latitude"]
            record.longitude = primary["longitude"]
            record.source = "auto"

        new_note = record.note
        needs_review = record.needs_review
        if record.source == "manual" and primary and GeoResolver._is_conflict(record, primary):
            needs_review = True
            new_note = "Manual coordinates differ from the latest automatic geocode suggestion."
        elif not primary:
            needs_review = True
            new_note = "No automatic geocode match found; set coordinates manually."
        elif len(candidates) > 1:
            needs_review = True
            new_note = "Multiple possible matches found; confirm the correct location."
        else:
            needs_review = False
            new_note = None

        if record.needs_review != needs_review or record.note != new_note:
            record.needs_review = needs_review
            record.note = new_note
            changed = True

        return changed

    @staticmethod
    def ensure_locations(location_names: Iterable[str]):
        normalized = {name.strip() for name in location_names or [] if name and name.strip()}
        if not normalized:
            return

        changed = False
        for name in normalized:
            changed = GeoResolver._upsert_location(name) or changed

        if changed:
            db.session.commit()

    @staticmethod
    def refresh_record(record: LocationResolution):
        updated = GeoResolver._upsert_location(record.name)
        if updated:
            db.session.commit()

    @staticmethod
    def save_manual_resolution(record: LocationResolution, latitude: float, longitude: float):
        record.latitude = latitude
        record.longitude = longitude
        record.source = "manual"
        record.needs_review = False
        record.note = None
        record.updated_at = datetime.utcnow()
        db.session.commit()

    @staticmethod
    def export_resolutions(names: Iterable[str]) -> List[dict]:
        normalized = {name.strip() for name in names or [] if name and name.strip()}
        if not normalized:
            return []

        records = (
            LocationResolution.query.filter(LocationResolution.name.in_(normalized))
            .order_by(LocationResolution.name)
            .all()
        )
        payloads = []
        for record in records:
            payload = record.to_payload()
            if payload:
                payloads.append(payload)
        return payloads

    @staticmethod
    def csv_to_list(csv_string: str) -> List[str]:
        if not csv_string:
            return []
        return [item.strip() for item in csv_string.split(',') if item.strip()]
