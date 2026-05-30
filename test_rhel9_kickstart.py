"""
Tests for rhel9-kickstart.cfg

Each test class covers a logical section of the kickstart file.
Run with: python3 -m pytest test_rhel9_kickstart.py -v
"""

import re
import pytest

KS_FILE = "rhel9-kickstart.cfg"


@pytest.fixture(scope="session")
def ks_text():
    with open(KS_FILE) as f:
        return f.read()


@pytest.fixture(scope="session")
def ks_lines(ks_text):
    return ks_text.splitlines()


def active_lines(text):
    """Return non-empty, non-comment lines."""
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def section(text, start_marker, end_marker=None):
    """Extract text between two markers (exclusive)."""
    lines = text.splitlines()
    capturing = False
    result = []
    for line in lines:
        if line.strip().startswith(start_marker):
            capturing = True
            continue
        if capturing:
            if end_marker and line.strip() == end_marker:
                break
            result.append(line)
    return "\n".join(result)


# ---------------------------------------------------------------------------
# File basics
# ---------------------------------------------------------------------------

class TestFileHeader:
    def test_version_comment_present(self, ks_text):
        assert "#version=RHEL9" in ks_text

    def test_install_source_defined(self, ks_text):
        # cdrom must appear as a standalone directive (not inside a comment)
        non_comment = active_lines(ks_text)
        assert any(line == "cdrom" for line in non_comment), \
            "Expected 'cdrom' install source directive"


# ---------------------------------------------------------------------------
# Locale & keyboard
# ---------------------------------------------------------------------------

class TestLocale:
    def test_lang_set(self, ks_text):
        assert re.search(r"^lang\s+en_US\.UTF-8", ks_text, re.MULTILINE)

    def test_keyboard_set(self, ks_text):
        assert re.search(r"^keyboard\s+", ks_text, re.MULTILINE)

    def test_keyboard_uses_us_layout(self, ks_text):
        m = re.search(r"^keyboard\s+(.*)", ks_text, re.MULTILINE)
        assert m and "us" in m.group(1)


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

class TestNetwork:
    def test_network_directive_present(self, ks_text):
        assert re.search(r"^network\s+", ks_text, re.MULTILINE)

    def test_network_activates_on_boot(self, ks_text):
        assert "--onboot=yes" in ks_text

    def test_network_has_hostname(self, ks_text):
        assert "--hostname=" in ks_text


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

class TestAuthentication:
    def test_rootpw_present(self, ks_text):
        assert re.search(r"^rootpw\s+", ks_text, re.MULTILINE)

    def test_rootpw_is_crypted(self, ks_text):
        m = re.search(r"^rootpw\s+(.*)", ks_text, re.MULTILINE)
        assert m and "--iscrypted" in m.group(1), \
            "rootpw must use --iscrypted"

    def test_rootpw_uses_sha512(self, ks_text):
        m = re.search(r"^rootpw\s+.*?(\$\d\$.*)", ks_text, re.MULTILINE)
        assert m and m.group(1).startswith("$6$"), \
            "rootpw hash should be SHA-512 ($6$)"

    def test_admin_user_created(self, ks_text):
        assert re.search(r"^user\s+.*--name=admin", ks_text, re.MULTILINE)

    def test_admin_user_in_wheel(self, ks_text):
        m = re.search(r"^user\s+(.*)", ks_text, re.MULTILINE)
        assert m and "--groups=wheel" in m.group(1), \
            "admin user must be in the wheel group"

    def test_admin_password_is_crypted(self, ks_text):
        m = re.search(r"^user\s+(.*)", ks_text, re.MULTILINE)
        assert m and "--iscrypted" in m.group(1)


# ---------------------------------------------------------------------------
# Security policy
# ---------------------------------------------------------------------------

class TestSecurity:
    def test_selinux_enforcing(self, ks_text):
        assert re.search(r"^selinux\s+--enforcing", ks_text, re.MULTILINE), \
            "SELinux must be set to enforcing"

    def test_firewall_enabled(self, ks_text):
        assert re.search(r"^firewall\s+--enabled", ks_text, re.MULTILINE)

    def test_firewall_allows_ssh(self, ks_text):
        m = re.search(r"^firewall\s+(.*)", ks_text, re.MULTILINE)
        assert m and "--ssh" in m.group(1), \
            "Firewall must allow SSH traffic"


