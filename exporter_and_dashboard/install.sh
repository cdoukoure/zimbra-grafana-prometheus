#!/bin/bash

set -e

# Variables
EXPORTER_USER="zimbra"
EXPORTER_DIR="/opt/zimbra-exporter"
EXPORTER_SCRIPT="zimbra10_prometheus_exporter.py"
EXPORTER_PORT=9093

echo "==> Installation des dépendances Python"
if command -v yum &>/dev/null; then
    yum install -y python3 python3-pip
elif command -v apt-get &>/dev/null; then
    apt-get update
    apt-get install -y python3 python3-pip
else
    echo "Gestionnaire de paquets non supporté. Installez python3 et pip manuellement."
    exit 1
fi

pip3 install --upgrade psutil requests flask prometheus_client urllib3

echo "==> Création du dossier $EXPORTER_DIR"
mkdir -p "$EXPORTER_DIR"
chown "$EXPORTER_USER":"$EXPORTER_USER" "$EXPORTER_DIR"

echo "==> Copie du script $EXPORTER_SCRIPT vers $EXPORTER_DIR"
cp "$EXPORTER_SCRIPT" "$EXPORTER_DIR/"
chown "$EXPORTER_USER":"$EXPORTER_USER" "$EXPORTER_DIR/$EXPORTER_SCRIPT"
chmod 755 "$EXPORTER_DIR/$EXPORTER_SCRIPT"

echo "==> Création du service systemd"

cat >/etc/systemd/system/zimbra10-prometheus-exporter.service <<EOF
[Unit]
Description=Zimbra Exporter for Prometheus
After=network.target

[Service]
User=$EXPORTER_USER
Group=$EXPORTER_USER
WorkingDirectory=$EXPORTER_DIR
ExecStart=/usr/bin/python3 $EXPORTER_DIR/$EXPORTER_SCRIPT
Restart=always

[Install]
WantedBy=multi-user.target
EOF

echo "==> Reload systemd, enable et démarrer le service"
systemctl daemon-reload
systemctl enable zimbra10-prometheus-exporter.service
systemctl restart zimbra10-prometheus-exporter.service

echo "==> Vérification du service"
systemctl status zimbra10-prometheus-exporter.service --no-pager

echo "==> Exporter déployé et en cours d'exécution sur le port $EXPORTER_PORT"
