from __future__ import annotations

import uuid
from pathlib import Path

from backend.models.action import Action
from backend.models.action_finding import ActionFinding
from backend.models.finding import Finding
from backend.models.security_graph_edge import SecurityGraphEdge
from backend.models.security_graph_node import SecurityGraphNode
from backend.services.action_scoring import score_action_finding
from backend.services import security_graph as security_graph_service


_MIGRATION_PATH = Path("alembic/versions/0041_security_graph_foundation.py")


class _FakeSession:
    def __init__(self, actions: list[Action]) -> None:
        self.actions = actions
        self.nodes: list[SecurityGraphNode] = []
        self.edges: list[SecurityGraphEdge] = []

    def add(self, obj: object) -> None:
        if isinstance(obj, SecurityGraphNode):
            self.nodes.append(obj)
        elif isinstance(obj, SecurityGraphEdge):
            self.edges.append(obj)
        else:  # pragma: no cover - defensive test guard
            raise AssertionError(f"unexpected add type: {type(obj)!r}")

    def delete(self, obj: object) -> None:
        if isinstance(obj, SecurityGraphEdge):
            self.edges = [edge for edge in self.edges if edge is not obj]
            return
        if isinstance(obj, SecurityGraphNode):
            self.nodes = [node for node in self.nodes if node is not obj]
            self.edges = [
                edge
                for edge in self.edges
                if edge.source_node_id != obj.id and edge.target_node_id != obj.id
            ]
            return
        raise AssertionError(f"unexpected delete type: {type(obj)!r}")


def _constraint_names(model: type) -> set[str]:
    return {constraint.name for constraint in model.__table__.constraints if constraint.name}


def _index_names(model: type) -> set[str]:
    return {index.name for index in model.__table__.indexes if index.name}


def _finding(
    *,
    tenant_id: uuid.UUID,
    account_id: str,
    finding_id: str,
    control_id: str,
    title: str,
    description: str,
    resource_id: str,
    resource_type: str,
    region: str = "us-east-1",
) -> Finding:
    return Finding(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        account_id=account_id,
        region=region,
        finding_id=finding_id,
        source="security_hub",
        severity_label="HIGH",
        severity_normalized=75,
        title=title,
        description=description,
        resource_id=resource_id,
        resource_type=resource_type,
        control_id=control_id,
        status="NEW",
        in_scope=True,
        raw_json={
            "relationship_context": {
                "complete": True,
                "confidence": 1.0,
                "account_id": account_id,
                "region": region,
                "resource_id": resource_id,
                "resource_type": resource_type,
            }
        },
    )


def _action(
    *,
    tenant_id: uuid.UUID,
    account_id: str,
    action_type: str,
    target_id: str,
    finding: Finding,
) -> Action:
    score = score_action_finding(finding)
    action = Action(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        action_type=action_type,
        target_id=target_id,
        account_id=account_id,
        region=finding.region,
        score=score.score,
        score_components=score.components,
        priority=score.score,
        status="open",
        title=finding.title,
        description=finding.description,
        control_id=finding.control_id,
        resource_id=finding.resource_id,
        resource_type=finding.resource_type,
        owner_type="unassigned",
        owner_key="unassigned",
        owner_label="Unassigned",
    )
    action.action_finding_links = [ActionFinding(finding=finding)]
    return action


def _patch_graph_store(monkeypatch, session: _FakeSession) -> None:
    monkeypatch.setattr(
        security_graph_service,
        "_scoped_actions",
        lambda _db, tenant_id, account_id=None, region=None: [
            action
            for action in session.actions
            if action.tenant_id == tenant_id
            and (account_id is None or action.account_id == account_id)
            and (region is None or action.region == region)
        ],
    )
    monkeypatch.setattr(
        security_graph_service,
        "_existing_nodes_by_key",
        lambda _db, tenant_id, node_keys: {
            node.node_key: node
            for node in session.nodes
            if node.tenant_id == tenant_id and node.node_key in set(node_keys)
        },
    )
    monkeypatch.setattr(
        security_graph_service,
        "_existing_edges_by_key",
        lambda _db, tenant_id, edge_keys: {
            edge.edge_key: edge
            for edge in session.edges
            if edge.tenant_id == tenant_id and edge.edge_key in set(edge_keys)
        },
    )
    monkeypatch.setattr(
        security_graph_service,
        "_scoped_nodes",
        lambda _db, tenant_id, account_id=None, region=None: [
            node
            for node in session.nodes
            if node.tenant_id == tenant_id
            and (account_id is None or node.account_id == account_id)
            and (region is None or node.region == region)
        ],
    )
    monkeypatch.setattr(
        security_graph_service,
        "_scoped_edges",
        lambda _db, tenant_id, account_id=None, region=None: [
            edge
            for edge in session.edges
            if edge.tenant_id == tenant_id
            and (account_id is None or edge.account_id == account_id)
            and (region is None or edge.region == region)
        ],
    )


