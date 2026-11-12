# CLAUDE.md

Start every session by reading **`HANDOFF.md`**, then the latest entries of **`WORKLOG.md`**. HANDOFF covers the
current status, open problems, how to run everything, and the user's preferences. Update it before you finish.

Hard rules:
- **Log everything you do in `WORKLOG.md`** (the user's rule, for future agents). Add an entry for every piece of
  work, as you go and not only at the end: what was asked, what you changed and why, the files touched, the commands
  run, how you checked it, and what is left undone or undecided. Include failed attempts and things you chose not to
  do. Entries are append-only: never rewrite or delete an older one; correct it with a new entry. `HANDOFF.md` stays
  the summary of the current state; `WORKLOG.md` is the history.
- Never overwrite the user's art (`art/reference_*.png`, `art/stamps/*`) or their edited Tiled map
  (`tiled/maps/*.tmj`). Ask before using `blueprint.py --force` or deleting a stamp file.
- Free tools only, and flag any paid step. Animate only flags and grass.
- Don't stitch whole AI scene images. Buildings are stamps cut from the user's images; the ground is tiles.
- Run Python scripts with plain `python3` from the repo root (not `-I`: Pillow is in the user's site-packages).
