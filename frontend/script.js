let map;
let allMarkers = [];
let lastInputs = { address1: "", address2: "" };
let placeId1 = "";
let placeId2 = "";

// Expose initMap globally for the Google Maps callback
window.initMap = function initMap() {
  map = new google.maps.Map(document.getElementById("map"), {
    center: { lat: 33.0198, lng: -96.6155 }, // Murphy, TX
    zoom: 10,
    mapId: "6ade2f259e719d66c41d923b", // Required for Advanced Markers
  });

  // Attach Places Autocomplete to both inputs using the new PlaceAutocompleteElement
  const input1 = document.getElementById("address1");
  const input2 = document.getElementById("address2");

  // Use the new PlaceAutocompleteElement instead of deprecated Autocomplete
  const ac1 = new google.maps.places.PlaceAutocompleteElement();
  ac1.inputElement = input1;
  
  const ac2 = new google.maps.places.PlaceAutocompleteElement();
  ac2.inputElement = input2;

  ac1.addListener("gmp-placeselect", (event) => {
    const place = event.place;
    placeId1 = place?.id || "";
    if (place?.displayName) input1.value = place.displayName;
  });
  ac2.addListener("gmp-placeselect", (event) => {
    const place = event.place;
    placeId2 = place?.id || "";
    if (place?.displayName) input2.value = place.displayName;
  });
};

const form = document.getElementById("search-form");
form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const address1 = document.getElementById("address1").value.trim();
  const address2 = document.getElementById("address2").value.trim();
  const placeType = document.getElementById("placeType").value;

  lastInputs = { address1, address2 };

  if (!address1 || !address2) {
    alert("Please enter both addresses.");
    return;
    }

  await fetchMidpointData({ address1, address2, placeType, placeId1, placeId2 });
});

