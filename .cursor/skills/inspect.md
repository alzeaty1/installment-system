---
name: "Inspect"
description: "Analyze codebase: lines of code, languages, structure"
---

Analyze the codebase structure.

## What to report:
1. Total lines of code (by language)
2. File count per language
3. Code vs comment ratio
4. Project structure overview (key directories)
5. Largest files
6. Complexity hotspots (files with most code)

## Commands:
```bash
# Full breakdown (exclude deps)
pygount --format=summary --folders-to-skip=".git,node_modules,venv,.venv,__pycache__,dist,build" .

# Python only
pygount --suffix=py --format=summary --folders-to-skip=".git,venv" .

# Top 10 largest files
find . -type f -name "*.py" ! -path "*/venv/*" ! -path "*/.*" -exec wc -l {} + | sort -rn | head -10
```
