Name:		qubes-core-mgmt-client
Version:    %(cat version)
Release:	0.1%{?dist}
Summary:	Qubes OS management client tools

Group:		Qubes
License:	LGPLv2.1+
URL:		https://www.qubes-os.org

BuildRequires:	python2-setuptools
BuildRequires:	python3-setuptools
BuildRequires:	python2-devel
BuildRequires:	python3-devel
Requires:   python3-qubesmgmt
BuildArch:  noarch

%if 0%{?qubes_builder}
%define _builddir %(pwd)
%endif

%description
This package include managemt tools, like qvm-*.

%package -n python2-qubesmgmt
Summary:    Python2 module qubesmgmt

%description -n python2-qubesmgmt
Python2 module qubesmgmt.

%package -n python3-qubesmgmt
Summary:    Python3 module qubesmgmt

%description -n python3-qubesmgmt
Python3 module qubesmgmt.

%prep
%if !0%{?qubes_builder}
%setup -q
%endif


%build
make %{?_smp_mflags} PYTHON=%{__python2}
make %{?_smp_mflags} PYTHON=%{__python3}


%install
%make_install PYTHON=%{__python2}
%make_install PYTHON=%{__python3}


%files
%doc LICENSE

%files -n python2-qubesmgmt
%{python_sitelib}/qubesmgmt-*egg-info
%{python_sitelib}/qubesmgmt

%files -n python3-qubesmgmt
%{python3_sitelib}/qubesmgmt-*egg-info
%{python3_sitelib}/qubesmgmt


%changelog

