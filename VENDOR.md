# Vendored third-party files

Update a file only together with its row here (`openssl dgst -sha384 -binary <file> | openssl base64 -A`).
`tests/unit/test_vendor_hashes.py` fails if a file and its recorded hash drift apart.

| File | Version | Source | SHA-384 (base64) |
|------|---------|--------|------------------|
| `app/ui/static/htmx.min.js` | 2.0.8 | https://unpkg.com/htmx.org@2.0.8/dist/htmx.min.js | `sha384-/TgkGk7p307TH7EXJDuUlgG3Ce1UVolAOFopFekQkkXihi5u/6OCvVKyz1W+idaz` |
| `tests/integration/ui/axe.min.js` | 4.14.0 | https://cdn.jsdelivr.net/npm/axe-core@4.14.0/axe.min.js | `sha384-lFUXB8tI4BaTE1bqxH9eeAXON2NH1qsdAhs7S5L++nUNP5QOy+hwr0C3TYEJUEl0` |
