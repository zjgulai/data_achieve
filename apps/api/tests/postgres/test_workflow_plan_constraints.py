from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine


@dataclass(frozen=True)
class TenantIds:
    user_id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID


@dataclass(frozen=True)
class GraphIds:
    tenant: TenantIds
    plan_id: uuid.UUID
    version_id: uuid.UUID
    scope_id: uuid.UUID
    query_term_id: uuid.UUID


@asynccontextmanager
async def _database_engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(database_url)
    try:
        yield engine
    finally:
        await engine.dispose()


async def _seed_tenant(
    connection: AsyncConnection,
    *,
    user_id: uuid.UUID | None = None,
    workspace_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
) -> TenantIds:
    tenant = TenantIds(
        user_id=user_id or uuid.uuid4(),
        workspace_id=workspace_id or uuid.uuid4(),
        project_id=project_id or uuid.uuid4(),
    )
    await connection.execute(
        text(
            """
            INSERT INTO users (id, email, password_hash, name, status)
            VALUES (:user_id, :email, 'not-a-real-password', 'PG Test User', 'active')
            """
        ),
        {"user_id": tenant.user_id, "email": f"{tenant.user_id}@example.test"},
    )
    await connection.execute(
        text(
            """
            INSERT INTO workspaces (id, name, slug, owner_id)
            VALUES (:workspace_id, 'PG Test Workspace', :slug, :user_id)
            """
        ),
        {
            "workspace_id": tenant.workspace_id,
            "slug": f"pg-test-{tenant.workspace_id}",
            "user_id": tenant.user_id,
        },
    )
    await connection.execute(
        text(
            """
            INSERT INTO projects (id, workspace_id, name, domain, status, owner_id)
            VALUES (
                :project_id,
                :workspace_id,
                'PG Test Project',
                'osint',
                'active',
                :user_id
            )
            """
        ),
        {
            "project_id": tenant.project_id,
            "workspace_id": tenant.workspace_id,
            "user_id": tenant.user_id,
        },
    )
    return tenant


async def _seed_project_in_tenant(
    connection: AsyncConnection,
    tenant: TenantIds,
) -> TenantIds:
    project_id = uuid.uuid4()
    await connection.execute(
        text(
            """
            INSERT INTO projects (id, workspace_id, name, domain, status, owner_id)
            VALUES (
                :project_id,
                :workspace_id,
                'Second PG Test Project',
                'osint',
                'active',
                :user_id
            )
            """
        ),
        {
            "project_id": project_id,
            "workspace_id": tenant.workspace_id,
            "user_id": tenant.user_id,
        },
    )
    return TenantIds(
        user_id=tenant.user_id,
        workspace_id=tenant.workspace_id,
        project_id=project_id,
    )


async def _insert_plan(
    connection: AsyncConnection,
    tenant: TenantIds,
    *,
    plan_id: uuid.UUID,
    status: str = "previewed",
    flow_mode: str = "periodic_monitoring",
) -> None:
    await connection.execute(
        text(
            """
            INSERT INTO workflow_plans (
                id,
                workspace_id,
                project_id,
                created_by_user_id,
                name,
                flow_mode,
                status,
                current_version_id
            )
            VALUES (
                :plan_id,
                :workspace_id,
                :project_id,
                :user_id,
                'PG Constraint Plan',
                :flow_mode,
                :status,
                NULL
            )
            """
        ),
        {
            "plan_id": plan_id,
            "workspace_id": tenant.workspace_id,
            "project_id": tenant.project_id,
            "user_id": tenant.user_id,
            "status": status,
            "flow_mode": flow_mode,
        },
    )


