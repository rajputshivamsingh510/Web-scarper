"""Overture Maps Places (free, open data, CDLA-Permissive-2.0 for most sources).

Reads the public GeoParquet release directly with DuckDB. Only the rows inside the
bounding box are downloaded (parquet filter push-down), so no API key or per-request
fee is involved.
Docs: https://docs.overturemaps.org/guides/places
Attribution: "(c) Overture Maps Foundation, overturemaps.org" - https://docs.overturemaps.org/attribution/
"""
from __future__ import annotations

import logging
from typing import Iterable

from ..geocode import bbox_for
from ..models import Lead
from ..normalize import normalize_phones
from .base import Source, SearchSpec

log = logging.getLogger("leadcollector.overture")
ATTRIBUTION = "(c) Overture Maps Foundation, overturemaps.org (places theme, mostly CDLA-Permissive-2.0)"


def _connect(path: str):
    import duckdb
    con = duckdb.connect()
    if path.startswith("s3://"):
        con.execute("INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';")
    return con


def _path(cfg) -> str:
    if cfg.overture_path:
        return cfg.overture_path
    return f"s3://overturemaps-us-west-2/release/{cfg.overture_release}/theme=places/type=place/*"


def _category_expr(con, src: str) -> str:
    cols = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {src}").fetchall()}
    if "taxonomy" in cols:
        return "taxonomy.primary"
    if "categories" in cols:
        return "categories.primary"
    raise RuntimeError("Overture file has neither 'taxonomy' nor 'categories' columns")


def list_categories(cfg, bbox, top: int = 40):
    path = _path(cfg)
    con = _connect(path)
    src = f"read_parquet('{path}', hive_partitioning=1)"
    cat = _category_expr(con, src)
    s, w, n, e = bbox
    return con.execute(
        f"SELECT {cat} AS c, count(*) AS n FROM {src} "
        "WHERE bbox.xmin BETWEEN ? AND ? AND bbox.ymin BETWEEN ? AND ? "
        "GROUP BY c ORDER BY n DESC LIMIT ?", [w, e, s, n, top]).fetchall()


class OvertureSource(Source):
    name = "overture"

    def collect(self, spec: SearchSpec, limit: int) -> Iterable[Lead]:
        bbox = spec.bbox or bbox_for(self.client, spec.city, spec.state, self.cfg.data_dir / "cache")
        s, w, n, e = bbox
        terms = spec.category.overture
        if not terms:
            raise ValueError("No Overture category terms. Use --overture-term, see 'overture-categories'.")
        path = _path(self.cfg)
        log.info("Reading Overture places from %s (bbox=%s)", "local file" if not path.startswith("s3://") else "S3", bbox)
        con = _connect(path)
        src = f"read_parquet('{path}', hive_partitioning=1)"
        cat = _category_expr(con, src)
        like = " OR ".join([f"{cat} ILIKE ?"] * len(terms))
        # NOTE: no ORDER BY/LIMIT and no bbox.<field> in the SELECT list. Some DuckDB versions crash
        # ("Vector::Reference used on vector of different type") on that combination. The rows are
        # already limited by the bbox + category filters, so sorting/limiting is done in Python.
        sql = (
            f"SELECT id, names.primary, {cat}, phones, websites, addresses, confidence, "
            f"operating_status, bbox FROM {src} "
            "WHERE bbox.xmin BETWEEN ? AND ? AND bbox.ymin BETWEEN ? AND ? "
            "AND (operating_status IS NULL OR operating_status = 'open') "
            f"AND coalesce(confidence, 0) >= ? AND ({like})"
        )
        params = [w, e, s, n, spec.min_confidence] + [f"%{t}%" for t in terms]
        rows = con.execute(sql, params).fetchall()
        rows.sort(key=lambda r: -(float(r[6]) if r[6] is not None else 0.0))
        log.info("Overture matched %d places in the area", len(rows))
        for (pid, name, category, phones, websites, addresses, conf, _st, bb) in rows[:limit]:
            bb = bb or {}
            x0, x1, y0, y1 = bb.get("xmin"), bb.get("xmax"), bb.get("ymin"), bb.get("ymax")
            if not name:
                continue
            addr = (addresses or [{}])[0] or {}
            freeform = ", ".join(x for x in (addr.get("freeform"), addr.get("locality"),
                                             addr.get("postcode")) if x)
            phone_list = normalize_phones(phones or [])
            yield Lead(
                business_name=name.strip(),
                phone=phone_list[0] if phone_list else "",
                extra_phones=";".join(phone_list[1:3]),
                website=(websites or [""])[0] or "",
                category=spec.category.label,
                city=addr.get("locality") or spec.city,
                address=freeform,
                source=self.name,
                source_id=str(pid),
                source_url="",
                attribution=ATTRIBUTION,
                phone_source=self.name if phone_list else "",
                confidence=float(conf) if conf is not None else None,
                lat=float(y0 + y1) / 2 if y0 is not None else None,
                lon=float(x0 + x1) / 2 if x0 is not None else None,
            )