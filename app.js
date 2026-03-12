document.addEventListener('DOMContentLoaded', function() {
  const songsData = {};
  const yearFromInput = document.getElementById('yearFrom');
  const yearToInput = document.getElementById('yearTo');
  const topXInput = document.getElementById('topX');
  const skipYInput = document.getElementById('skipY');
  const videoTypeCheckbox = document.getElementById('videoType');
  const randomBtn = document.getElementById('randomBtn');
  const songDisplay = document.getElementById('songDisplay');
  const videoModeSpan = document.getElementById('videoMode');
  const presetPills = document.getElementById('presetPills');

  function randomSong() {
    let yearFrom = parseInt(yearFromInput.value);
    let yearTo = parseInt(yearToInput.value);
    let topX = parseInt(topXInput.value);
    let skipY = parseInt(skipYInput.value);
    let videoType = videoTypeCheckbox.checked ? 'karaoke' : 'lyricVideo';
    let filteredSongs = [];

    for (let year = yearFrom; year <= yearTo; year++) {
      if (songsData[year]) {
        const startIdx = skipY < songsData[year].length ? skipY : 0;
        const endIdx = startIdx + topX <= songsData[year].length ? startIdx + topX : songsData[year].length;
        filteredSongs.push(songsData[year].slice(startIdx, endIdx));
      }
    }
    let randomYear = Math.floor(Math.random() * filteredSongs.length);
    let randomSongIndex = Math.floor(Math.random() * filteredSongs[randomYear].length);
    let song = filteredSongs[randomYear][randomSongIndex];
    let videoUrl = song[videoType];
    songDisplay.innerHTML = `
      <div class="song-card">
        <h2>${song.songTitle}</h2>
        <p class="song-meta">Rank #${skipY + randomSongIndex + 1} &middot; ${yearFrom + randomYear}</p>
        <div class="video-wrapper">
          <iframe src="${videoUrl.replace('watch?v=', 'embed/')}" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
        </div>
      </div>
    `;
  }

  // Load songs data from 2006 to 2023
  for (let year = 2006; year <= 2023; year++) {
    fetch(`${year}.json`)
      .then(response => response.json())
      .then(data => {
        songsData[year] = data;
        if (year == 2023) {
          randomSong();
        }
      })
      .catch(error => console.error('Error loading song data:', error));
  }

  function updateVideoModeLabel() {
    videoModeSpan.textContent = videoTypeCheckbox.checked ? 'Karaoke' : 'Lyric Video';
  }

  randomBtn.addEventListener('click', randomSong);
  updateVideoModeLabel();
  videoTypeCheckbox.addEventListener('change', updateVideoModeLabel);

  // Preset pills
  const presets = {
    beginner:  { topX: 5,  skipY: 0  },
    easy:      { topX: 10, skipY: 5  },
    medium:    { topX: 15, skipY: 15 },
    hard:      { topX: 20, skipY: 30 },
    extraHard: { topX: 25, skipY: 50 },
    songGuru:  { topX: 30, skipY: 75 },
  };

  presetPills.addEventListener('click', function(e) {
    const pill = e.target.closest('.pill');
    if (!pill) return;
    presetPills.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
    pill.classList.add('active');
    const preset = presets[pill.dataset.value];
    if (preset) {
      topXInput.value = preset.topX;
      skipYInput.value = preset.skipY;
    }
  });
});
