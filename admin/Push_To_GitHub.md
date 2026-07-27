# Pushing to GitHub

The repository is already initialised and committed locally. You only need to create an empty repo on GitHub and push to it. Five minutes.

---

## Step 1. Create the repository on GitHub

1. Go to **github.com/new** (sign in first).
2. **Repository name:** `usdzar-forecasting` (or anything sensible).
3. **Description:** `SES x Codera Analytics Hackathon 2026. One-month-ahead USDZAR forecasts, team Spurious Decision.`
4. **Public.** The judges have to be able to open it without an invitation. If you make it private, you must add each judge as a collaborator, and any one of them failing to get access costs you marks.
5. **Do not** tick "Add a README", "Add .gitignore" or "Choose a license". The repo already has what it needs, and adding files here creates a conflict you would have to resolve under time pressure.
6. Click **Create repository**.

## Step 2. Push

GitHub will show you a page with commands. Ignore it and use these instead, because your commit already exists.

Open **Command Prompt** (Windows key, type `cmd`, Enter) and run these one at a time. Replace `YOURNAME` with your GitHub username and `usdzar-forecasting` with the repo name if you chose a different one.

```
cd C:\Users\aakas\Documents\Projects\Hackathon
git remote add origin https://github.com/YOURNAME/usdzar-forecasting.git
git branch -M main
git push -u origin main
```

If `git` is not recognised, install Git for Windows from **git-scm.com/download/win**, accept all the defaults, then close and reopen Command Prompt and try again.

## Step 3. Authentication

On the first push a browser window opens and asks you to sign in to GitHub. Do that and it will complete.

If instead it asks for a username and password in the terminal, GitHub will reject your account password. You need a token:

1. Go to **github.com/settings/tokens** → Generate new token (classic).
2. Note: `hackathon push`. Expiration: 7 days. Tick the **repo** scope.
3. Generate, copy the token.
4. Paste it as the **password** when the terminal asks. Your GitHub username is the username.

## Step 4. Check it before you paste the link

Open the repository page in a browser and confirm:

- [ ] The README renders with the results table at the top.
- [ ] `report/Project_Report.pdf` opens when clicked.
- [ ] `presentation/Deck.pptx` is there (GitHub will not preview it; that is normal).
- [ ] `data/processed/forecast_log.csv` opens and shows 261 rows.
- [ ] `code/` contains 12 files.
- [ ] The repo is **Public**. Check the label next to the repo name.

Then paste the URL into the submission form.

---

## What is in the repository, and what is not

**Included:** all code, the raw data, every processed output including the full forecast log, all charts, the report PDF, the deck, the presentation script, the original rules and rubric, and the project admin notes.

**Excluded on purpose:**

| Excluded | Why |
|---|---|
| `presentation/node_modules/` | 7.3 MB of installed dependencies. Anyone can restore them with `npm install`. Committing them is considered poor practice. |
| `submission/` and `submission.zip` | Derived packaging. Every file inside is already in the repo. Rebuild with `python code/make_submission.py`. |
| `report/Complete_Project_Guide.pdf` | Your personal study notes, not part of the submission. |
| `data/processed/members_cache.csv` | A regenerated intermediate. |
| `__pycache__/` | Python bytecode. |

If you decide you want the study guide public after all, delete that line from `.gitignore`, then `git add report/Complete_Project_Guide.pdf && git commit -m "add project guide" && git push`.

---

## If you change anything after pushing

```
cd C:\Users\aakas\Documents\Projects\Hackathon
python code/final_check.py
git add -A
git commit -m "describe what changed"
git push
```

The link stays the same, so you do not need to resubmit the form.
