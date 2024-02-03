document.addEventListener('DOMContentLoaded', function() {
  const songsData = {};
  const yearFromInput = document.getElementById('yearFrom');
  const yearToInput = document.getElementById('yearTo');
  const topXInput = document.getElementById('topX');
  const videoTypeCheckbox = document.getElementById('videoType');
  const randomBtn = document.getElementById('randomBtn');
  const songDisplay = document.getElementById('songDisplay');

  function randomSong() {
    let yearFrom = parseInt(yearFromInput.value);
    let yearTo = parseInt(yearToInput.value);
    let topX = parseInt(topXInput.value);
    let skipY = parseInt(skipYInput.value);
    let videoType = videoTypeCheckbox.checked ? 'karaoke' : 'lyricVideo';
    let filteredSongs = [];

    for (let year = yearFrom; year <= yearTo; year++) {
      if (songsData[year]) {
        const startIdx = skipY < songsData[year].length ? skipY : 0; // Ensure skipY does not exceed array bounds
        const endIdx = startIdx + topX <= songsData[year].length ? startIdx + topX : songsData[year].length;
        filteredSongs.push(songsData[year].slice(startIdx, endIdx));
      }
    }
    let randomYear = Math.floor(Math.random() * filteredSongs.length);
    let randomSongIndex = Math.floor(Math.random() * filteredSongs[randomYear].length);
    let randomSong = filteredSongs[randomYear][randomSongIndex];
    let videoUrl = randomSong[videoType];
    songDisplay.innerHTML = `
      <h2>${randomSong.songTitle}</h2>
      <h3>Rank: ${skipY + randomSongIndex + 1} in year ${2023 - filteredSongs.length + 1 + randomYear}<h3>
      <iframe width="560" height="315" src="${videoUrl.replace('watch?v=', 'embed/')}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
    `;
  }

  // Load songs data from 2009 to 2023
  for (let year = 2009; year <= 2023; year++) {
    fetch(`${year}.json`)
      .then(response => response.json())
      .then(data => {
        songsData[year] = data;
        if (year == 2023) {
          //Random a song
          randomSong();
          }
      })
      .catch(error => console.error('Error loading song data:', error));
  }

  const videoModeSpan = document.getElementById('videoMode');

  // Function to update video mode label
  function updateVideoModeLabel() {
    videoModeSpan.textContent = videoTypeCheckbox.checked ? 'Karaoke Mode' : 'Lyric Video Mode';
  }

  randomBtn.addEventListener('click', randomSong);

  // Initialize with correct mode
  updateVideoModeLabel();

  // Update label on toggle
  videoTypeCheckbox.addEventListener('change', updateVideoModeLabel);

  const skipYInput = document.getElementById('skipY');
  const presetSelect = document.getElementById('preset');

  presetSelect.addEventListener('change', function() {
    switch (this.value) {
      case 'beginner':
        topXInput.value = 5;
        skipYInput.value = 0;
        break;
      case 'easy':
        topXInput.value = 10;
        skipYInput.value = 5;
        break;
      case 'medium':
        topXInput.value = 15;
        skipYInput.value = 15;
        break;
      case 'hard':
        topXInput.value = 20;
        skipYInput.value = 30;
        break;
      case 'extraHard':
        topXInput.value = 25;
        skipYInput.value = 50;
        break;
      case 'songGuru':
        topXInput.value = 30;
        skipYInput.value = 75;
        break;
    }
    updateVideoModeLabel(); // Ensure the video mode label is updated
  });

});