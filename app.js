document.addEventListener('DOMContentLoaded', () => {
  const $ = (id) => document.getElementById(id);
  const yearFromInput = $('yearFrom');
  const yearToInput = $('yearTo');
  const topXInput = $('topX');
  const skipYInput = $('skipY');
  const presetSelect = $('preset');
  const videoTypeCheckbox = $('videoType');
  const videoModeSpan = $('videoMode');
  const randomBtn = $('randomBtn');
  const songDisplay = $('songDisplay');

  // [top X songs, skip top Y]
  const PRESETS = {
    beginner: [5, 0],
    easy: [10, 5],
    medium: [15, 15],
    hard: [20, 30],
    extraHard: [25, 50],
    songGuru: [30, 75],
  };
  const FALLBACK_FIRST_YEAR = 2006;
  const songsByYear = {};
  let loadedYears = [];

  function intValue(input, fallback) {
    const n = parseInt(input.value, 10);
    return Number.isFinite(n) ? n : fallback;
  }

  function videoId(url) {
    const m = /(?:v=|youtu\.be\/|embed\/)([\w-]{11})/.exec(url || '');
    return m ? m[1] : null;
  }

  function el(tag, props = {}, children = []) {
    const node = Object.assign(document.createElement(tag), props);
    node.append(...children);
    return node;
  }

  function showMessage(text) {
    songDisplay.replaceChildren(el('p', { className: 'message', textContent: text }));
  }

  // Songs whose rank falls in (skip, skip + top] for every year in the range.
  function candidateSongs() {
    let from = intValue(yearFromInput, loadedYears[0]);
    let to = intValue(yearToInput, loadedYears[loadedYears.length - 1]);
    if (from > to) [from, to] = [to, from];
    const top = Math.max(1, intValue(topXInput, 5));
    const skip = Math.max(0, intValue(skipYInput, 0));
    const pool = [];
    for (let year = from; year <= to; year++) {
      (songsByYear[year] || []).forEach((song, i) => {
        const rank = song.rank || i + 1;
        if (rank > skip && rank <= skip + top) pool.push({ year, rank, song });
      });
    }
    return pool;
  }

  function randomSong() {
    const pool = candidateSongs();
    if (!pool.length) {
      showMessage('No songs match these settings. Try a wider year range or a smaller "Skip Top Y".');
      return;
    }
    const { year, rank, song } = pool[Math.floor(Math.random() * pool.length)];
    const karaokeMode = videoTypeCheckbox.checked;
    let url = karaokeMode ? song.karaoke : song.lyricVideo;
    let note = '';
    if (!videoId(url)) {
      url = karaokeMode ? song.lyricVideo : song.karaoke;
      note = karaokeMode
        ? 'No embeddable karaoke version was found for this song, so here is the lyric video.'
        : 'No embeddable lyric video was found for this song, so here is the karaoke version.';
    }
    const id = videoId(url);

    const children = [
      el('h2', { textContent: song.title || song.songTitle }),
      song.artist ? el('p', { className: 'artist', textContent: song.artist }) : '',
      el('h3', { textContent: `Rank ${rank} in ${year}` }),
    ];
    if (note) children.push(el('p', { className: 'note', textContent: note }));
    if (id) {
      children.push(
        el('div', { className: 'video-wrapper' }, [
          el('iframe', {
            src: `https://www.youtube.com/embed/${id}`,
            title: `${song.title || song.songTitle} (${karaokeMode ? 'karaoke' : 'lyric video'})`,
            allow: 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture',
            allowFullscreen: true,
            referrerPolicy: 'strict-origin-when-cross-origin', // YouTube rejects embeds without a referrer
          }),
        ]),
        el('a', {
          className: 'watch-link',
          href: `https://www.youtube.com/watch?v=${id}`,
          target: '_blank',
          rel: 'noopener',
          textContent: 'Not playing? Watch on YouTube',
        }),
      );
    } else {
      children.push(el('p', { className: 'note', textContent: 'No video is available for this song yet.' }));
    }
    songDisplay.replaceChildren(...children.filter(Boolean));
  }

  function updateVideoModeLabel() {
    videoModeSpan.textContent = videoTypeCheckbox.checked ? 'Karaoke Mode' : 'Lyric Video Mode';
  }

  async function fetchJson(path) {
    const response = await fetch(path);
    if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
    return response.json();
  }

  async function loadSongs() {
    let years;
    try {
      years = await fetchJson('years.json');
    } catch (error) {
      console.warn('years.json unavailable, probing each year instead', error);
      years = [];
      for (let y = FALLBACK_FIRST_YEAR; y <= new Date().getFullYear(); y++) years.push(y);
    }
    const results = await Promise.allSettled(years.map((year) => fetchJson(`${year}.json`)));
    results.forEach((result, i) => {
      if (result.status === 'fulfilled' && Array.isArray(result.value)) songsByYear[years[i]] = result.value;
    });
    loadedYears = Object.keys(songsByYear).map(Number).sort((a, b) => a - b);
    if (!loadedYears.length) {
      showMessage('Could not load the song lists. Please refresh the page.');
      return;
    }
    const first = loadedYears[0];
    const last = loadedYears[loadedYears.length - 1];
    for (const input of [yearFromInput, yearToInput]) {
      input.min = first;
      input.max = last;
    }
    yearFromInput.value = first;
    yearToInput.value = last;
    randomBtn.disabled = false;
    randomSong();
  }

  presetSelect.addEventListener('change', () => {
    const preset = PRESETS[presetSelect.value];
    if (preset) [topXInput.value, skipYInput.value] = preset;
  });
  videoTypeCheckbox.addEventListener('change', updateVideoModeLabel);
  randomBtn.addEventListener('click', randomSong);

  updateVideoModeLabel();
  randomBtn.disabled = true;
  showMessage('Loading songs…');
  loadSongs();
});
