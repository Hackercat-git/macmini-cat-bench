## What does this add?
- [ ] New run folder `runs/<run-id>/` (only that folder)
- [ ] New or changed tasks (`python3 -m catbench validate` passes)
- [ ] New model in `models.toml` (source of the weights named below)
- [ ] Other:

## Machine and settings
Chip, RAM, macOS, Ollama version, any non-default setting:

## Checks
- [ ] `python3 -m unittest discover -s tests -t .` passes
- [ ] `python3 -m catbench report --run-id <id> --site /tmp/site` builds
