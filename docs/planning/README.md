# Planning docs (historical)

These are the original hackathon-rebuild plan: context, product spec, engineering spec, demo design and the
task checklist. The shipped app evolved from them; the main differences:

- **One page instead of four.** Logo → dish (sales CSV pick or photo) → Action! → Post to YouTube, plus a video history.
- **8-second Shorts** by default (5.7s of AI motion + an animated logo ending), narrated, no on-screen presenter.
- **Gemini Omni replaces Veo** for image-to-video (Veo is no longer offered on the Gemini API for our key).
- **Each visitor connects their own YouTube channel** (stored encrypted in their browser, never on the server).
- **Hosting:** Vercel (frontend) + Render free tier (API), instead of a paid host with a persistent disk.

See the top-level `README.md` for how the app works today.