async def _insert_version(
    connection: AsyncConnection,
    tenant: TenantIds,
    *,
    plan_id: uuid.UUID,
    version_id: uuid.UUID,
    version_number: int = 1,
    planning_status: str = "resolved",
) -> None:
    await connection.execute(
        text(
            """
            INSERT INTO workflow_versions (
                id,
                workspace_id,
                project_id,
                workflow_plan_id,
                created_by_user_id,
                version_number,
                planning_status,
                planner_contract_version,
                catalog_snapshot_id,
                policy_version,
                mode_template_version,
                query_versions,
                fingerprint_payload,
                normalized_input,
                plan_payload,
                preview_fingerprint
            )
            VALUES (
                :version_id,
                :workspace_id,
                :project_id,
                :plan_id,
                :user_id,
                :version_number,
                :planning_status,
                'workflow-planner.v1',
                'catalog.v1',
                'policy.v1',
                'mode-template.v1',
                CAST(:query_versions AS JSON),
                CAST(:fingerprint_payload AS JSON),
                CAST(:normalized_input AS JSON),
                CAST(:plan_payload AS JSON),
                :preview_fingerprint
            )
            """
        ),
        {
            "version_id": version_id,
            "workspace_id": tenant.workspace_id,
            "project_id": tenant.project_id,
            "plan_id": plan_id,
            "user_id": tenant.user_id,
            "version_number": version_number,
            "planning_status": planning_status,
            "query_versions": json.dumps({"compiler": "v1"}),
            "fingerprint_payload": json.dumps({"mode": "periodic_monitoring"}),
            "normalized_input": json.dumps({"brand": "example"}),
            "plan_payload": json.dumps({"routes": []}),
            "preview_fingerprint": f"sha256:{'a' * 64}",
        },
    )


async def _insert_scope(
    connection: AsyncConnection,
    tenant: TenantIds,
    *,
    scope_id: uuid.UUID,
    scope_key: str,
    scope_type: str = "brand",
    match_mode: str = "exact",
) -> None:
    await connection.execute(
        text(
            """
            INSERT INTO monitoring_scopes (
                id,
                workspace_id,
                project_id,
                created_by_user_id,
                scope_key,
                scope_type,
                canonical_term,
                aliases,
                include_terms,
                exclude_terms,
                official_accounts,
                seed_urls,
                effective_languages,
                effective_regions,
                effective_platforms,
                match_mode
            )
            VALUES (
                :scope_id,
                :workspace_id,
                :project_id,
                :user_id,
                :scope_key,
                :scope_type,
                'example',
                CAST('[]' AS JSON),
                CAST('[]' AS JSON),
                CAST('[]' AS JSON),
                CAST('[]' AS JSON),
                CAST('[]' AS JSON),
                CAST('["en"]' AS JSON),
                CAST('["US"]' AS JSON),
                CAST('["reddit"]' AS JSON),
                :match_mode
            )
            """
        ),
        {
            "scope_id": scope_id,
            "workspace_id": tenant.workspace_id,
            "project_id": tenant.project_id,
            "user_id": tenant.user_id,
            "scope_key": scope_key,
            "scope_type": scope_type,
            "match_mode": match_mode,
        },
    )


async def _insert_version_scope(
    connection: AsyncConnection,
    tenant: TenantIds,
    *,
    version_id: uuid.UUID,
    scope_id: uuid.UUID,
    ordinal: int,
) -> None:
    await connection.execute(
        text(
            """
            INSERT INTO workflow_version_scopes (
                workspace_id,
                project_id,
                workflow_version_id,
                monitoring_scope_id,
                ordinal
            )
            VALUES (:workspace_id, :project_id, :version_id, :scope_id, :ordinal)
            """
        ),
        {
            "workspace_id": tenant.workspace_id,
            "project_id": tenant.project_id,
            "version_id": version_id,
            "scope_id": scope_id,
            "ordinal": ordinal,
        },
    )


async def _insert_query_term(
    connection: AsyncConnection,
    tenant: TenantIds,
    *,
    query_term_id: uuid.UUID,
    version_id: uuid.UUID,
    matched_scope_id: uuid.UUID | None,
    ordinal: int = 0,
    status: str = "active",
    origin: str = "canonical",
) -> None:
    await connection.execute(
        text(
            """
            INSERT INTO query_terms (
                id,
                workspace_id,
                project_id,
                workflow_version_id,
                ordinal,
                term,
                normalized_term,
                origin,
                status,
                reason,
                source,
                score,
                conflict_codes,
                matched_scope_id
            )
            VALUES (
                :query_term_id,
                :workspace_id,
                :project_id,
                :version_id,
                :ordinal,
                'Example',
                'example',
                :origin,
                :status,
                NULL,
                'canonical_term',
                1.0,
                CAST('[]' AS JSON),
                :matched_scope_id
            )
            """
        ),
        {
            "query_term_id": query_term_id,
            "workspace_id": tenant.workspace_id,
            "project_id": tenant.project_id,
            "version_id": version_id,
            "ordinal": ordinal,
            "status": status,
            "origin": origin,
            "matched_scope_id": matched_scope_id,
        },
    )


