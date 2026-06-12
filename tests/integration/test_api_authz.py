"""Cross-tenant authorization regression suite (tenant scoping).

These tests encode the trust model: a non-admin user may only see or mutate
objects they own (``created_by``, derived through the parent campaign for
assets/jobs/compliance/metrics); admins may access anything. Every cross-tenant
access must return **404** (never 200, and not 403 — a 403 would confirm the
object exists).

They run against the REAL Postgres harness (``real_app_client``) so the
SQL-level scoping (WHERE clauses, subqueries) is what's actually exercised —
a mocked session cannot catch a missing filter.

This suite exists because the original BOLA finding (any authenticated user
could read/modify any other user's data by UUID) shipped despite 450+ tests:
none asserted cross-tenant isolation. Do not delete or weaken these.
"""

from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime

import pytest
from src.api.dependencies import create_access_token

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def _seed_user(session, role: str):
    """Seed a real user; return (auth_headers, user_id)."""
    from src.db.models import User

    user = User(
        id=_uuid.uuid4(),
        email=f"authz-{_uuid.uuid4().hex[:10]}@example.com",
        password_hash="$2b$12$placeholder.hash.value.not.used.for.jwt.login.flow",
        display_name=f"Authz {role}",
        role=role,
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(user)
    await session.flush()
    headers = {"Authorization": f"Bearer {create_access_token(str(user.id), role)}"}
    return headers, user.id


async def _seed_campaign_graph(session, owner_id):
    """Seed a campaign owned by *owner_id* plus one job, asset and report.

    Returns a dict of string ids for use in request paths.
    """
    from src.db.models import Campaign, ComplianceReport, GeneratedAsset, Job

    now = datetime.now(UTC)
    campaign = Campaign(
        id=_uuid.uuid4(),
        campaign_id=f"AZ-{_uuid.uuid4().hex[:8]}",
        campaign_name="Tenant A campaign",
        brand_name="TenantBrand",
        status="draft",
        image_backend="firefly",
        brief={"headline": "Private"},
        target_locales=["en-US"],
        aspect_ratios=["1:1"],
        created_by=owner_id,
        created_at=now,
        updated_at=now,
    )
    session.add(campaign)
    await session.flush()

    job = Job(id=_uuid.uuid4(), campaign_id=campaign.id, status="queued", progress_percent=0, created_at=now)
    asset = GeneratedAsset(
        id=_uuid.uuid4(),
        campaign_id=campaign.id,
        product_id="P-1",
        locale="en-US",
        aspect_ratio="1:1",
        file_path="/output/private.png",
        storage_key=f"campaigns/{campaign.campaign_id}/private.png",
        generation_method="firefly",
        created_at=now,
    )
    report = ComplianceReport(
        id=_uuid.uuid4(),
        campaign_id=campaign.id,
        is_compliant=True,
        violations=[],
        summary={"status": "checked"},
        checked_at=now,
    )
    session.add_all([job, asset, report])
    await session.flush()

    return {
        "campaign_id": str(campaign.id),
        "job_id": str(job.id),
        "asset_id": str(asset.id),
    }


async def _seed_brand(session, owner_id) -> str:
    from src.db.models import BrandGuideline

    now = datetime.now(UTC)
    brand = BrandGuideline(
        id=_uuid.uuid4(),
        name=f"Brand-{_uuid.uuid4().hex[:8]}",
        primary_colors=["#000000"],
        secondary_colors=[],
        primary_font="Arial",
        created_by=owner_id,
        created_at=now,
        updated_at=now,
    )
    session.add(brand)
    await session.flush()
    return str(brand.id)


# ---------------------------------------------------------------------------
# Cross-tenant DETAIL/MUTATION access is a 404
# ---------------------------------------------------------------------------


CROSS_TENANT_CASES = [
    ("get", "/api/v1/campaigns/{campaign_id}"),
    ("patch", "/api/v1/campaigns/{campaign_id}"),
    ("post", "/api/v1/campaigns/{campaign_id}/reprocess"),
    ("get", "/api/v1/campaigns/{campaign_id}/assets"),
    ("get", "/api/v1/campaigns/{campaign_id}/compliance"),
    ("post", "/api/v1/campaigns/{campaign_id}/compliance/check"),
    ("post", "/api/v1/campaigns/{campaign_id}/compliance/approve"),
    ("get", "/api/v1/campaigns/{campaign_id}/metrics"),
    ("get", "/api/v1/assets/{asset_id}"),
    ("get", "/api/v1/assets/{asset_id}/download"),
    ("get", "/api/v1/jobs/{job_id}"),
    ("post", "/api/v1/jobs/{job_id}/cancel"),
]


@pytest.mark.parametrize("method,path_tmpl", CROSS_TENANT_CASES)
async def test_cross_tenant_access_is_404(real_app_client, method, path_tmpl):
    """An editor in tenant B gets 404 (not 200/403) on tenant A's objects."""
    client, session = real_app_client
    _, owner_id = await _seed_user(session, "editor")
    intruder_headers, _ = await _seed_user(session, "editor")
    ids = await _seed_campaign_graph(session, owner_id)

    path = path_tmpl.format(**ids)
    kwargs = {"headers": intruder_headers}
    if method == "patch":
        kwargs["json"] = {"campaign_name": "hijacked"}
    resp = await getattr(client, method)(path, **kwargs)

    assert resp.status_code == 404, f"{method.upper()} {path} -> {resp.status_code}: {resp.text}"


async def test_cross_tenant_brand_access_is_404(real_app_client):
    client, session = real_app_client
    _, owner_id = await _seed_user(session, "editor")
    intruder_headers, _ = await _seed_user(session, "editor")
    brand_id = await _seed_brand(session, owner_id)

    r_get = await client.get(f"/api/v1/brands/{brand_id}", headers=intruder_headers)
    r_patch = await client.patch(f"/api/v1/brands/{brand_id}", json={"name": "stolen"}, headers=intruder_headers)
    assert r_get.status_code == 404, r_get.text
    assert r_patch.status_code == 404, r_patch.text


async def test_owner_retains_access(real_app_client):
    """Scoping must not lock the owner out of their own objects."""
    client, session = real_app_client
    owner_headers, owner_id = await _seed_user(session, "editor")
    ids = await _seed_campaign_graph(session, owner_id)

    for path in (
        f"/api/v1/campaigns/{ids['campaign_id']}",
        f"/api/v1/jobs/{ids['job_id']}",
        f"/api/v1/assets/{ids['asset_id']}",
        f"/api/v1/campaigns/{ids['campaign_id']}/assets",
        f"/api/v1/campaigns/{ids['campaign_id']}/compliance",
        f"/api/v1/campaigns/{ids['campaign_id']}/metrics",
    ):
        resp = await client.get(path, headers=owner_headers)
        assert resp.status_code == 200, f"GET {path} -> {resp.status_code}: {resp.text}"


async def test_admin_can_access_any_object(real_app_client):
    """Admins are the support/ops escape hatch: they may access any object."""
    client, session = real_app_client
    _, owner_id = await _seed_user(session, "editor")
    admin_headers, _ = await _seed_user(session, "admin")
    ids = await _seed_campaign_graph(session, owner_id)

    resp = await client.get(f"/api/v1/campaigns/{ids['campaign_id']}", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    resp = await client.get(f"/api/v1/jobs/{ids['job_id']}", headers=admin_headers)
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# LIST endpoints are tenant-scoped
# ---------------------------------------------------------------------------


async def test_list_campaigns_excludes_other_tenants(real_app_client):
    client, session = real_app_client
    _, owner_id = await _seed_user(session, "editor")
    intruder_headers, _ = await _seed_user(session, "editor")
    ids = await _seed_campaign_graph(session, owner_id)

    resp = await client.get("/api/v1/campaigns", headers=intruder_headers)
    assert resp.status_code == 200
    listed_ids = {item["id"] for item in resp.json()["data"]}
    assert ids["campaign_id"] not in listed_ids
    assert resp.json()["meta"]["total"] == 0


async def test_list_jobs_excludes_other_tenants(real_app_client):
    client, session = real_app_client
    _, owner_id = await _seed_user(session, "editor")
    intruder_headers, _ = await _seed_user(session, "editor")
    ids = await _seed_campaign_graph(session, owner_id)

    resp = await client.get("/api/v1/jobs", headers=intruder_headers)
    assert resp.status_code == 200
    assert ids["job_id"] not in {item["id"] for item in resp.json()["data"]}


async def test_list_brands_excludes_other_tenants(real_app_client):
    client, session = real_app_client
    _, owner_id = await _seed_user(session, "editor")
    intruder_headers, _ = await _seed_user(session, "editor")
    brand_id = await _seed_brand(session, owner_id)

    resp = await client.get("/api/v1/brands", headers=intruder_headers)
    assert resp.status_code == 200
    assert brand_id not in {item["id"] for item in resp.json()["data"]}


async def test_null_owned_campaign_is_admin_only(real_app_client):
    """Legacy rows with NULL created_by are visible to admins, nobody else."""
    from src.db.models import Campaign

    client, session = real_app_client
    user_headers, _ = await _seed_user(session, "editor")
    admin_headers, _ = await _seed_user(session, "admin")

    now = datetime.now(UTC)
    legacy = Campaign(
        id=_uuid.uuid4(),
        campaign_id=f"LEGACY-{_uuid.uuid4().hex[:8]}",
        campaign_name="Unowned legacy row",
        brand_name="Old",
        status="draft",
        image_backend="firefly",
        brief={},
        target_locales=["en-US"],
        aspect_ratios=["1:1"],
        created_by=None,
        created_at=now,
        updated_at=now,
    )
    session.add(legacy)
    await session.flush()

    r_user = await client.get(f"/api/v1/campaigns/{legacy.id}", headers=user_headers)
    r_admin = await client.get(f"/api/v1/campaigns/{legacy.id}", headers=admin_headers)
    assert r_user.status_code == 404, r_user.text
    assert r_admin.status_code == 200, r_admin.text


# ---------------------------------------------------------------------------
# Aggregates and caches must not leak across tenants
# ---------------------------------------------------------------------------


async def test_aggregate_metrics_scoped_to_caller(real_app_client):
    """A user who owns nothing sees zeroed aggregates even when other
    tenants have campaigns — totals must not leak activity volumes."""
    client, session = real_app_client
    _, owner_id = await _seed_user(session, "editor")
    intruder_headers, _ = await _seed_user(session, "editor")
    await _seed_campaign_graph(session, owner_id)

    resp = await client.get("/api/v1/metrics/aggregate", headers=intruder_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_campaigns"] == 0
    assert data["total_assets"] == 0
    assert data["campaigns_by_status"] == {}


async def test_detail_cache_hit_does_not_bypass_scoping(real_app_client):
    """The campaign-detail cache key is shared across users; a cache entry
    populated by the owner's read must still 404 for another user."""
    client, session = real_app_client
    owner_headers, owner_id = await _seed_user(session, "editor")
    intruder_headers, _ = await _seed_user(session, "editor")
    ids = await _seed_campaign_graph(session, owner_id)

    # Owner read populates the shared detail cache entry.
    r_owner = await client.get(f"/api/v1/campaigns/{ids['campaign_id']}", headers=owner_headers)
    assert r_owner.status_code == 200, r_owner.text

    # Intruder read immediately after MUST NOT be served from that entry.
    r_intruder = await client.get(f"/api/v1/campaigns/{ids['campaign_id']}", headers=intruder_headers)
    assert r_intruder.status_code == 404, r_intruder.text
