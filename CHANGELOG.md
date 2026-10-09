## [Unreleased]

### Added

- **Unseen films** - `filmweb unseen USER --vod PROVIDER` lists top-rated films on a VOD platform that the user has not rated, with `--since`, `--min-votes` and `--limit` filters
- **Logged-in session** - optional `FILMWEB_COOKIE` env var, needed to read more than 100 user votes

## [1.1.0]

### Added

- **Top roles** - display top roles/rankings for given content

### Changed

- **Dev tooling** - bumped pre-commit hooks, dev requirements, and GitHub Actions versions

## [1.0.0]

### Added

- **Search** - search films, series, games, characters, people, and worlds via Filmweb API
- **Content info** - display title, year, duration, genres, ratings (user and critics), full description
- **VOD providers** - show where content is available to stream, with compact and full views
- **Person preview** - show person details, known-for titles
- **Character preview** - show character details and where they appear
- **World preview** - show world details
- **Interactive search** - `filmweb-fzf` script for fuzzy finding via fzf