async def _create_graph(
    engine: AsyncEngine,
    *,
    tenant: TenantIds | None = None,
) -> GraphIds:
    plan_id = uuid.uuid4()
    version_id = uuid.uuid4()
    scope_id = uuid.uuid4()
    query_term_id = uuid.uuid4()
    async with engine.begin() as connection:
        selected_tenant = tenant or await _seed_tenant(connection)
        await _insert_plan(connection, selected_tenant, plan_id=plan_id)
        await _insert_version(
            connection,
            selected_tenant,
            plan_id=plan_id,
            version_id=version_id,
        )
        await _insert_scope(
            connection,
            selected_tenant,
            scope_id=scope_id,
            scope_key=uuid.uuid4().hex,
        )
        await _insert_version_scope(
            connection,
            selected_tenant,
            version_id=version_id,
            scope_id=scope_id,
            ordinal=0,
        )
        await _insert_query_term(
            connection,
            selected_tenant,
            query_term_id=query_term_id,
            version_id=version_id,
            matched_scope_id=scope_id,
        )
        await connection.execute(
            text(
                """
                UPDATE workflow_plans
                SET current_version_id = :version_id
                WHERE id = :plan_id
                """
            ),
            {"version_id": version_id, "plan_id": plan_id},
        )
    return GraphIds(
        tenant=selected_tenant,
        plan_id=plan_id,
        version_id=version_id,
        scope_id=scope_id,
        query_term_id=query_term_id,
    )


async def _insert_save_request(
    connection: AsyncConnection,
    graph: GraphIds,
    *,
    save_request_id: uuid.UUID,
    outcome: str = "created",
) -> None:
    await connection.execute(
        text(
            """
            INSERT INTO workflow_plan_save_requests (
                id,
                workspace_id,
                project_id,
                created_by_user_id,
                idempotency_scope,
                idempotency_key_hash,
                request_hash,
                workflow_plan_id,
                workflow_version_id,
                outcome,
                response_status,
                response_payload
            )
            VALUES (
                :save_request_id,
                :workspace_id,
                :project_id,
                :user_id,
                :idempotency_scope,
                :idempotency_key_hash,
                :request_hash,
                :plan_id,
                :version_id,
                :outcome,
                201,
                CAST(:response_payload AS JSON)
            )
            """
        ),
        {
            "save_request_id": save_request_id,
            "workspace_id": graph.tenant.workspace_id,
            "project_id": graph.tenant.project_id,
            "user_id": graph.tenant.user_id,
            "idempotency_scope": f"workflow_plan.create:{graph.tenant.project_id}",
            "idempotency_key_hash": f"sha256:{'b' * 64}",
            "request_hash": f"sha256:{'c' * 64}",
            "plan_id": graph.plan_id,
            "version_id": graph.version_id,
            "outcome": outcome,
            "response_payload": json.dumps({"plan_id": str(graph.plan_id)}),
        },
    )


def _sqlstate(error: DBAPIError) -> str | None:
    return getattr(error.orig, "sqlstate", None) or getattr(error.orig, "pgcode", None)


@pytest.mark.asyncio
async def test_migration_creates_six_tables_and_project_supporting_unique(
    postgres_database_url: str,
) -> None:
    expected_tables = {
        "workflow_plans",
        "workflow_versions",
        "monitoring_scopes",
        "workflow_version_scopes",
        "query_terms",
        "workflow_plan_save_requests",
    }
    async with (
        _database_engine(postgres_database_url) as engine,
        engine.connect() as connection,
    ):
        table_names = set(
            (
                await connection.execute(
                    text(
                        """
                            SELECT tablename
                            FROM pg_catalog.pg_tables
                            WHERE schemaname = 'public'
                              AND tablename = ANY(:table_names)
                            """
                    ),
                    {"table_names": sorted(expected_tables)},
                )
            ).scalars()
        )
        project_constraints = set(
            (
                await connection.execute(
                    text(
                        """
                            SELECT conname
                            FROM pg_catalog.pg_constraint
                            WHERE conrelid = 'projects'::regclass
                            """
                    )
                )
            ).scalars()
        )

    assert table_names == expected_tables
    assert "uq_projects_workspace_id" in project_constraints


