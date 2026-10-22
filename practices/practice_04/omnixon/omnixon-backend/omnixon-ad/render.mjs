// FILM_LANG=en|ru node render.mjs events -> out/events-<lang>.json (the cue sheet music.py scores to)
// FILM_LANG=en|ru node render.mjs video  -> out/omnixon-ad-<lang>.mp4 (1920x1080, 60 fps, with out/music-<lang>.wav); SUB=5 sub-frames of motion blur
import { chromium } from '../omnixon/omnixon-frontend/node_modules/playwright/index.mjs';
import { spawn } from 'node:child_process';
import { writeFileSync, existsSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const mode = process.argv[2] || 'video';
const SUB = +(process.env.SUB || 5), LANG = process.env.FILM_LANG || 'en';
const url = pathToFileURL(join(here, 'index.html')).href + `?render&lang=${LANG}&sub=${mode === 'events' ? 1 : SUB}`;
const browser = await chromium.launch({ channel: 'chrome' });

async function openPage() {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  page.on('pageerror', e => console.error('PAGE ERROR', e.message));
  await page.goto(url);
  await page.evaluate(() => window.__film.ready);
  return page;
}

if (mode === 'events') {
  const page = await openPage();
  const film = await page.evaluate(() => ({ dur: window.__film.DUR, beat: window.__film.BEAT, slam: window.__film.slam, sections: window.__film.sections, events: window.__film.events }));
  writeFileSync(join(here, `out/events-${LANG}.json`), JSON.stringify(film));
  console.log(`${film.events.length} cues, ${film.dur}s -> out/events-${LANG}.json`);
} else {
  const probe = await openPage(); const dur = await probe.evaluate(() => window.__film.DUR); await probe.close();
  const fps = 60, N = fps * dur, WORKERS = 6;
  const audio = join(here, `out/music-${LANG}.wav`);
  const args = ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'png', '-i', '-'];
  if (existsSync(audio)) args.push('-i', audio, '-c:a', 'aac', '-b:a', '320k', '-shortest');
  args.push('-c:v', 'libx264', '-preset', 'slow', '-crf', '15', '-pix_fmt', 'yuv420p', '-profile:v', 'high',
    '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-movflags', '+faststart', join(here, `out/omnixon-ad-${LANG}.mp4`));
  const ff = spawn('ffmpeg', args, { stdio: ['pipe', 'inherit', 'inherit'] });
  const done = new Promise((res, rej) => ff.on('close', c => (c === 0 ? res() : rej(new Error('ffmpeg exited ' + c)))));

  const pages = await Promise.all(Array.from({ length: WORKERS }, openPage));
  const ready = new Map();
  let nextToWrite = 0, nextToRender = 0, wake = null;
  const t0 = Date.now();

  async function worker(page) {
    while (true) {
      // keep a bounded window of frames in memory
      while (nextToRender - nextToWrite > WORKERS * 4) await new Promise(r => setTimeout(r, 5));
      const f = nextToRender++;
      if (f >= N) return;
      const b64 = await page.evaluate(f => { window.__film.render(f / 60); return document.getElementById('c').toDataURL('image/png').split(',')[1]; }, f);
      ready.set(f, Buffer.from(b64, 'base64'));
      if (wake) wake();
    }
  }
  async function writer() {
    while (nextToWrite < N) {
      if (!ready.has(nextToWrite)) { await new Promise(r => (wake = r)); wake = null; continue; }
      const buf = ready.get(nextToWrite); ready.delete(nextToWrite);
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      nextToWrite++;
      if (nextToWrite % 120 === 0) console.log(`frame ${nextToWrite}/${N}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
    }
    ff.stdin.end();
  }
  await Promise.all([...pages.map(worker), writer()]);
  await done;
  console.log(`done in ${((Date.now() - t0) / 1000).toFixed(0)}s -> out/omnixon-ad-${LANG}.mp4`);
}
await browser.close();
