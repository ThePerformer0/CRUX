# Améliorations Futures de CRUX issues de la Vérité Terrain

Document consignant les pistes d'amélioration identifiées lors de la validation expérimentale sur les cas réels du noyau Linux et de Memcached.

---

## 1. Détection des Libérations Orphelines (Issu du Cas M01 — Memcached `crawler.c`)

### Problème identifié
`src/analysis/site_extractor.py` instancie des sections critiques $[L, U]$ uniquement à partir d'une instruction d'acquisition (`lock`). Un appel `unlock` orphelin (présent dans le code sans aucun `lock` local ni hérité dans le lockset d'entrée) n'est pas capturé par le scanner.

### Solution technique à implémenter
* Ajouter dans `SiteExtractor` une passe de collecte des instructions `unlock` non appairées.
* Si $\text{entry\_lockset}(f) = \emptyset$ et qu'un `unlock(m)` est rencontré sans `lock(m)` dans le graphe de flot de contrôle en amont, lever une anomalie **`UNPAIRED_RELEASE` / `EMPTY_CS`**.

---

## 2. Granularité Champ-par-Champ et Sémantique des Structures (Issu du Cas L01 — Linux Bluetooth `hci_conn.c`)

### Problème identifié
Dans `src/core/classifier.py`, la règle `READ_ONLY` est inhibée dès qu'un `share_conflict` existe sur l'objet parent (`conn` ou `hdev`). Parce que d'autres fonctions du pilote modifient la structure globale `conn`, CRUX conserve保守ement le verrou, alors que `hci_conn_get_phy()` n'accède qu'aux champs scalaires indépendants (`tx_phy`, `rx_phy`) et que le verrou `hdev->lock` ne protégeait même pas ces champs.

### Solution technique à implémenter
* **Analyse d'alias sensible aux champs (`Field-Sensitive GEP`)** : Découpler les conflits de partage au niveau des champs spécifiques plutôt qu'au niveau du pointeur de structure global.
* **Corrélation Verrou-Champ** : Vérifier si le mutex acquis (`hdev->lock`) correspond au domaine de protection des champs lus dans la section critique.

---

## 3. Prise en compte des Protocoles de Variables de Condition (Issu des Faux Positifs Memcached)

### Problème identifié
CRUX a classé plusieurs verrous de terminaison de thread (`stop_conn_timeout_thread`, `stop_threads`) comme `REDUNDANT` ou `EMPTY_CS` car ils ne modifient qu'un simple flag entier (`do_run = 0`). Or, ce flag est le prédicat d'un `pthread_cond_wait`/`pthread_cond_signal`, qui requiert impérativement la tenue du mutex pour éviter les réveils perdus (*lost wake-up*).

### Solution technique à implémenter
* Associer formellement les variables de condition (`pthread_cond_t`) à leur mutex compagnon (`pthread_mutex_t`).
* Immuniser contre l'élision toute section critique contenant un `pthread_cond_signal` ou `pthread_cond_broadcast` modifiant le prédicat de garde.
