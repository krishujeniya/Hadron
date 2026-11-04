"""Read-only production probes. Exit nonzero on unavailable or unsafe service state."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def probe(url: str) -> tuple[int, dict]:
    try:
        with urlopen(url, timeout=30) as response:
            raw = response.read(1_000_000)
            try:
                body = json.loads(raw)
            except (ValueError, UnicodeError):
                body = {}
            return response.status, body if isinstance(body, dict) else {}
    except HTTPError as exc:
        return exc.code, {}
    except (URLError, TimeoutError, OSError):
        return 0, {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frontend', default='https://hadron.vercel.app')
    parser.add_argument('--backend', default='https://hadron-backend.vercel.app')
    args = parser.parse_args()
    frontend, backend = args.frontend.rstrip('/'), args.backend.rstrip('/')
    targets = [frontend, backend + '/health/live', backend + '/health/ready', frontend + '/api/v1/auth/me']
    with ThreadPoolExecutor(max_workers=4) as pool:
        home, live, ready, auth = list(pool.map(probe, targets))
    services = ready[1].get('services', {})
    checks = {
        'frontend_available': home[0] == 200,
        'backend_alive': live[0] == 200 and live[1].get('status') == 'ok',
        'pipeline_ready': ready[0] == 200 and ready[1].get('pipeline_ready') is True,
        'production_environment': ready[1].get('env') == 'production',
        'worker_available': services.get('worker') == 'ok',
        'anonymous_data_denied_through_proxy': auth[0] == 401,
    }
    print(json.dumps({'checks': checks, 'http_statuses': [home[0], live[0], ready[0], auth[0]],
                      'environment': ready[1].get('env'), 'services': services, 'verdict': 'PASS' if all(checks.values()) else 'FAIL'}, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
