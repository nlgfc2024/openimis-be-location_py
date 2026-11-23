"""Provider-neutral geographic validation and local delivery. No network access."""
import math

MAX_POINTS = 100000

def safe_geojson(body):
    """Render polygon geometry only, excluding arbitrary source properties."""
    if not isinstance(body, dict):
        raise ValueError("Invalid GeoJSON")
    features = body.get("features") if body.get("type") == "FeatureCollection" else [body]
    if not isinstance(features, list) or len(features) > 10000:
        raise ValueError("Invalid GeoJSON features")
    output, count = [], 0
    for feature in features:
        if not isinstance(feature, dict):
            raise ValueError("Invalid feature")
        geometry = feature.get("geometry") if feature.get("type") == "Feature" else feature
        if not isinstance(geometry, dict) or geometry.get("type") not in ("Polygon", "MultiPolygon"):
            raise ValueError("Only polygon publications are supported")
        coordinates = geometry.get("coordinates")
        polygons = [coordinates] if geometry["type"] == "Polygon" else coordinates
        if not isinstance(polygons, list) or not polygons:
            raise ValueError("Invalid polygons")
        for polygon in polygons:
            if not isinstance(polygon, list) or not polygon:
                raise ValueError("Invalid rings")
            for ring in polygon:
                if not isinstance(ring, list) or len(ring) < 4 or ring[0] != ring[-1]:
                    raise ValueError("Invalid closed ring")
                for point in ring:
                    count += 1
                    if (count > MAX_POINTS or not isinstance(point, list) or len(point) != 2
                            or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in point)
                            or not -180 <= point[0] <= 180 or not -85 <= point[1] <= 85):
                        raise ValueError("Invalid or excessive coordinates")
        output.append({"type": "Feature", "properties": {},
                       "geometry": {"type": geometry["type"], "coordinates": geometry["coordinates"]}})
    return {"type": "FeatureCollection", "features": output}



def local_geometry(feature):
    geometry = None
    status = feature.publication_status
    if feature.geometry is not None:
        try:
            geometry = safe_geojson(feature.geometry)
            status = 'available'
        except (ValueError, TypeError):
            status = 'invalid_local_geometry'
    return {"status": status,
            "revision": str(feature.geometry_revision if feature.geometry_revision is not None else feature.observed_revision),
            "relation": feature.geometry_relation, "source": feature.geometry_source,
            "geojson": geometry, "refresh_status": feature.refresh_status}


def legacy_reference_key(reference_id):
    """Resolve the historical CoreMIS reference ID without network access."""
    from location.models import MsrLocationReference
    row = MsrLocationReference.objects.filter(pk=reference_id).values('source_instance','msr_type','msr_id').first()
    if row is None:
        return None
    return {'source_instance':row['source_instance'], 'external_type':row['msr_type'], 'external_id':str(row['msr_id'])}

def legacy_geometry(reference):
    """Legacy display API reads the accepted CoreMIS copy; never contacts MSR."""
    from location.models import GeographicFeature
    feature = GeographicFeature.objects.filter(source_instance=reference.source_instance,
        external_type=reference.msr_type, external_id=str(reference.msr_id)).first()
    if feature is None:
        return {"status": "not_downloaded", "revision": str(reference.revision),
                "relation": reference.geometry_relation, "source": reference.geometry_source, "geojson": None}
    result = local_geometry(feature)
    result.pop("refresh_status", None)
    return result
