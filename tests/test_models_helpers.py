"""The helpers of response models."""

from __future__ import annotations

import pytest

from fastsandbox import (
    CommandFailedError,
)
from fastsandbox.exceptions import OperationFailedError
from fastsandbox.models import (
    DaemonEvent,
    EventKind,
    ExecOutput,
    HostActivity,
    ImageSummary,
    NetworkLog,
    RuleChangeResult,
)


def test_image_reference_prefers_the_tag() -> None:
    tagged = ImageSummary(repository="docker.io/sbx/shell", tag="latest", id="sha256:1")
    by_digest = ImageSummary(repository="docker.io/sbx/shell", digest="sha256:d", id="sha256:1")
    bare = ImageSummary(repository="docker.io/sbx/shell", id="sha256:1")
    assert tagged.reference == "docker.io/sbx/shell:latest"
    assert by_digest.reference == "docker.io/sbx/shell@sha256:d"
    assert bare.reference == "docker.io/sbx/shell@sha256:1"


def test_network_log_filters_one_sandbox() -> None:
    log = NetworkLog(
        allowed_hosts=[HostActivity(host="a:443", vm_name="one")],
        blocked_hosts=[HostActivity(host="b:443", vm_name="two")],
    )
    assert [h.host for h in log.for_sandbox("one").allowed_hosts] == ["a:443"]
    assert log.for_sandbox("one").blocked_hosts == []


def test_exec_output_check() -> None:
    assert ExecOutput(exit_code=0, stdout="ok").check().ok
    with pytest.raises(CommandFailedError) as raised:
        ExecOutput(exit_code=2, stderr="boom\n").check()
    assert raised.value.exit_code == 2
    assert "boom" in str(raised.value)


def test_rule_change_result_check() -> None:
    assert RuleChangeResult(action="allow").is_applied
    with pytest.raises(OperationFailedError):
        RuleChangeResult(error="unknown rule").check()


def test_event_kinds() -> None:
    event = DaemonEvent.model_validate({"id": "1", "type": "sync", "action": "complete"})
    assert event.kind is EventKind.SYNC
    assert event.is_sync
    other = DaemonEvent.model_validate(
        {"id": "2", "type": "brand.new", "action": "x", "sandbox_name": "job"}
    )
    assert other.kind is EventKind.OTHER
    assert other.is_about("job")
