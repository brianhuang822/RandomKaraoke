document.addEventListener('DOMContentLoaded', function() {
  const songsData = {};
  const yearFromInput = document.getElementById('yearFrom');
  const yearToInput = document.getElementById('yearTo');
  const topXInput = document.getElementById('topX');
  const videoTypeCheckbox = document.getElementById('videoType');
  const randomBtn = document.getElementById('randomBtn');
  const songDisplay = document.getElementById('songDisplay');

  // Load songs data from 2006 to 2023
  for (let year = 2022; year <= 2023; year++) {
    fetch(`${year}.json`)
      .then(response => response.json())
      .then(data => {
        songsData[year] = data;
      })
      .catch(error => console.error('Error loading song data:', error));
  }

  randomBtn.addEventListener('click', function() {
    let yearFrom = parseInt(yearFromInput.value);
    let yearTo = parseInt(yearToInput.value);
    let topX = parseInt(topXInput.value);
    let videoType = videoTypeCheckbox.checked ? 'karaoke' : 'lyricVideo';
    let filteredSongs = [];

    for (let year = yearFrom; year <= yearTo; year++) {
      if (songsData[year]) {
        filteredSongs.push(...songsData[year].slice(0, topX));
      }
    }

    let randomSong = filteredSongs[Math.floor(Math.random() * filteredSongs.length)];
    let videoUrl = randomSong[videoType];
    songDisplay.innerHTML = `
      <h2>${randomSong.songTitle}</h2>
      <iframe width="560" height="315" src="${videoUrl.replace('watch?v=', 'embed/')}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
    `;
  });
});
