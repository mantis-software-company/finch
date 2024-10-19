PKG_VERSION=$1

mkdir -p dist/linux/deb/DEBIAN
mkdir -p dist/linux/deb/usr/local/bin
mkdir -p dist/linux/deb/usr/share/applications
mkdir -p dist/linux/deb/usr/share/icons
mkdir -p dist/linux/deb/usr/lib/python3/dist-packages

cat <<EOF > dist/linux/deb/DEBIAN/control
Package: finch-s3-client
Version: $PKG_VERSION
Section: base
Priority: optional
Architecture: all
Depends: python3-pyqt5, python3-boto3, python3-keyring, python3-slugify
Maintainer: Furkan Kalkan <furkankalkan@mantis.com.tr>
Description: Open source and cross-platform GUI client for Amazon S3 and compatible storage platforms.
EOF

pip install --target=dist/linux/deb/usr/lib/python3/dist-packages --no-deps .
mv dist/linux/deb/usr/lib/python3/dist-packages/bin dist/linux/deb/usr/local/
sed -i '1s|^.*|#!/usr/bin/python3|' dist/linux/deb/usr/local/bin/finch

cp icon.png dist/linux/deb/usr/share/icons/finch.png

cat <<EOF > dist/linux/deb/usr/share/applications/finch.desktop
[Desktop Entry]
Name=Finch S3 Client
Comment=Open source and cross-platform GUI client for Amazon S3 and compatible storage platforms.
Exec=/usr/local/bin/finch
Icon=/usr/share/icons/finch.png
Terminal=false
Type=Application
Categories=Network;Development;Utility;FileManager
EOF

dpkg-deb --build dist/linux/deb "dist/linux/finch-${PKG_VERSION}-linux-all.deb"