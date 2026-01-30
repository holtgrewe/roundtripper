# roundtripper

Roundtripping with Confluence

## Setup

Setup Python with uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.13
```

Clone the repository

```bash
git clone https://github.com/mholtgrewe/roundtripper.git
```

Run Tests

```bash
cd roundtripper
uv sync --group dev
make test
```

## Development

### Check Code Quality

```bash
make check
```

### Format Code

```bash
make fix
```

### Run Tests

```bash
make test
```

### Update Dependencies

```bash
make lock
```

## Usage

```bash
roundtripper --help
```