def test_security_graph_models_have_tenant_scoped_uniques_and_indexes() -> None:
    assert "uq_security_graph_nodes_tenant_key" in _constraint_names(SecurityGraphNode)
    assert "uq_security_graph_edges_tenant_key" in _constraint_names(SecurityGraphEdge)
    assert "ix_security_graph_nodes_tenant_type_account_region" in _index_names(SecurityGraphNode)
    assert "ix_security_graph_edges_tenant_type_account_region" in _index_names(SecurityGraphEdge)
    assert "ix_security_graph_edges_tenant_source" in _index_names(SecurityGraphEdge)
    assert "ix_security_graph_edges_tenant_target" in _index_names(SecurityGraphEdge)


def test_security_graph_migration_creates_graph_tables_and_constraints() -> None:
    text = _MIGRATION_PATH.read_text(encoding="utf-8")

    assert '"security_graph_nodes"' in text
    assert '"security_graph_edges"' in text
    assert "uq_security_graph_nodes_tenant_key" in text
    assert "uq_security_graph_edges_tenant_key" in text
    assert "ix_security_graph_nodes_tenant_type_account_region" in text
    assert "ix_security_graph_edges_tenant_type_account_region" in text
    assert 'op.drop_table("security_graph_edges")' in text
    assert 'op.drop_table("security_graph_nodes")' in text


def test_graph_snapshot_contains_expected_node_and_edge_types() -> None:
    tenant_id = uuid.uuid4()
    account_id = "123456789012"
    public_bucket_finding = _finding(
        tenant_id=tenant_id,
        account_id=account_id,
        finding_id="finding-public-bucket",
        control_id="S3.2",
        title="Public bucket exposes sensitive customer data",
        description="Bucket is open to 0.0.0.0/0 and stores sensitive customer records.",
        resource_id="arn:aws:s3:::prod-sensitive-bucket",
        resource_type="AwsS3Bucket",
    )
    root_key_finding = _finding(
        tenant_id=tenant_id,
        account_id=account_id,
        finding_id="finding-root-key",
        control_id="IAM.4",
        title="Root user has long-lived access keys",
        description="Root credentials remain active and expose privileged access.",
        resource_id=account_id,
        resource_type="AwsAccount",
    )
    actions = [
        _action(
            tenant_id=tenant_id,
            account_id=account_id,
            action_type="s3_bucket_block_public_access",
            target_id=f"{account_id}|us-east-1|arn:aws:s3:::prod-sensitive-bucket|S3.2",
            finding=public_bucket_finding,
        ),
        _action(
            tenant_id=tenant_id,
            account_id=account_id,
            action_type="iam_root_access_key_absent",
            target_id=f"{account_id}|us-east-1|{account_id}|IAM.4",
            finding=root_key_finding,
        ),
    ]

    snapshot = security_graph_service.build_security_graph_snapshot(actions, tenant_id)
    node_types = {node.node_type for node in snapshot.nodes}
    edge_types = {edge.edge_type for edge in snapshot.edges}

    assert {"resource", "identity", "exposure", "finding", "action"} <= node_types
    assert "action_derived_from_finding" in edge_types
    assert "action_targets_resource" in edge_types
    assert "finding_targets_resource" in edge_types
    assert "action_targets_identity" in edge_types
    assert "finding_targets_identity" in edge_types
    assert "action_indicates_exposure" in edge_types
    assert "finding_indicates_exposure" in edge_types


def test_graph_snapshot_skips_cross_tenant_action_finding_links() -> None:
    tenant_id = uuid.uuid4()
    other_tenant_id = uuid.uuid4()
    account_id = "123456789012"
    valid_finding = _finding(
        tenant_id=tenant_id,
        account_id=account_id,
        finding_id="finding-valid",
        control_id="S3.2",
        title="Valid same-tenant finding",
        description="Bucket is public and internet facing.",
        resource_id="arn:aws:s3:::tenant-a-bucket",
        resource_type="AwsS3Bucket",
    )
    rogue_finding = _finding(
        tenant_id=other_tenant_id,
        account_id=account_id,
        finding_id="finding-rogue",
        control_id="S3.2",
        title="Rogue other-tenant finding",
        description="This should never be linked into tenant A graph.",
        resource_id="arn:aws:s3:::tenant-b-bucket",
        resource_type="AwsS3Bucket",
    )
    action = _action(
        tenant_id=tenant_id,
        account_id=account_id,
        action_type="s3_bucket_block_public_access",
        target_id=f"{account_id}|us-east-1|arn:aws:s3:::tenant-a-bucket|S3.2",
        finding=valid_finding,
    )
    action.action_finding_links = [ActionFinding(finding=valid_finding), ActionFinding(finding=rogue_finding)]

    snapshot = security_graph_service.build_security_graph_snapshot([action], tenant_id)
    node_keys = {node.node_key for node in snapshot.nodes}
    rogue_key = security_graph_service._stable_key("finding", str(rogue_finding.id))

    assert rogue_key not in node_keys
    assert all(rogue_key not in {edge.source_node_key, edge.target_node_key} for edge in snapshot.edges)


