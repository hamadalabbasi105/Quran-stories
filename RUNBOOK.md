# Daily Story runbook (@al.quran.kareem105)

The 7 AM scheduled task follows this file. Change the rules here, not in the task.

## Files
- `render.py`: makes the slides. `python3 render.py content.json OUT_DIR` writes `1.jpg 2.jpg 3.jpg` (+ `friday.jpg` on Fridays). Exit code 2 = do not post.
- `fonts/`: Amiri Quran (verses), Tajawal (everything else). Both under the SIL Open Font License.
- `YYYY-MM-DD/`: that day's `content.json` and slides.
- `posted.json`: Instagram media ids per date. Use it to avoid double-posting.

## Daily steps (Bahrain date)
1. If `posted.json` already has today's date with all slides, stop. Never post the same day twice.
2. Write `YYYY-MM-DD/content.json` from the same content as the morning email:
   - `ayahs`: `{"surah": N, "name": "<Arabic surah name>", "from": A, "to": B}`. The verse text is downloaded by render.py from the King Fahd Complex Hafs edition. Never type verse text into content.json.
   - `hook`: a short curiosity question (no emoji).
   - `meaning` + `meaning_src`, `story` + `story_src`, `lesson`: same wording as the email. Quran quoted inside the story goes in «» quotes.
   - `date_label`: e.g. "الثلاثاء ٢٤ نوفمبر".
   - Fridays only: `friday` = `{"title": "جمعة مباركة", "items": [[text, source], ...], "closing": "..."}`. 2–3 Friday sunnahs or a Friday dua, each with an authentic source (e.g. Kahf: al-Hakim/al-Bayhaqi, graded sahih by al-Albani; salawat: Abu Dawud 1047; hour of response: al-Bukhari 935, Muslim 852). Rotate the wording week to week.
3. Run render.py. If it prints `text too long`, shorten the story/meaning faithfully (keep the meaning, same sources) and retry, at most twice. Any other RENDER ERROR: do not post; report it.
4. Look at the three slides (Read the images) and check nothing overlaps or is cut off.
5. Commit the day's folder and push to `main`. Get the commit SHA with `git rev-parse HEAD`.
6. Post with Windsor `execute_action`, connector `instagram`, action `create_story`, account `17841455318700489`, in order 1 → 2 → 3, with
   `image_url = https://raw.githubusercontent.com/hamadalabbasi105/Quran-stories/<SHA>/YYYY-MM-DD/<n>.jpg`
   (the SHA in the URL avoids cached old images). On Fridays post `friday.jpg` as a 4th Story.
   If a post fails, retry that slide once. If it still fails, stop. Don't post later slides out of order.
7. Record the media ids in `posted.json`, commit, and push.
8. Mention the result in the morning email: Stories posted (or the exact error). On Fridays, include the download link to friday.jpg for reposting on a personal account.

## Never
- Never change account settings, follow, comment, DM or delete anything, and never start ads. Account-growth ideas go in the email as suggestions only; Hamad decides.
- Never depict prophets, angels or God. Never use unverified stories or disputed rulings.
