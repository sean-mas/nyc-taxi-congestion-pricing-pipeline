# Before making this repo public

The repo is private. Making it public is Sean's decision; nothing here has been done yet. This lists what must change first, and why.

## Must change

1. **Remove `solution/`.** It's the course's reference solution, not this project's work, and it comes from a private course repo (`neuefische/mle-data-pipeline-project`). Then clean up what points at it:
   - `pyproject.toml`: drop `extend-exclude = ["solution"]` under `[tool.ruff]` and `"solution/src"` from `root` under `[tool.ty.environment]`.
   - `README.md`: the `solution/` line in "Project structure".
   - `docs/decisions.md`: decision 1 mentions the reference solution; keep the idea, drop the pointer.
2. **Remove `course/`.** The brief is course material from the same private repo. Then:
   - `README.md`: the sentence linking to `course/project-brief.md` (keep a plain mention of the course, without the link) and the `course/` line in "Project structure".
   - `README.md`: the "Course reflection" block at the bottom holds the course answers. Keep it or drop it for the public version; the Context section already explains where the project comes from.
   - `.github/pull_request_template.md` is the course's submission checklist. Delete it, or replace it with a short template of your own.
3. **Keep `LICENSE` as it is.** It's the MIT license from the course template, copyright neuefische GmbH. MIT allows reusing and publishing the code only if that copyright line and the permission text stay. You may add your own line under it for your changes (for example `Copyright (c) 2026 Sean Kress`), but don't remove or replace neuefische's line.
4. **Start the public repo without the old history.** Deleting files in a new commit doesn't remove them from git history: anyone can open an old commit and read `solution/` and `course/`. The history also holds the template's commits by five course authors, with their email addresses, from a repo that is private.

   | Option | What it means | |
   |---|---|---|
   | (a) Flip this repo to public after deleting the folders | Publishes the private course material through the history | ✗ |
   | (b) New public repo from a clean copy of the final files | One first commit; this private repo keeps the pull request history | ✓ my pick |
   | (c) Rewrite this repo's history with `git filter-repo` | Keeps your commits; changes every commit ID and leaves the old pull requests pointing at commits that no longer exist | |

   My pick is (b): it's the only option that can't leak anything, and it takes minutes. Link the new repo from your CV, and keep this one private as the full record.

## Should check

- **The course's rules.** Ask Spiced/neuefische whether students may publish project work built on their template. The template repo being private suggests they care.
- **Your email address.** Commits use `sean.kress.pm@gmail.com`. In a public repo anyone can read it. To hide it, commit with your GitHub `noreply` address (GitHub settings → Emails).
- **Links after the move.** The CI badge in `README.md` points at `sean-mas/mle-data-pipeline-project`. Update it if the public repo gets a new name, for example `nyc-green-taxi-congestion-pricing`.
- **Name, description and topics for the public repo.** The project is now called `nyc-taxi-congestion-pricing-pipeline` (title in `README.md`, `name` in `pyproject.toml`). Use the same name for the public repo, so it says what's inside: the data, the question and the skill. Suggested description: *ELT pipeline (Postgres, dbt, Prefect) testing whether NYC congestion pricing changed Green Taxi trips and revenue.* Suggested topics: `data-engineering`, `elt`, `dbt`, `prefect`, `postgres`, `docker`, `python`, `nyc-taxi`.
- **The "How it was built" line** in the README's Context section says the project was built with Claude Code. Keep it if you're comfortable with that; it's honest, and the commit history shows it anyway.

## Already fine

- **No secrets in git.** `.env` is ignored; `.env.example` only holds the local Docker defaults (`postgres`/`postgres`), which protect nothing outside your laptop.
- **No personal paths** in the notebook outputs.
- **Data** isn't in git (`data/raw/` and `data/processed/` are ignored), and the NYC TLC trip records are public anyway.
