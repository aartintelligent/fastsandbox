"""The wire shape of request models."""

from __future__ import annotations

from fastsandbox.models import (
    ExecSpec,
    McpServerCheck,
    NetworkCheck,
    PortBinding,
    RuleChange,
    SandboxInfo,
    Setting,
    wire,
)


def test_rule_changes_have_the_shape_of_the_library() -> None:
    assert wire(RuleChange.allow("pypi.org")) == {
        "action": "allow",
        "resources": ["pypi.org"],
        "protocols": ["tcp"],
        "methods": [],
    }
    deny = RuleChange.deny("example.org").for_sandbox("job")
    assert wire(deny)["protocols"] == ["tcp", "udp"]
    assert wire(deny)["sandbox_id"] == "job"
    assert wire(RuleChange.remove_rule("r1")) == {
        "action": "remove-id",
        "id": "r1",
        "resources": [],
        "protocols": [],
        "methods": [],
    }
    http = RuleChange.allow_http("api.github.com").with_methods("GET").with_path("/repos/**")
    assert wire(http)["action"] == "http-allow"
    assert wire(http)["path"] == "/repos/**"


def test_aliases_follow_the_daemon_names() -> None:
    assert wire(McpServerCheck.remote("docs", "https://mcp.example.com")) == {
        "Name": "docs",
        "Type": "remote",
        "Command": [],
        "URL": "https://mcp.example.com",
    }
    assert wire(NetworkCheck.http("GET", "https://pypi.org/simple")) == {
        "type": "http",
        "target": "https://pypi.org/simple",
        "method": "GET",
    }
    setting = Setting.model_validate({"key": "a.b", "value": True, "type": "bool"})
    assert setting.value_type == "bool"


def test_unknown_fields_are_kept() -> None:
    info = SandboxInfo.model_validate(
        {"id": "1", "name": "job", "agent": "shell", "status": "running", "future_field": 7}
    )
    assert info.is_running
    assert info.model_extra == {"future_field": 7}


def test_shell_specs() -> None:
    assert ExecSpec.shell("echo hi").cmd == ["sh", "-c", "echo hi"]
    assert PortBinding.udp(53, 5353).protocol == "udp"