@pytest.mark.asyncio
async def test_migration_creates_all_tenant_composite_foreign_keys(
    postgres_database_url: str,
) -> None:
    expected_foreign_keys = {
        "fk_workflow_plans_project_tenant",
        "fk_workflow_plans_current_version_owner",
        "fk_workflow_versions_plan_tenant",
        "fk_monitoring_scopes_project_tenant",
        "fk_workflow_version_scopes_version_tenant",
        "fk_workflow_version_scopes_scope_tenant",
        "fk_query_terms_version_scope_tenant",
        "fk_workflow_plan_save_requests_plan_tenant",
        "fk_workflow_plan_save_requests_version_tenant",
    }
    async with (
        _database_engine(postgres_database_url) as engine,
        engine.connect() as connection,
    ):
        foreign_keys = set(
            (
                await connection.execute(
                    text(
                        """
                            SELECT conname
                            FROM pg_catalog.pg_constraint
                            WHERE contype = 'f'
                              AND connamespace = 'public'::regnamespace
                            """
                    )
                )
            ).scalars()
        )

    assert expected_foreign_keys <= foreign_keys


@pytest.mark.asyncio
async def test_digest_columns_fit_prefixed_sha256_values(
    postgres_database_url: str,
) -> None:
    expected_lengths = {
        ("monitoring_scopes", "scope_key"): 71,
        ("workflow_versions", "preview_fingerprint"): 71,
        ("workflow_plan_save_requests", "idempotency_key_hash"): 71,
        ("workflow_plan_save_requests", "request_hash"): 71,
    }
    async with (
        _database_engine(postgres_database_url) as engine,
        engine.connect() as connection,
    ):
        rows = (
            await connection.execute(
                text(
                    """
                    SELECT table_name, column_name, character_maximum_length
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND (table_name, column_name) IN (
                          ('monitoring_scopes', 'scope_key'),
                          ('workflow_versions', 'preview_fingerprint'),
                          ('workflow_plan_save_requests', 'idempotency_key_hash'),
                          ('workflow_plan_save_requests', 'request_hash')
                      )
                    """
                )
            )
        ).all()

    assert {(row[0], row[1]): row[2] for row in rows} == expected_lengths


@pytest.mark.asyncio
async def test_plan_can_commit_after_null_to_owned_current_version_transition(
    postgres_database_url: str,
) -> None:
    async with _database_engine(postgres_database_url) as engine:
        graph = await _create_graph(engine)
        async with engine.connect() as connection:
            current_version_id = await connection.scalar(
                text("SELECT current_version_id FROM workflow_plans WHERE id = :plan_id"),
                {"plan_id": graph.plan_id},
            )

    assert current_version_id == graph.version_id


@pytest.mark.asyncio
async def test_plan_commit_rejects_null_current_version(
    postgres_database_url: str,
) -> None:
    async with _database_engine(postgres_database_url) as engine:
        with pytest.raises(DBAPIError) as caught:
            async with engine.begin() as connection:
                tenant = await _seed_tenant(connection)
                await _insert_plan(connection, tenant, plan_id=uuid.uuid4())

    assert _sqlstate(caught.value) == "23514"
    assert "current_version_id" in str(caught.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("target_tenant_kind", ["same_project", "other_project", "other_workspace"])
async def test_current_version_rejects_cross_plan_or_tenant_ownership(
    postgres_database_url: str,
    target_tenant_kind: str,
) -> None:
    async with _database_engine(postgres_database_url) as engine:
        source = await _create_graph(engine)
        if target_tenant_kind == "same_project":
            target = await _create_graph(engine, tenant=source.tenant)
        elif target_tenant_kind == "other_project":
            async with engine.begin() as connection:
                target_tenant = await _seed_project_in_tenant(connection, source.tenant)
            target = await _create_graph(engine, tenant=target_tenant)
        else:
            target = await _create_graph(engine)

        with pytest.raises(IntegrityError):
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        """
                        UPDATE workflow_plans
                        SET current_version_id = :version_id
                        WHERE id = :plan_id
                        """
                    ),
                    {"version_id": target.version_id, "plan_id": source.plan_id},
                )


