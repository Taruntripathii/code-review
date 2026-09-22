#!/bin/sh
# Run pending DB migrations, then exec whatever command was given (CMD or a
# compose `command:` override). Set as ENTRYPOINT so migrations run regardless
# of which service (api, dashboard) is being started.
set -e

echo "Running database migrations..."
uv run alembic upgrade head

exec "$@"
