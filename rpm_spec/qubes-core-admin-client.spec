Name:		qubes-core-admin-client
Version:    %(cat version)
Release:	0.1%{?dist}
Summary:	Qubes OS admin client tools

Group:		Qubes
License:	LGPLv2.1+
URL:		https://www.qubes-os.org

BuildRequires:	python2-setuptools
BuildRequires:	python3-setuptools
BuildRequires:	python2-devel
BuildRequires:	python3-devel
BuildRequires:	python3-sphinx
BuildRequires:	python3-dbus
Requires:   python3-qubesadmin
BuildArch:  noarch

%if 0%{?qubes_builder}
%define _builddir %(pwd)
%endif

%description
This package include managemt tools, like qvm-*.

%package -n python2-qubesadmin
Summary:    Python2 module qubesadmin
Requires:   python-daemon

%description -n python2-qubesadmin
Python2 module qubesadmin.

%package -n python3-qubesadmin
Summary:    Python3 module qubesadmin
Requires:   python3-daemon

%description -n python3-qubesadmin
Python3 module qubesadmin.

%prep
%if !0%{?qubes_builder}
%setup -q
%endif


%build
make -C doc PYTHON=%{__python3} SPHINXBUILD=sphinx-build-%{python3_version} man

%install
rm -rf build
%make_install PYTHON=%{__python2}
rm -rf build
%make_install PYTHON=%{__python3}

make -C doc DESTDIR=$RPM_BUILD_ROOT \
    PYTHON=%{__python3} SPHINXBUILD=sphinx-build-%{python3_version} \
    install


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

%files -n python3-qubesadmin
%{python3_sitelib}/qubesadmin-*egg-info
%{python3_sitelib}/qubesadmin


%changelog

