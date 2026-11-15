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

  const KIND_NAME = { karaoke: 'karaoke version', lyricVideo: 'lyric video' };
  let currentPick = 0;

  // The IFrame API tells us when a video refuses to play here (region locks, uploads
  // removed since the data was refreshed) so we can switch to the song's other video.
  let youTubeApi = null;
  function loadYouTubeApi() {
    if (!youTubeApi) {
      youTubeApi = new Promise((resolve, reject) => {
        if (window.YT && window.YT.Player) return resolve(window.YT);
        const previous = window.onYouTubeIframeAPIReady;
        window.onYouTubeIframeAPIReady = () => {
          if (previous) previous();
          resolve(window.YT);
        };
        const script = el('script', { src: 'https://www.youtube.com/iframe_api', async: true });
        script.onerror = reject;
        document.head.append(script);
      });
    }
    return youTubeApi;
  }

  function watchLink(id, text) {
    return el('a', {
      className: 'watch-link',
      href: `https://www.youtube.com/watch?v=${id}`,
      target: '_blank',
      rel: 'noopener',
      textContent: text,
    });
  }

  function randomSong() {
    const pool = candidateSongs();
    if (!pool.length) {
      showMessage('No songs match these settings. Try a wider year range or a smaller "Skip Top Y".');
      return;
    }
    const pick = pool[Math.floor(Math.random() * pool.length)];
    const wanted = videoTypeCheckbox.checked ? 'karaoke' : 'lyricVideo';
    const other = wanted === 'karaoke' ? 'lyricVideo' : 'karaoke';
    const videos = [wanted, other]
      .map((kind) => ({ kind, id: videoId(pick.song[kind]) }))
      .filter((v, i, all) => v.id && all.findIndex((w) => w.id === v.id) === i);
    currentPick += 1;
    showVideo(pick, wanted, videos, 0, currentPick);
  }

  // Show videos[index]; on a playback error move on to the next one.
  function showVideo(pick, wanted, videos, index, pickId) {
    const { year, rank, song } = pick;
    const title = song.title || song.songTitle;
    const video = videos[index];
    const children = [
      el('h2', { textContent: title }),
      song.artist ? el('p', { className: 'artist', textContent: song.artist }) : '',
      el('h3', { textContent: `Rank ${rank} in ${year}` }),
    ];

    if (!video) {
      const text = videos.length
        ? "This song's videos won't play on this site right now."
        : 'No video is available for this song yet.';
      children.push(el('p', { className: 'note', textContent: text }));
      if (videos.length) children.push(watchLink(videos[0].id, 'Watch on YouTube instead'));
      songDisplay.replaceChildren(...children.filter(Boolean));
      return;
    }

    if (video.kind !== wanted) {
      const reason = index > 0
        ? `The ${KIND_NAME[wanted]} won't play on this site`
        : `No embeddable ${KIND_NAME[wanted]} was found for this song`;
      children.push(el('p', { className: 'note', textContent: `${reason}, so here is the ${KIND_NAME[video.kind]}.` }));
    }
    const origin = location.origin && location.origin !== 'null' ? `&origin=${encodeURIComponent(location.origin)}` : '';
    const iframe = el('iframe', {
      src: `https://www.youtube.com/embed/${video.id}?enablejsapi=1${origin}`,
      title: `${title} (${KIND_NAME[video.kind]})`,
      allow: 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture',
      allowFullscreen: true,
      referrerPolicy: 'strict-origin-when-cross-origin', // YouTube rejects embeds without a referrer
    });
    children.push(el('div', { className: 'video-wrapper' }, [iframe]), watchLink(video.id, 'Not playing? Watch on YouTube'));
    songDisplay.replaceChildren(...children.filter(Boolean));

    loadYouTubeApi()
      .then((YT) => new YT.Player(iframe, {
        events: {
          onError: () => {
            if (pickId === currentPick) showVideo(pick, wanted, videos, index + 1, pickId);
          },
        },
      }))
      .catch(() => {}); // without the API the plain embed still plays
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
