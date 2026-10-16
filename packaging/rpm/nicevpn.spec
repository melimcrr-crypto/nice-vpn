Name:           nicevpn
Version:        1.1.0
Release:        1%{?dist}
Summary:        Nice VPN — self-contained Xray/VLESS client with GUI for Fedora KDE
License:        MIT
URL:            https://github.com/melimcrr-crypto/nice-vpn
Source0:        nicevpn-%{version}.tar.gz
BuildArch:      x86_64
# خودکفا: پایتون و PySide6 و xray و tun2socks داخل خود بسته هستند.
# فقط این دو برای «تونل کامل» لازم‌اند و روی فدورا از قبل نصب‌اند:
Requires:       polkit
Requires:       iproute

%description
Nice VPN is a clean and simple Xray/VLESS client for Fedora KDE Plasma.

- SELF-CONTAINED: bundled Python + PySide6 + xray + tun2socks (nothing to install!)
- No ads, no forced channel join, no remote-config backdoor
- Reality XHTTP / VLESS WS / gRPC nodes built in (offline list)
- Real connectivity verification (never reports "connected" without traffic)
- Full system tunnel mode (TUN) with route/anti-leak handling via pkexec
- Automatic system proxy setup for KDE Plasma and GNOME
- Tray icon, real-address TCP ping, import vless:// / vmess:// links and subscriptions
- Ad blocking (geosite:category-ads-all) and direct routing for Iranian sites

رابط فارسی — بدون تبلیغات، بدون عضویت اجباری.

%prep
%setup -q -n %{name}-%{version}

%build

%install
mkdir -p %{buildroot}%{_datadir}/nicevpn
cp -a runtime %{buildroot}%{_datadir}/nicevpn/
cp -a data    %{buildroot}%{_datadir}/nicevpn/
mkdir -p %{buildroot}%{_datadir}/nicevpn/bin
install -m 755 bin/xray       %{buildroot}%{_datadir}/nicevpn/bin/xray
install -m 755 bin/tun2socks  %{buildroot}%{_datadir}/nicevpn/bin/tun2socks
install -m 755 bin/nicevpn-tun %{buildroot}%{_datadir}/nicevpn/bin/nicevpn-tun

mkdir -p %{buildroot}%{_bindir}
cat > %{buildroot}%{_bindir}/nicevpn <<'EOF'
#!/bin/sh
# Nice VPN — کاملاً خودکفا (پایتون داخلی)
exec /usr/share/nicevpn/runtime/bin/python3 -m nicevpn "$@"
EOF
chmod 755 %{buildroot}%{_bindir}/nicevpn

for s in 16 32 48 64 128 256; do
  mkdir -p %{buildroot}%{_datadir}/icons/hicolor/${s}x${s}/apps
  install -m 644 runtime/lib/python3.11/site-packages/nicevpn/assets/icons/logo-${s}.png \
    %{buildroot}%{_datadir}/icons/hicolor/${s}x${s}/apps/nicevpn.png 2>/dev/null || true
done
if [ -f runtime/lib/python3.11/site-packages/nicevpn/assets/icons/logo.svg ]; then
  mkdir -p %{buildroot}%{_datadir}/icons/hicolor/scalable/apps
  install -m 644 runtime/lib/python3.11/site-packages/nicevpn/assets/icons/logo.svg \
    %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/nicevpn.svg
fi

mkdir -p %{buildroot}%{_datadir}/applications
cat > %{buildroot}%{_datadir}/applications/nicevpn.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=Nice VPN
GenericName=VPN Client
Comment=Clean Xray/VLESS client — no ads, no forced join
Exec=nicevpn
Icon=nicevpn
Terminal=false
Categories=Network;Qt;
Keywords=vpn;proxy;xray;vless;
X-KDE-StartupNotify=true
EOF

%files
%{_bindir}/nicevpn
%{_datadir}/nicevpn/
%{_datadir}/icons/hicolor/*/apps/nicevpn.*
%{_datadir}/applications/nicevpn.desktop

%post
update-desktop-database >/dev/null 2>&1 || :
gtk-update-icon-cache -q -f %{_datadir}/icons/hicolor >/dev/null 2>&1 || :
exit 0
