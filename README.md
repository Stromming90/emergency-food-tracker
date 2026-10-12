# Emergency Food Storage Tracker

Track your emergency food storage: keep a permanent product list, record
purchases with best-before dates, and see alerts at **6 months**, **3 months**
and **1 month** before each item expires.

Two interfaces over the same CSV data:

- **Web UI** (`server.py`) — a simple web page, ideal for Docker / TrueNAS.
- **CLI** (`tracker.py`) — for local use and shell scripts / cron.

Data is plain CSV (`data/products.csv`, `data/inventory.csv`) — commit it to
git to keep full history of your storage.

## Run with Docker (recommended)

```bash
docker compose up -d
```

Then open **http://localhost:8000**. The container is ~150 MB, needs no
external Python packages, and writes all data to a mounted volume.

The image is `python:3.12-slim`; the web server uses only the Python standard
library, so it is trivial to audit and maintain.

### TrueNAS (SCALE) installation

1. Create a dataset, e.g. `tank/apps/food-tracker` for the app files and
   `tank/apps/food-tracker-data` for the CSV data.
2. Copy this repo into `tank/apps/food-tracker` (or clone it there).
3. Point the compose volume at your data dataset by editing
   `docker-compose.yml`:

   ```yaml
   volumes:
     - /mnt/tank/apps/food-tracker-data:/data
   ```

4. TrueNAS SCALE: **Apps → Discover → Install via YAML**, paste the compose
   file contents (or use `docker compose up -d` from a shell on the host).
5. Access the UI at `http://<truenas-ip>:8000`.

To keep data on the host even without a dataset path change, the default
compose already mounts `./data`, which is the repo's own `data/` folder —
fine for a quick start, but a dedicated dataset is recommended for backups.

### Back up your data

Because everything is CSV, a backup is just a copy of two files:
`data/products.csv` and `data/inventory.csv` (or your `/data` volume).
TrueNAS snapshot tasks on the data dataset work great too.

## Web UI

Open the app in any browser (works on phones — the layout adapts):

- **Add product to list** — extend your permanent product list any time.
- **Record a purchase** — pick a product, set the best-before date, quantity.
- **Inventory** — sorted by best-before date, with a colour badge per item:
  🟩 fine · 🟨 &lt; 6 months · 🟠 &lt; 3 months · 🔴 &lt; 1 month · ⚫ expired.
- ✕ buttons remove individual purchases or products from the list.

The page refreshes itself every minute, so badges update as time passes.

There is **no login** by default — keep it on your LAN, or put it behind a
reverse proxy with authentication (TrueNAS has built-in options for this,
e.g. in the *Traefik/ingress* or via an auth middleware).

## CLI usage

```bash
# Data dir defaults to ./data — same files the web app uses.
python3 tracker.py add-product "Canned beans" --category Canned
python3 tracker.py buy "Canned beans" 2028-06-01 --quantity 6
python3 tracker.py list-products
python3 tracker.py inventory            # sorted by best-before date
python3 tracker.py alerts               # current 6/3/1-month warnings
python3 tracker.py check                # print + desktop notification
```

## Data files

| File | Contents |
|---|---|
| `data/products.csv` | Permanent product list: name, category, date added |
| `data/inventory.csv` | Stock: id, product, best_before, quantity, date added |

## Development run (no Docker)

```bash
DATA_DIR=./data python3 server.py
# or simply:
python3 server.py
```

## Git

```bash
git init
git add .
git commit -m "Initial food storage tracker"
```

Commit regularly — every purchase changes only the CSVs, so diffs show
exactly what changed.
