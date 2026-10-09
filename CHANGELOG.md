## [1.2.0]

### Added

- **Unseen films** - `filmweb unseen USER --vod PROVIDER` lists top-rated films on a VOD platform that the user has not rated, with `--since`, `--min-votes` and `--limit` filters (#1)
- **Unseen filters** - `--until YEAR`, repeatable `--genre` (Polish or English name, any match), repeatable `--vod`, and `--type serial` for series
- **Logged-in session** - optional `FILMWEB_COOKIE` env var, needed to read more than 100 user votes

### Changed

- **Faster unseen** - the search filters by vote count on the server, reads pages in rate order and stops once enough titles are found (Netflix since 2011: about 35 s down to 3 s)
- **Request limit** - at most 10 requests to Filmweb run at once

### Fixed

- **Series years** - `--since`/`--until` for series match the first-aired year, not any year on air
- **Login errors** - a missing, expired or broken cookie gives one clear message instead of a traceback
- **Input checks** - `--limit` below 1, negative `--min-votes` and `--since` later than `--until` are usage errors
- **Genre names** - matched without Polish diacritics, e.g. `kryminal`

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
