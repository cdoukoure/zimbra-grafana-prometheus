# 📡 Zimbra Exporter pour Prometheus & Grafana

Un **exporter Prometheus** avancé développé en **Python 3**, destiné au monitoring complet d'une infrastructure **Zimbra FOSS 10 multi-nœuds** (MTA / Proxy / Mailstore / LDAP). Il expose des métriques détaillées pour la supervision via Grafana.

---

## 🎯 Objectifs

- Supervision des services Zimbra (status, ports, webmail, queues, quota…)
- Export des métriques système (CPU, RAM, disque, I/O, réseau)
- Intégration **simple et native** avec Prometheus & Grafana
- Support de l’édition **Zimbra Open Source** (FOSS 10+)
- Déploiement léger via **systemd** ou Docker (optionnel)

---

## 🔧 Fonctionnalités

| Catégorie           | Métriques Exportées                              |
|---------------------|---------------------------------------------------|
| **Système**         | CPU %, Load avg, RAM, swap, disques, réseau       |
| **Zimbra Services** | Status `zmcontrol`, ports écoutés                 |
| **Mailboxes**       | Nombre total et actifs (login < 30j), quotas      |
| **MTA/Postfix**     | Files d’attente actives et différées              |
| **Jetty/Webmail**   | Santé de Jetty (API healthcheck), latence         |
| **ClamAV/Amavis**   | Process actif, files temporaires                  |
| **Logger MySQL**    | Connexions ouvertes au logger                     |

---

## 📊 Dashboard Grafana

> Un dashboard prêt à l'emploi est fourni : [`zimbra10-grafana-prometheus.json`](./exporter_and_dashboard/zimbra10-grafana-prometheus.json)

Il contient :
- Vue par rôle (mailbox, mta, proxy, ldap)
- Graphiques pour l'activité des comptes et des files d’attente
- Panel sur la santé Jetty, quota, amavis, etc.
- Alertes configurables via Prometheus Rules

---

## 🚀 Déploiement rapide

### 1. Installation 

```bash
git clone https://github.com/cdoukoure/zimbra-grafana-prometheus
cd zimbra-grafana-prometheus
sudo ./install.sh
