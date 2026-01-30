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

### Configure Confluence

Configure your Confluence credentials and connection settings:

```bash
roundtripper confluence config
```

This will open an interactive configuration menu. Configuration is stored in `~/.config/roundtripper/config.json` following the XDG Base Directory specification.

To view your current configuration:

```bash
roundtripper confluence config --show
```

To jump directly to a specific configuration section:

```bash
roundtripper confluence config --jump-to auth.confluence
```

## Acknowledgments

This project includes code adapted from [confluence-markdown-exporter](https://github.com/Spenhouet/confluence-markdown-exporter) by Sebastian Penhouet.
