# Entrypoint gunicorn imports: `gunicorn backend.wsgi:app`. See backend/README.md.
from deploy.config import DeployConfig

from .app import create_app

app = create_app(DeployConfig.from_env())
