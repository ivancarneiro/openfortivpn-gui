# OpenFortiVPN GUI Constitution

## Core Principles

### I. Security & Credential Safety (NON-NEGOTIABLE)
- **Zero Plaintext Secrets**: Passwords, OTP tokens, and user credentials MUST NEVER be stored in plain text files on the filesystem.
- **Keyring / Ephemeral Storage**: Credentials must be securely stored using the OS Keyring (`keyring` library / SecretService) or held in memory only for the duration of the session.
- **Sanitized Logging**: Passwords, 2FA/OTP tokens, and private hashes must never be printed to stdout, stderr, or written to debug log files (`~/.config/ofvpn-gui/debug.log`).
- **Guaranteed Cleanup**: Temporary runtime configuration files generated for `openfortivpn` must have strict file permissions (0600) and must be securely wiped and unlinked immediately upon process exit or error.

### II. Privilege Separation & Process Lifecycle Management
- **Unprivileged Execution**: The GUI application runs exclusively in the user space without administrative privileges.
- **Scoped Privilege Elevation**: Root/administrative execution is strictly scoped to the `openfortivpn` daemon process via `sudo`, `pkexec`, or sudoers rules defined in `/etc/sudoers.d/openfortivpn-gui`.
- **Orphan Process Prevention**: When disconnecting or closing the application, all spawned background subprocesses MUST be reliably terminated (SIGTERM with fallback to SIGKILL) and monitored until dead. Never leave background `openfortivpn` processes running unattended without GUI association.

### III. Qt Threading & UI Responsiveness
- **Non-Blocking Main Thread**: The GUI thread must never block on disk I/O, network requests, or synchronous subprocess calls.
- **Asynchronous Execution & Signals**: Long-running tasks, traffic statistic polling, and subprocess stdout/stderr parsing must run in background threads (`QThread`) or use asynchronous event-driven slots/signals.
- **Modular Component Separation**: Maintain clean separation between UI components (`MainWindow`, `ConfigDialog`, `StatsPanel`), domain models (`ProfileManager`), process supervisors (`VpnManager`), and system migration helpers (`migration_utils.py`).

### IV. Resilience, Failover & Error Handling
- **Multi-Gateway Failover**: VPN profiles supporting multiple gateways must gracefully transition between gateways upon connection failures.
- **Explicit State Transitions**: Connection state machine must strictly report valid states: `disconnected`, `connecting`, `connected`, `failover`, `failed`.
- **Informative User Feedback**: Network failures, SSL certificate mismatches, or missing permissions must produce actionable, non-cryptic error dialogs and native desktop notifications.

### V. Linux Desktop Integration & UX Standards
- **Modern Theme Consistency**: Adhere to the dark theme styling (`Fusion Dark`) and cohesive UI layouts.
- **Desktop Environment Compatibility**: Ensure seamless operation across KDE Plasma, GNOME, XFCE, and other standard desktop environments, including system tray icon lifecycle and autostart capabilities.

## Governance
- This Constitution defines non-negotiable architectural and security standards for all features in `openfortivpn-gui`.
- Every specification (`spec.md`), technical plan (`plan.md`), task breakdown (`tasks.md`), and implementation MUST comply with these principles.
- Code changes must maintain compatibility with Python 3.8+ and PySide6 on modern Linux distributions.

**Version**: 1.0.0 | **Ratified**: 2026-10-05 | **Last Amended**: 2026-10-05