# ---------------------------------------------------------------------------
# Services & timezone
# ---------------------------------------------------------------------------

class TestServicesAndTimezone:
    def test_services_directive_present(self, ks_text):
        assert re.search(r"^services\s+", ks_text, re.MULTILINE)

    def test_sshd_enabled(self, ks_text):
        m = re.search(r"^services\s+(.*)", ks_text, re.MULTILINE)
        assert m and "sshd" in m.group(1)

    def test_chronyd_enabled(self, ks_text):
        m = re.search(r"^services\s+(.*)", ks_text, re.MULTILINE)
        assert m and "chronyd" in m.group(1)

    def test_timezone_set(self, ks_text):
        assert re.search(r"^timezone\s+", ks_text, re.MULTILINE)

    def test_timezone_utc(self, ks_text):
        assert re.search(r"^timezone\s+.*--utc", ks_text, re.MULTILINE)


# ---------------------------------------------------------------------------
# Bootloader
# ---------------------------------------------------------------------------

class TestBootloader:
    def test_bootloader_directive_present(self, ks_text):
        assert re.search(r"^bootloader\s+", ks_text, re.MULTILINE)

    def test_bootloader_location_mbr(self, ks_text):
        assert "--location=mbr" in ks_text

    def test_bootloader_drive_set(self, ks_text):
        assert "--boot-drive=" in ks_text


# ---------------------------------------------------------------------------
# Partitioning
# ---------------------------------------------------------------------------

class TestPartitioning:
    def test_clearpart_all(self, ks_text):
        assert re.search(r"^clearpart\s+--all", ks_text, re.MULTILINE)

    def test_zerombr_present(self, ks_text):
        assert re.search(r"^zerombr", ks_text, re.MULTILINE)

    def test_boot_partition_xfs(self, ks_text):
        assert re.search(
            r'^part\s+/boot\s+.*--fstype="xfs"', ks_text, re.MULTILINE
        )

    def test_boot_partition_minimum_size(self, ks_text):
        m = re.search(r'^part\s+/boot\s+.*--size=(\d+)', ks_text, re.MULTILINE)
        assert m and int(m.group(1)) >= 512, \
            "/boot must be at least 512 MB"

    def test_efi_partition_present(self, ks_text):
        assert re.search(
            r'^part\s+/boot/efi\s+.*--fstype="efi"', ks_text, re.MULTILINE
        )

    def test_lvm_pv_present(self, ks_text):
        assert re.search(
            r'^part\s+\S+\s+.*--fstype="lvmpv"', ks_text, re.MULTILINE
        )

    def test_volgroup_defined(self, ks_text):
        assert re.search(r"^volgroup\s+\S+", ks_text, re.MULTILINE)

    def test_root_logvol_present(self, ks_text):
        assert re.search(
            r'^logvol\s+/\s+.*--fstype="xfs"', ks_text, re.MULTILINE
        )

    def test_root_logvol_minimum_size(self, ks_text):
        m = re.search(r'^logvol\s+/\s+.*--size=(\d+)', ks_text, re.MULTILINE)
        assert m and int(m.group(1)) >= 10240, \
            "/ must be at least 10 GB"

    def test_home_logvol_present(self, ks_text):
        assert re.search(r'^logvol\s+/home\s+', ks_text, re.MULTILINE)

    def test_var_logvol_present(self, ks_text):
        assert re.search(r'^logvol\s+/var\s+', ks_text, re.MULTILINE)

    def test_tmp_logvol_present(self, ks_text):
        assert re.search(r'^logvol\s+/tmp\s+', ks_text, re.MULTILINE)

    def test_tmp_mount_options_secure(self, ks_text):
        m = re.search(r'^logvol\s+/tmp\s+(.*)', ks_text, re.MULTILINE)
        assert m, "/tmp logvol not found"
        opts = m.group(1)
        for flag in ("nodev", "nosuid", "noexec"):
            assert flag in opts, f"/tmp must have {flag} mount option"

    def test_swap_logvol_present(self, ks_text):
        assert re.search(
            r'^logvol\s+swap\s+.*--fstype="swap"', ks_text, re.MULTILINE
        )


# ---------------------------------------------------------------------------
# Package selection
# ---------------------------------------------------------------------------

