# BlablaCook

La référence métier est `BlablaCook_Prompt_Codex.md`. Le guide de démo et les conventions se trouvent dans `README.md`.

- Installer avec `python3 -m venv .venv` puis `.venv/bin/python -m pip install -r requirements.txt`.
- Démarrer avec `.venv/bin/python -m blablacook`.
- Vérifier avec `.venv/bin/python -m pytest -q`. Les tests utilisent des bases temporaires et une horloge injectable.
- Les décisions de réservation et leurs effets sont centralisés dans `blablacook/domain.py`. Garder les projections publiques et personnelles explicites.
