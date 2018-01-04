Name:		qubes-core-admin-client
Version:    %(cat version)
Release:	0.1%{?dist}
Summary:	Qubes OS admin client tools

Group:		Qubes
License:	LGPLv2.1+
URL:		https://www.qubes-os.org

BuildRequires:	python2-setuptools
BuildRequires:	python2-devel
%if 0%{?rhel} >= 7
BuildRequires:	python34-setuptools
BuildRequires:	python34-devel
BuildRequires:	python-sphinx
BuildRequires:	python34-dbus
Requires:   python34-qubesadmin
%else
BuildRequires:	python3-setuptools
BuildRequires:	python3-devel
BuildRequires:	python3-sphinx
BuildRequires:	python3-dbus
Requires:   python3-qubesadmin
%endif
BuildArch:  noarch

%if 0%{?qubes_builder}
%define _builddir %(pwd)
%endif

%description
This package include managemt tools, like qvm-*.

%package -n python2-qubesadmin
Summary:    Python2 module qubesadmin
Requires:   python-daemon
Requires:   python-docutils
Requires:   python2-lxml

%description -n python2-qubesadmin
Python2 module qubesadmin.

%if 0%{?rhel} >= 7
%package -n python34-qubesadmin
Summary:    Python34 module qubesadmin
Requires:   python-daemon
Requires:   python34-docutils
Requires:   python34-lxml
Conflicts:  qubes-manager < 4.0.6

%description -n python34-qubesadmin
Python34 module qubesadmin.
%else
%package -n python3-qubesadmin
Summary:    Python3 module qubesadmin
Requires:   python3-daemon
Requires:   python3-docutils
Requires:   python3-lxml
Conflicts:  qubes-manager < 4.0.6

%description -n python3-qubesadmin
Python3 module qubesadmin.
%endif

%prep
%if !0%{?qubes_builder}
%setup -q
%endif


%build
%if 0%{?rhel} >= 7
make -C doc PYTHON=%{__python3} SPHINXBUILD=sphinx-build man
%else
make -C doc PYTHON=%{__python3} SPHINXBUILD=sphinx-build-%{python3_version} man
%endif

%install
rm -rf build
%make_install PYTHON=%{__python2}
rm -rf build
%make_install PYTHON=%{__python3}

%if 0%{?rhel} >= 7
make -C doc DESTDIR=$RPM_BUILD_ROOT \
    PYTHON=%{__python3} SPHINXBUILD=sphinx-build \
    install
%else
make -C doc DESTDIR=$RPM_BUILD_ROOT \
    PYTHON=%{__python3} SPHINXBUILD=sphinx-build-%{python3_version} \
    install
%endif


%files
%defattr(-,root,root,-)
%doc LICENSE
%config /etc/xdg/autostart/qvm-start-gui.desktop
%{_bindir}/qubes-*
%{_bindir}/qvm-*
%{_mandir}/man1/qvm-*.1*
%{_mandir}/man1/qubes*.1*

%files -n python2-qubesadmin
%{python_sitelib}/qubesadmin-*egg-info
%{python_sitelib}/qubesadmin

%if 0%{?rhel} >= 7
%files -n python34-qubesadmin
%else
%files -n python3-qubesadmin
%endif
%{python3_sitelib}/qubesadmin-*egg-info
%{python3_sitelib}/qubesadmin


%changelog

