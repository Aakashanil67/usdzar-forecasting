# Submission checklist, Team Spurious Decision

**Deadline: Monday 27 July 2026, 23:59.** Email to `28399323@sun.ac.za`. No late submissions.
**Prize-giving: Tuesday 28 July, 18:00–21:00**, at least one team member must attend to claim a prize.

---

## Blocking, only Aakash can do these

- [ ] **Confirm both team members are registered** via the poster link. Without this, nothing else matters, the work is ineligible.
- [x] ~~Obtain the submission form.~~ Done. **It asks for a GitHub link.**
- [ ] **Complete the submission form** with team name *Spurious Decision* and both members.
- [ ] **Create the GitHub repo and push.** Follow `admin/Push_To_GitHub.md`, about five minutes. The repo must be **public**.
- [ ] **Paste the repo URL into the submission form** and check the link opens in a private/incognito window, which proves it is really public.
- [ ] **Send the form** before 23:59 Monday. Send it early, do not test the deadline.

## Before sending

- [ ] Run `python code/run_all.py` one final time (confirms everything still reproduces).
- [ ] Run `python code/make_submission.py` (rebuilds `submission/` from the current results).
- [ ] Open `submission/00_README.txt` and check the headline numbers read 0.5600 vs 0.5624.
- [ ] Zip `submission/` only if the form also asks for attachments. The GitHub repo already contains everything.

## Before presenting (Tuesday)

- [ ] **The slot is 2 to 5 minutes.** Read `presentation/Script.md` aloud twice **with a timer**. Target 4:20. If you land over 4:40, cut the third bullet on slide 2 and the robustness sentence on slide 4.
- [ ] Learn the emergency 1-minute version in case the slot is tightened on the day.
- [ ] Memorise which backup slide answers which question (table in Script.md). Present slides 1 to 5 only.
- [ ] Memorise: **0.5600 / 0.5624 / +0.42% / 261 forecasts / DM p-value 0.47**.
- [ ] Decide who presents. For a slot this short one presenter is cleaner than two.
- [ ] Work through the Q&A bank in Script.md, say the answers out loud, not just read them.
- [ ] Laptop ready with: the deck, `Project_Report.pdf`, and `forecast_log.csv` open in tabs.
- [ ] Bring a printed copy of `Project_Report.pdf`.

## Things to be ready to say

- **The opening line:** the team name is the methodology, a spurious relationship looks real in your data and isn't there in the world; the whole project was built to avoid one.
- **Volunteer the weaknesses before judges find them:** the result is not statistically significant (DM p = 0.47); AR(1) is competitive on MAE; we lose 2025 when the rand strengthened back toward the benchmark's mean.
- **Invite the code walkthrough.** It signals you want the technical defence rather than fearing it.
