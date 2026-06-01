# Guide de contribution & Pull Requests

Ce document définit le workflow Git de l'équipe. Il s'applique à toute contribution sur le dépôt.

## Modèle de branches

| Branche | Rôle |
|---------|------|
| `main` | Branche stable et livrable. Protégée. Ne reçoit **que** des merges depuis `staging`. |
| `staging` | Branche d'intégration. Toutes les branches de travail y sont fusionnées et validées avant de remonter vers `main`. |
| branches de travail | Partent de `staging`, y reviennent via Pull Request. |

Flux : `feat/* | fix/* | …` → **`staging`** → **`main`** (une fois stable).

## Convention de nommage des branches

Format : `<type>/<description-courte-kebab-case>`

| Type | Usage | Exemple |
|------|-------|---------|
| `feat/` | Nouvelle fonctionnalité | `feat/fait-consultation` |
| `fix/` | Correction de bug | `fix/ingestion-deces` |
| `refactor/` | Refactoring sans changement fonctionnel | `refactor/dimension-temps` |
| `chore/` | Maintenance, config, dépendances | `chore/setup-hive` |
| `docs/` | Documentation uniquement | `docs/modele-conceptuel` |

La description doit être courte, explicite et en anglais kebab-case.

## Workflow de contribution

1. Se placer sur `staging` à jour : `git switch staging && git pull`
2. Créer sa branche : `git switch -c feat/mon-sujet`
3. Développer et committer (voir convention de commits)
4. Pousser la branche : `git push -u origin feat/mon-sujet`
5. Ouvrir une **Pull Request vers `staging`**
6. Faire relire par au moins un autre membre de l'équipe
7. Merger dans `staging` après validation
8. Quand `staging` est stable et testé → Pull Request `staging` → `main`

## Convention de commits

Format [Conventional Commits](https://www.conventionalcommits.org/) :

```
<type>: <description à l'impératif, en français>
```

Types : `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`.

Exemples :
- `feat: ajout du fait consultation`
- `fix: correction de la jointure dimension établissement`
- `docs: rédaction du modèle conceptuel`

Messages courts et directs, un commit = un changement cohérent.

## Convention des Pull Requests

- **Titre** : même format que les commits, ex. `feat: modélisation Fait_Consultation`
- **Description** : objectif, changements clés, points d'attention pour le relecteur
- Lier la tâche correspondante (ClickUp) lorsque c'est pertinent
- Une PR = un sujet ; éviter les PR fourre-tout

## Règles strictes

- **Jamais de commit direct sur `main` ni `staging`** : toujours via Pull Request.
- **1 branche = 1 sujet** : ne pas mélanger plusieurs fonctionnalités.
- **Au moins une relecture** avant tout merge.
- **Ne jamais committer de données** (voir `.gitignore`) : les données patients sont sensibles et volumineuses (2,1 Go).
- **Pas de `--force push`** sans accord explicite de l'équipe.
- Pas de secrets / identifiants dans le code : utiliser des variables d'environnement.