@pytest.mark.asyncio
async def test_scope_key_is_unique_within_project(postgres_database_url: str) -> None:
    async with _database_engine(postgres_database_url) as engine:
        graph = await _create_graph(engine)
        duplicate_key = uuid.uuid4().hex
        async with engine.begin() as connection:
            await _insert_scope(
                connection,
                graph.tenant,
                scope_id=uuid.uuid4(),
                scope_key=duplicate_key,
            )
        with pytest.raises(IntegrityError):
            async with engine.begin() as connection:
                await _insert_scope(
                    connection,
                    graph.tenant,
                    scope_id=uuid.uuid4(),
                    scope_key=duplicate_key,
                )


@pytest.mark.asyncio
async def test_scope_ordinal_is_unique_within_version(postgres_database_url: str) -> None:
    async with _database_engine(postgres_database_url) as engine:
        graph = await _create_graph(engine)
        second_scope_id = uuid.uuid4()
        async with engine.begin() as connection:
            await _insert_scope(
                connection,
                graph.tenant,
                scope_id=second_scope_id,
                scope_key=uuid.uuid4().hex,
            )
        with pytest.raises(IntegrityError):
            async with engine.begin() as connection:
                await _insert_version_scope(
                    connection,
                    graph.tenant,
                    version_id=graph.version_id,
                    scope_id=second_scope_id,
                    ordinal=0,
                )


@pytest.mark.asyncio
@pytest.mark.parametrize("association_kind", ["null", "not_associated"])
async def test_query_term_requires_scope_associated_to_same_version(
    postgres_database_url: str,
    association_kind: str,
) -> None:
    async with _database_engine(postgres_database_url) as engine:
        graph = await _create_graph(engine)
        matched_scope_id: uuid.UUID | None = None
        if association_kind == "not_associated":
            matched_scope_id = uuid.uuid4()
            async with engine.begin() as connection:
                await _insert_scope(
                    connection,
                    graph.tenant,
                    scope_id=matched_scope_id,
                    scope_key=uuid.uuid4().hex,
                )

        with pytest.raises(IntegrityError):
            async with engine.begin() as connection:
                await _insert_query_term(
                    connection,
                    graph.tenant,
                    query_term_id=uuid.uuid4(),
                    version_id=graph.version_id,
                    matched_scope_id=matched_scope_id,
                    ordinal=1,
                )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("invalid_kind", "invalid_value"),
    [
        ("plan_status", "unknown"),
        ("flow_mode", "unknown"),
        ("planning_status", "partial"),
        ("scope_type", "unknown"),
        ("match_mode", "fuzzy"),
        ("query_status", "held"),
        ("query_origin", "unknown"),
        ("save_outcome", "replayed"),
    ],
)
async def test_allowed_value_checks_reject_unknown_values(
    postgres_database_url: str,
    invalid_kind: str,
    invalid_value: str,
) -> None:
    async with _database_engine(postgres_database_url) as engine:
        if invalid_kind in {"plan_status", "flow_mode"}:
            with pytest.raises(IntegrityError):
                async with engine.begin() as connection:
                    tenant = await _seed_tenant(connection)
                    await _insert_plan(
                        connection,
                        tenant,
                        plan_id=uuid.uuid4(),
                        status=invalid_value if invalid_kind == "plan_status" else "previewed",
                        flow_mode=(
                            invalid_value if invalid_kind == "flow_mode" else "periodic_monitoring"
                        ),
                    )
            return

        graph = await _create_graph(engine)
        with pytest.raises(IntegrityError):
            async with engine.begin() as connection:
                if invalid_kind == "planning_status":
                    await _insert_version(
                        connection,
                        graph.tenant,
                        plan_id=graph.plan_id,
                        version_id=uuid.uuid4(),
                        version_number=2,
                        planning_status=invalid_value,
                    )
                elif invalid_kind in {"scope_type", "match_mode"}:
                    await _insert_scope(
                        connection,
                        graph.tenant,
                        scope_id=uuid.uuid4(),
                        scope_key=uuid.uuid4().hex,
                        scope_type=invalid_value if invalid_kind == "scope_type" else "brand",
                        match_mode=invalid_value if invalid_kind == "match_mode" else "exact",
                    )
                elif invalid_kind in {"query_status", "query_origin"}:
                    await _insert_query_term(
                        connection,
                        graph.tenant,
                        query_term_id=uuid.uuid4(),
                        version_id=graph.version_id,
                        matched_scope_id=graph.scope_id,
                        ordinal=1,
                        status=invalid_value if invalid_kind == "query_status" else "active",
                        origin=invalid_value if invalid_kind == "query_origin" else "canonical",
                    )
                else:
                    await _insert_save_request(
                        connection,
                        graph,
                        save_request_id=uuid.uuid4(),
                        outcome=invalid_value,
                    )


