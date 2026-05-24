# SonarQube (local)

Static analysis for Python sources using a **local SonarQube Community Edition** instance. This stack is isolated from the app `docker-compose.yml` so you can run Postgres/SQS/worker without SonarQube.

Based on [Try out SonarQube](https://docs.sonarsource.com/sonarqube-server/9.9/try-out-sonarqube).

## Persistence

SonarQube stores data on the host under `docker/sonarqube/` (bind mounts for `data`, `extensions`, and `logs`). These directories are gitignored. `docker compose -f docker-compose.sonar.yml down` keeps your instance; delete the folders under `docker/sonarqube/` to reset.

## 1. Start SonarQube

```powershell
docker compose -f docker-compose.sonar.yml up -d
```

Wait until the UI is up: [http://localhost:9000](http://localhost:9000) (first boot can take 1–2 minutes).

Default login: `admin` / `admin` (you will be prompted to change the password).

## 2. Create project and token

1. **Create project** → manual → Project key: `fh` (must match `sonar.projectKey` in `sonar-project.properties`).
2. **Generate a token** under *Provide a token* and copy it.
3. Add to `.env` (from `.env.example`):

   ```env
   SONAR_TOKEN=squ_...
   SONAR_HOST_URL=http://localhost:9000
   ```

   `SONAR_HOST_URL` is used by the scanner CLI on the host. The Docker-based scan script uses `host.docker.internal` by default on Windows/macOS so the scanner container can reach SonarQube on the host port `9000`.

## 3. Run analysis

**Windows (PowerShell):**

```powershell
.\scripts\sonar-scan.ps1
```

**macOS / Linux:**

```bash
./scripts/sonar-scan.sh
```

**Make:**

```bash
make sonar-up     # start server
make sonar-scan   # run scanner (requires SONAR_TOKEN in .env)
make sonar-test   # up + wait for healthy + scan (integration smoke test)
```

After a successful run, open the project in SonarQube to review issues, security hotspots, and *new code* quality (Clean as You Code).

## 4. Stop SonarQube

```powershell
docker compose -f docker-compose.sonar.yml down
```

Data is kept under `docker/sonarqube/`. To wipe the instance, stop the container and delete those directories.

## Troubleshooting

| Issue | Fix |
| --- | --- |
| SonarQube container exits on start | Ensure `SONAR_ES_BOOTSTRAP_CHECKS_DISABLE=true` (already set in `docker-compose.sonar.yml`). On Linux, you may need higher `vm.max_map_count` — see SonarQube server docs. |
| Scanner cannot reach server | On Windows/macOS Docker Desktop, use default `host.docker.internal:9000` in `scripts/sonar-scan.ps1`. On Linux, set `SONAR_HOST_URL=http://localhost:9000` and use host networking or `--network host` if needed. |
| Git Bash: invalid working directory `C:/Program Files/Git/usr/src` | Fixed in `scripts/sonar-scan.sh` via `MSYS_NO_PATHCONV=1`. Re-run `./scripts/sonar-scan.sh` or `make sonar-scan`. |
| PowerShell `make sonar-scan` error 193 | `make` cannot execute `.ps1` directly; the Makefile invokes PowerShell explicitly on Windows. |
| Invalid token / 401 | Regenerate token in SonarQube UI; update `.env`. |
| Project key mismatch | Project key in the UI must equal `sonar.projectKey` in `sonar-project.properties`. |

## Optional: coverage

To feed test coverage into SonarQube later:

1. Run tests with coverage, e.g. `uv run pytest --cov=app --cov-report=xml`.
2. Uncomment/add in `sonar-project.properties`: `sonar.python.coverage.reportPaths=coverage.xml`.
3. Add `coverage.xml` to `.gitignore` if generated locally.
