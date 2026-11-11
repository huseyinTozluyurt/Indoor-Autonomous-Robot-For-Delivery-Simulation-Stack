# Project website

React + Vite one-page site that explains the indoor delivery robot, built from the six reports
(`../reports/figures` and the PDFs in `../docs/reports` are copied into `public/` by `scripts/copy-assets.mjs` before every
`dev` and `build`).

```bash
cd site
npm install
npm run dev        # http://localhost:5173
npm run build      # static site in dist/
```

## GitHub Pages

`.github/workflows/deploy-site.yml` builds `site/` and deploys `site/dist` on every push to `main`
that touches `site/` or `reports/`. Turn it on once in the repository: **Settings → Pages → Source:
GitHub Actions**. The build uses a relative base path, so it works at
`https://<user>.github.io/<repo>/` whatever the repository is called.

The workflow needs `reports/figures/` and `docs/reports/*.pdf` to be committed.

## Adding the simulation video

The **Video** section shows a "coming soon" panel until a video is set in `src/data.js` → `simVideo`:

- **File in the repo:** put it at `public/video/simulation.mp4` (H.264 MP4, keep it under ~50 MB; GitHub
  rejects files over 100 MB) and set `src: 'video/simulation.mp4'`.
- **YouTube (better for long or large videos):** upload it and set `youtube: '<video id>'`.

Gazebo screenshots for the Simulation section are in `public/gazebo/` (cropped from the original screen captures).