def test_sync_security_graph_is_idempotent_for_reprocessing_same_scope(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    other_tenant_id = uuid.uuid4()
    account_id = "123456789012"
    public_bucket_finding = _finding(
        tenant_id=tenant_id,
        account_id=account_id,
        finding_id="finding-public-bucket",
        control_id="S3.2",
        title="Public bucket exposes sensitive customer data",
        description="Bucket is open to 0.0.0.0/0 and stores sensitive customer records.",
        resource_id="arn:aws:s3:::prod-sensitive-bucket",
        resource_type="AwsS3Bucket",
    )
    root_key_finding = _finding(
        tenant_id=tenant_id,
        account_id=account_id,
        finding_id="finding-root-key",
        control_id="IAM.4",
        title="Root user has long-lived access keys",
        description="Root credentials remain active and expose privileged access.",
        resource_id=account_id,
        resource_type="AwsAccount",
    )
    other_tenant_finding = _finding(
        tenant_id=other_tenant_id,
        account_id="999999999999",
        finding_id="finding-other-tenant",
        control_id="S3.2",
        title="Other tenant public bucket",
        description="Separate tenant data should stay isolated.",
        resource_id="arn:aws:s3:::other-tenant-bucket",
        resource_type="AwsS3Bucket",
    )
    session = _FakeSession(
        actions=[
            _action(
                tenant_id=tenant_id,
                account_id=account_id,
                action_type="s3_bucket_block_public_access",
                target_id=f"{account_id}|us-east-1|arn:aws:s3:::prod-sensitive-bucket|S3.2",
                finding=public_bucket_finding,
            ),
            _action(
                tenant_id=tenant_id,
                account_id=account_id,
                action_type="iam_root_access_key_absent",
                target_id=f"{account_id}|us-east-1|{account_id}|IAM.4",
                finding=root_key_finding,
            ),
            _action(
                tenant_id=other_tenant_id,
                account_id="999999999999",
                action_type="s3_bucket_block_public_access",
                target_id="999999999999|us-east-1|arn:aws:s3:::other-tenant-bucket|S3.2",
                finding=other_tenant_finding,
            ),
        ]
    )
    _patch_graph_store(monkeypatch, session)

    first = security_graph_service.sync_security_graph_for_scope(
        session,
        tenant_id,
        account_id=account_id,
        region="us-east-1",
    )
    first_node_count = len(session.nodes)
    first_edge_count = len(session.edges)
    second = security_graph_service.sync_security_graph_for_scope(
        session,
        tenant_id,
        account_id=account_id,
        region="us-east-1",
    )

    assert first["graph_nodes_created"] > 0
    assert first["graph_edges_created"] > 0
    assert second["graph_nodes_created"] == 0
    assert second["graph_edges_created"] == 0
    assert second["graph_nodes_deleted"] == 0
    assert second["graph_edges_deleted"] == 0
    assert len(session.nodes) == first_node_count
    assert len(session.edges) == first_edge_count
    assert len({node.node_key for node in session.nodes}) == len(session.nodes)
    assert len({edge.edge_key for edge in session.edges}) == len(session.edges)
    assert all(node.tenant_id == tenant_id for node in session.nodes)
    assert all(edge.tenant_id == tenant_id for edge in session.edges)


def test_sync_security_graph_uses_pending_node_rows_when_existing_queries_miss_unflushed_inserts(
    monkeypatch,
) -> None:
    tenant_id = uuid.uuid4()
    account_id = "123456789012"
    finding = _finding(
        tenant_id=tenant_id,
        account_id=account_id,
        finding_id="finding-autoflush-gap",
        control_id="S3.2",
        title="Public bucket exposes sensitive customer data",
        description="Bucket is open to 0.0.0.0/0 and stores sensitive customer records.",
        resource_id="arn:aws:s3:::prod-sensitive-bucket",
        resource_type="AwsS3Bucket",
    )
    session = _FakeSession(
        actions=[
            _action(
                tenant_id=tenant_id,
                account_id=account_id,
                action_type="s3_bucket_block_public_access",
                target_id=f"{account_id}|us-east-1|arn:aws:s3:::prod-sensitive-bucket|S3.2",
                finding=finding,
            )
        ]
    )
    _patch_graph_store(monkeypatch, session)
    existing_node_calls: list[tuple[str, ...]] = []

    def _missing_existing_nodes(_db, scoped_tenant_id, node_keys):
        if scoped_tenant_id == tenant_id:
            existing_node_calls.append(tuple(sorted(node_keys)))
        return {}

    monkeypatch.setattr(security_graph_service, "_existing_nodes_by_key", _missing_existing_nodes)

    counts = security_graph_service.sync_security_graph_for_scope(
        session,
        tenant_id,
        account_id=account_id,
        region="us-east-1",
    )

    assert len(existing_node_calls) == 1
    assert counts["graph_nodes_created"] > 0
    assert counts["graph_edges_created"] > 0
    assert session.edges
