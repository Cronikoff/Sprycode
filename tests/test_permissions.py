"""
Tests for the SpryCode Permission System.
"""

import pytest
from sprycode.permissions import Permission, PermissionError, PermissionSet


class TestBasicPermissions:
    def test_allow_grants_access(self):
        ps = PermissionSet()
        ps.add_allow("filesystem.read", "./data")
        # Should not raise
        ps.check("filesystem.read", "./data")

    def test_deny_blocks_access(self):
        ps = PermissionSet()
        ps.add_deny("filesystem.read", "./secret")
        with pytest.raises(PermissionError):
            ps.check("filesystem.read", "./secret")

    def test_secure_mode_requires_explicit_allow(self):
        ps = PermissionSet()
        ps.enable_secure_mode()
        with pytest.raises(PermissionError):
            ps.check("filesystem.read", "./data")

    def test_secure_mode_with_allow(self):
        ps = PermissionSet()
        ps.enable_secure_mode()
        ps.add_allow("filesystem.read", "./data")
        # Should not raise
        ps.check("filesystem.read", "./data")

    def test_allow_all_variant(self):
        ps = PermissionSet()
        ps.add_allow("filesystem.all")
        # filesystem.read is covered by filesystem.all
        ps.check("filesystem.read", "/any/path")
        ps.check("filesystem.write", "/any/path")

    def test_deny_overrides_allow(self):
        ps = PermissionSet()
        ps.add_allow("filesystem.read")  # Allow all reads
        ps.add_deny("filesystem.read", "/secret")  # But deny this path

        # Should work for other paths
        ps.check("filesystem.read", "/public")

        # Should fail for denied path
        with pytest.raises(PermissionError):
            ps.check("filesystem.read", "/secret")

    def test_network_permission(self):
        ps = PermissionSet()
        ps.add_allow("network.request", "https://api.example.com")
        ps.check("network.request", "https://api.example.com")

    def test_secret_permission(self):
        ps = PermissionSet()
        ps.add_allow("secret.read", "API_KEY")
        ps.check("secret.read", "API_KEY")

    def test_secret_permission_denied(self):
        ps = PermissionSet()
        ps.enable_secure_mode()
        with pytest.raises(PermissionError):
            ps.check("secret.read", "API_KEY")


class TestIsAllowed:
    def test_is_allowed_true(self):
        ps = PermissionSet()
        ps.add_allow("filesystem.read")
        assert ps.is_allowed("filesystem.read") is True

    def test_is_allowed_false_deny(self):
        ps = PermissionSet()
        ps.add_deny("filesystem.write")
        assert ps.is_allowed("filesystem.write") is False

    def test_is_allowed_false_secure_mode(self):
        ps = PermissionSet()
        ps.enable_secure_mode()
        assert ps.is_allowed("network.request") is False


class TestClone:
    def test_clone_inherits_rules(self):
        ps = PermissionSet()
        ps.add_allow("filesystem.read")
        clone = ps.clone()
        clone.check("filesystem.read")

    def test_clone_is_independent(self):
        ps = PermissionSet()
        clone = ps.clone()
        clone.add_allow("filesystem.read")
        # Original should not have this permission
        ps.enable_secure_mode()
        with pytest.raises(PermissionError):
            ps.check("filesystem.read")


class TestPathMatching:
    def test_path_prefix_matching(self):
        ps = PermissionSet()
        ps.add_allow("filesystem.read", "./data")
        # Should allow paths under ./data
        ps.check("filesystem.read", "./data/file.txt")

    def test_exact_path_denial(self):
        ps = PermissionSet()
        ps.add_deny("filesystem.write", "./readonly")
        with pytest.raises(PermissionError):
            ps.check("filesystem.write", "./readonly")


class TestMultiplePermissions:
    def test_multiple_allows(self):
        ps = PermissionSet()
        ps.add_allow("filesystem.read", "./data")
        ps.add_allow("filesystem.write", "./output")
        ps.add_allow("network.request", "https://api.example.com")

        ps.check("filesystem.read", "./data")
        ps.check("filesystem.write", "./output")
        ps.check("network.request", "https://api.example.com")

    def test_allow_then_deny(self):
        """Last rule wins."""
        ps = PermissionSet()
        ps.add_allow("filesystem.read", "./data")
        ps.add_deny("filesystem.read", "./data")
        with pytest.raises(PermissionError):
            ps.check("filesystem.read", "./data")

    def test_deny_then_allow(self):
        """Last rule wins."""
        ps = PermissionSet()
        ps.add_deny("filesystem.read", "./data")
        ps.add_allow("filesystem.read", "./data")
        # Should not raise — last rule (allow) wins
        ps.check("filesystem.read", "./data")