class TestPackages:
    @pytest.fixture(scope="class")
    def pkg_section(self, ks_text):
        return section(ks_text, "%packages", "%end")

    def test_packages_section_exists(self, ks_text):
        assert "%packages" in ks_text

    def test_minimal_environment_included(self, pkg_section):
        assert "@^minimal-environment" in pkg_section

    @pytest.mark.parametrize("pkg", [
        "chrony", "openssh-server", "sudo", "vim-enhanced",
        "wget", "curl", "bash-completion",
    ])
    def test_required_package_present(self, pkg_section, pkg):
        assert pkg in pkg_section, f"Expected package '{pkg}' in %packages"

    def test_firmware_packages_excluded(self, pkg_section):
        assert "-iwl*firmware" in pkg_section, \
            "Wireless firmware packages should be explicitly excluded"

    def test_packages_section_closed(self, ks_text):
        pkg_start = ks_text.index("%packages")
        assert "%end" in ks_text[pkg_start:], \
            "%packages section must be closed with %end"


# ---------------------------------------------------------------------------
# Pre-install script
# ---------------------------------------------------------------------------

class TestPreScript:
    def test_pre_section_exists(self, ks_text):
        assert "%pre" in ks_text

    def test_pre_has_log(self, ks_text):
        assert re.search(r"%pre\s+--log=", ks_text)

    def test_pre_section_closed(self, ks_text):
        pre_start = ks_text.index("%pre")
        remaining = ks_text[pre_start:]
        # The first %end after %pre closes it
        assert "%end" in remaining


# ---------------------------------------------------------------------------
# Post-install script
# ---------------------------------------------------------------------------

class TestPostScript:
    @pytest.fixture(scope="class")
    def post_section(self, ks_text):
        return section(ks_text, "%post", "%end")

    def test_post_section_exists(self, ks_text):
        assert "%post" in ks_text

    def test_post_has_log(self, ks_text):
        assert re.search(r"%post\s+--log=", ks_text)

    def test_post_uses_strict_bash(self, post_section):
        assert "set -euo pipefail" in post_section, \
            "Post script should use 'set -euo pipefail' for safety"

    def test_post_disables_root_ssh_login(self, post_section):
        assert "PermitRootLogin no" in post_section

    def test_post_disables_x11_forwarding(self, post_section):
        assert "X11Forwarding no" in post_section

    def test_post_sets_secure_umask(self, post_section):
        assert "umask 027" in post_section

    def test_post_disables_cramfs(self, post_section):
        assert "install cramfs /bin/true" in post_section

    def test_post_disables_unused_filesystems(self, post_section):
        for fs in ("freevxfs", "jffs2", "hfs", "hfsplus", "squashfs", "udf"):
            assert f"install {fs} /bin/true" in post_section, \
                f"Expected {fs} to be disabled in modprobe config"

    def test_post_enables_dnf_automatic(self, post_section):
        assert "dnf-automatic" in post_section
        assert "apply_updates = yes" in post_section

    def test_post_configures_chrony(self, post_section):
        assert "chrony.conf" in post_section
        assert "pool 2.rhel.pool.ntp.org iburst" in post_section

    def test_post_kernel_disables_ip_forwarding(self, post_section):
        assert "net.ipv4.ip_forward = 0" in post_section

    def test_post_kernel_enables_syn_cookies(self, post_section):
        assert "net.ipv4.tcp_syncookies = 1" in post_section

    def test_post_kernel_disables_icmp_redirects(self, post_section):
        assert "net.ipv4.conf.all.accept_redirects = 0" in post_section

    def test_post_kernel_enables_rp_filter(self, post_section):
        assert "net.ipv4.conf.all.rp_filter = 1" in post_section

    def test_post_disables_ipv6(self, post_section):
        assert "net.ipv6.conf.all.disable_ipv6 = 1" in post_section

    def test_post_section_closed(self, ks_text):
        post_start = ks_text.index("%post")
        assert "%end" in ks_text[post_start:]


# ---------------------------------------------------------------------------
# End directive
# ---------------------------------------------------------------------------

class TestEndDirective:
    def test_reboot_directive_present(self, ks_text):
        assert re.search(r"^reboot", ks_text, re.MULTILINE), \
            "Kickstart should end with 'reboot'"

    def test_reboot_ejects_media(self, ks_text):
        assert re.search(r"^reboot\s+--eject", ks_text, re.MULTILINE), \
            "reboot should use --eject to remove install media"