async function fetchMidpointData(payload) {
  try {
    const response = await fetch("http://127.0.0.1:5000/api/find_midpoint", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const body = await response.json();
    if (!response.ok) {
      alert(body.error || "Something went wrong. Try again.");
      return;
    }

    displayResults(body);
  } catch (err) {
    console.error(err);
    alert("Could not reach the server. Is the backend running?");
  }
}

function clearMarkers() {
  for (const m of allMarkers) {
    m.setMap(null);
  }
  allMarkers = [];
}

function addMarker(position, title, type = 'place') {
  let marker;
  
  if (type === 'you') {
    // Use AdvancedMarkerElement with custom pin
    const pin = new google.maps.marker.PinElement({
      background: '#2563eb',
      borderColor: '#ffffff',
      glyphColor: '#ffffff',
      glyph: 'Y',
      scale: 1.2
    });
    marker = new google.maps.marker.AdvancedMarkerElement({
      map,
      position,
      title,
      content: pin.element
    });
  } else if (type === 'friend') {
    const pin = new google.maps.marker.PinElement({
      background: '#16a34a',
      borderColor: '#ffffff',
      glyphColor: '#ffffff',
      glyph: 'F',
      scale: 1.2
    });
    marker = new google.maps.marker.AdvancedMarkerElement({
      map,
      position,
      title,
      content: pin.element
    });
  } else if (type === 'midpoint') {
    const pin = new google.maps.marker.PinElement({
      background: '#dc2626',
      borderColor: '#ffffff',
      glyphColor: '#ffffff',
      glyph: 'M',
      scale: 1.0
    });
    marker = new google.maps.marker.AdvancedMarkerElement({
      map,
      position,
      title,
      content: pin.element
    });
  } else {
    // Default pin for places
    const pin = new google.maps.marker.PinElement({
      background: '#ef4444',
      borderColor: '#ffffff',
      glyphColor: '#ffffff'
    });
    marker = new google.maps.marker.AdvancedMarkerElement({
      map,
      position,
      title,
      content: pin.element
    });
  }
  
  allMarkers.push(marker);
  return marker;
}

function displayResults(data) {
  if (!map) return;

  clearMarkers();

  const bounds = new google.maps.LatLngBounds();

  // Origins and midpoint markers with custom icons
  addMarker(data.origin1, "You", "you");
  addMarker(data.origin2, "Friend", "friend");
  addMarker(data.midpoint, "Midpoint", "midpoint");

  bounds.extend(data.origin1);
  bounds.extend(data.origin2);
  bounds.extend(data.midpoint);

  // Place markers (midpoint results) - always show markers regardless of source
  for (const place of data.places) {
    const pos = place.location;
    if (!pos || typeof pos.lat !== "number" || typeof pos.lng !== "number") continue;
    const marker = addMarker(pos, place.name || "Place");
    bounds.extend(pos);

    // Open the detailed place panel instead of info window
    marker.addListener("click", () => openPlacePanel(place));
  }

  map.fitBounds(bounds);
  renderList(data);
}

function renderList(data) {
  const list = document.getElementById("results-list");
  const noResults = document.getElementById("no-results");
  list.innerHTML = "";

  // Show places with simple name-only items
  if (data.places && data.places.length > 0) {
    noResults.classList.add("hidden");
    for (const place of data.places) {
      list.appendChild(createSimpleListItem(place));
    }
  } else {
    noResults.classList.remove("hidden");
  }
}

function createSimpleListItem(place) {
  const li = document.createElement('li');
  li.className = 'result-simple';
  li.innerHTML = `
    <h4>${escapeHtml(place.name || 'Place')}</h4>
    ${place.rating ? `<div class="rating">⭐ ${place.rating} (${place.user_ratings_total || 0})</div>` : ''}
  `;
  
  // Click to open detailed panel
  li.addEventListener('click', () => openPlacePanel(place));
  
  return li;
}

function placeListItem(place) {
  const li = document.createElement('li');
  li.className = 'result-item';
  const t1 = place.travel_time_from_origin1_text ? ` · You: ${place.travel_time_from_origin1_text}` : '';
  const t2 = place.travel_time_from_origin2_text ? ` · Friend: ${place.travel_time_from_origin2_text}` : '';
  li.innerHTML = `
    <h3>${escapeHtml(place.name || 'Place')}</h3>
    <div class="result-meta">
      ${place.rating ? `⭐ ${place.rating} (${place.user_ratings_total || 0}) · ` : ''}
      ${escapeHtml(place.address || '')}
    </div>
    <div class="actions">
      ${place.travel_time_from_origin1_text ? `<span class='badge'><span class='dot'></span>You: ${place.travel_time_from_origin1_text}</span>` : ''}
      ${place.travel_time_from_origin2_text ? `<span class='badge'><span class='dot'></span>Friend: ${place.travel_time_from_origin2_text}</span>` : ''}
    </div>
    <div class="actions" style="margin-top:8px">
      <a class="btn btn-outline" target="_blank" rel="noopener" href="https://www.google.com/maps/dir/?api=1&origin=${encodeURIComponent(lastInputs.address1)}&destination=${encodeURIComponent((place.location?.lat||'') + ',' + (place.location?.lng||''))}">Directions (You → Here)</a>
      <a class="btn btn-primary" target="_blank" rel="noopener" href="https://www.google.com/maps/dir/?api=1&origin=${encodeURIComponent(lastInputs.address2)}&destination=${encodeURIComponent((place.location?.lat||'') + ',' + (place.location?.lng||''))}">Directions (Friend → Here)</a>
    </div>
  `;
  return li;
}

function openPlacePanel(place) {
  const panel = document.getElementById("place-panel");
  const backdrop = document.getElementById("panel-backdrop");
  
  // Populate the panel with place data
  document.getElementById("place-title").textContent = place.name || "Place";
  
  // Rating
  const ratingDiv = document.getElementById("place-rating");
  if (place.rating) {
    ratingDiv.innerHTML = `
      <div class="flex items-center gap-1">
        <span class="text-yellow-500">⭐</span>
        <span class="font-medium">${place.rating}</span>
        <span class="text-slate-500">(${place.user_ratings_total || 0} reviews)</span>
      </div>
    `;
  } else {
    ratingDiv.innerHTML = '<span class="text-slate-500">No rating available</span>';
  }
  
  // Address
  document.getElementById("place-address").textContent = place.address || "Address not available";
  
  // Travel times
  const timeYou = document.getElementById("time-you");
  const timeFriend = document.getElementById("time-friend");
  
  if (place.travel_time_from_origin1_text) {
    timeYou.innerHTML = `
      <div>${place.travel_time_from_origin1_text}</div>
      ${place.travel_distance_from_origin1_text ? `<div class="text-xs">${place.travel_distance_from_origin1_text}</div>` : ''}
    `;
  } else {
    timeYou.innerHTML = '<div>Travel time not available</div>';
  }
  
  if (place.travel_time_from_origin2_text) {
    timeFriend.innerHTML = `
      <div>${place.travel_time_from_origin2_text}</div>
      ${place.travel_distance_from_origin2_text ? `<div class="text-xs">${place.travel_distance_from_origin2_text}</div>` : ''}
    `;
  } else {
    timeFriend.innerHTML = '<div>Travel time not available</div>';
  }
  
  // Direction links
  const directionsYou = document.getElementById("directions-you");
  const directionsFriend = document.getElementById("directions-friend");
  
  directionsYou.href = `https://www.google.com/maps/dir/?api=1&origin=${encodeURIComponent(lastInputs.address1)}&destination=${encodeURIComponent((place.location?.lat||'') + ',' + (place.location?.lng||''))}`;
  directionsFriend.href = `https://www.google.com/maps/dir/?api=1&origin=${encodeURIComponent(lastInputs.address2)}&destination=${encodeURIComponent((place.location?.lat||'') + ',' + (place.location?.lng||''))}`;
  
  // Show the panel with slide animation
  panel.classList.remove("hidden");
  setTimeout(() => {
    panel.classList.remove("-translate-x-full");
  }, 10);
  
  // Close button handler
  document.getElementById("close-place-panel").onclick = closePlacePanel;
}

function closePlacePanel() {
  const panel = document.getElementById("place-panel");
  
  panel.classList.add("-translate-x-full");
  setTimeout(() => {
    panel.classList.add("hidden");
  }, 300);
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}


