Name:           wersynking
Version:        0.2.0
Release:        1%{?dist}
Summary:        Managed rsync connections with a PySide6/QML UI

# Renamed from we-rsynk-ing at 0.2.0; let dnf swap the old package.
Obsoletes:      we-rsynk-ing <= 0.1.0
Provides:       we-rsynk-ing = %{version}-%{release}

# PolyForm Noncommercial is a valid SPDX id but NOT a Fedora-allowed license;
# this package is distributed via GitHub Releases only, never Fedora/COPR.
License:        PolyForm-Noncommercial-1.0.0
URL:            https://github.com/jmoraur/wersynking
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  desktop-file-utils

# External tools invoked at runtime
Requires:       rsync
Requires:       util-linux
Requires:       hicolor-icon-theme
Requires:       python3-pyside6
Recommends:     systemd

%description
WeRSynking is a desktop app for managing recurring rsync jobs between
local folders, removable drives and SSH remotes, with live device
detection, a system tray indicator and desktop notifications.

License: PolyForm Noncommercial 1.0.0 (source available, noncommercial
use only).

%prep
%autosetup -n %{name}-%{version}

%generate_buildrequires
# -R: skip runtime deps at build time (no need for PySide6 in the buildroot
# to build a pure-Python wheel). Runtime Requires still get auto-generated
# from the installed dist-info metadata.
%pyproject_buildrequires -R

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files -l rsync_app

install -Dpm0644 packaging/wersynking.desktop \
    %{buildroot}%{_datadir}/applications/wersynking.desktop
install -Dpm0644 packaging/icons/rsync-app.svg \
    %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/rsync-app.svg

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/wersynking.desktop

%files -f %{pyproject_files}
%license LICENSE
%doc README.md
%{_bindir}/wersynking
%{_datadir}/applications/wersynking.desktop
%{_datadir}/icons/hicolor/scalable/apps/rsync-app.svg

%changelog
* Mon Jul 20 2026 Jan Moraru <jan@moraru.ch> - 0.2.0-1
- Rename package we-rsynk-ing -> wersynking (app is now "WeRSynking")
- In-app two-color wordmark
- Explicit light/dark/system theme mode

* Mon Jul 20 2026 Jan Moraru <jan@moraru.ch> - 0.1.0-1
- Initial package