@pytest.mark.asyncio
async def test_history_tables_have_immutable_triggers(postgres_database_url: str) -> None:
    expected_triggers = {
        "trg_workflow_versions_immutable",
        "trg_monitoring_scopes_immutable",
        "trg_workflow_version_scopes_immutable",
        "trg_query_terms_immutable",
        "trg_workflow_plan_save_requests_immutable",
    }
    async with (
        _database_engine(postgres_database_url) as engine,
        engine.connect() as connection,
    ):
        trigger_names = set(
            (
                await connection.execute(
                    text(
                        """
                            SELECT tgname
                            FROM pg_catalog.pg_trigger
                            WHERE NOT tgisinternal
                              AND tgrelid IN (
                                  'workflow_versions'::regclass,
                                  'monitoring_scopes'::regclass,
                                  'workflow_version_scopes'::regclass,
                                  'query_terms'::regclass,
                                  'workflow_plan_save_requests'::regclass
                              )
                            """
                    )
                )
            ).scalars()
        )

    assert trigger_names == expected_triggers


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("table_name", "identity_column", "identity_attr", "mutation"),
    [
        ("workflow_versions", "id", "version_id", "preview_fingerprint = 'd'"),
        ("monitoring_scopes", "id", "scope_id", "canonical_term = 'changed'"),
        (
            "workflow_version_scopes",
            "workflow_version_id",
            "version_id",
            "ordinal = 1",
        ),
        ("query_terms", "id", "query_term_id", "term = 'changed'"),
        (
            "workflow_plan_save_requests",
            "id",
            "save_request_id",
            "response_status = 200",
        ),
    ],
)
async def test_history_tables_reject_updates(
    postgres_database_url: str,
    table_name: str,
    identity_column: str,
    identity_attr: str,
    mutation: str,
) -> None:
    async with _database_engine(postgres_database_url) as engine:
        graph = await _create_graph(engine)
        save_request_id = uuid.uuid4()
        async with engine.begin() as connection:
            await _insert_save_request(
                connection,
                graph,
                save_request_id=save_request_id,
            )
        identity_value = (
            save_request_id if identity_attr == "save_request_id" else getattr(graph, identity_attr)
        )

        with pytest.raises(DBAPIError) as caught:
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        f"UPDATE {table_name} SET {mutation} "
                        f"WHERE {identity_column} = :identity_value"
                    ),
                    {"identity_value": identity_value},
                )

        assert _sqlstate(caught.value) == "55000"
        assert "immutable" in str(caught.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("table_name", "identity_column", "identity_attr"),
    [
        ("workflow_versions", "id", "version_id"),
        ("monitoring_scopes", "id", "scope_id"),
        ("workflow_version_scopes", "workflow_version_id", "version_id"),
        ("query_terms", "id", "query_term_id"),
        ("workflow_plan_save_requests", "id", "save_request_id"),
    ],
)
async def test_history_tables_reject_deletes(
    postgres_database_url: str,
    table_name: str,
    identity_column: str,
    identity_attr: str,
) -> None:
    async with _database_engine(postgres_database_url) as engine:
        graph = await _create_graph(engine)
        save_request_id = uuid.uuid4()
        async with engine.begin() as connection:
            await _insert_save_request(
                connection,
                graph,
                save_request_id=save_request_id,
            )
        identity_value = (
            save_request_id if identity_attr == "save_request_id" else getattr(graph, identity_attr)
        )

        with pytest.raises(DBAPIError) as caught:
            async with engine.begin() as connection:
                await connection.execute(
                    text(f"DELETE FROM {table_name} WHERE {identity_column} = :identity_value"),
                    {"identity_value": identity_value},
                )

        assert _sqlstate(caught.value) == "55000"
        assert "immutable" in str(caught.value)
