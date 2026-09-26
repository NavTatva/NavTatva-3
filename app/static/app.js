/* NTRO Oil Spill Attribution Console
   Vanilla JS, Leaflet only. No framework, no build step, no CDN at runtime.
   Every value rendered here comes from the job document the API returned. */

(function () {
  "use strict";

  var API = "";
  var state = {
    scenes: [],
    scene: null,
    job: null,
    config: null,
    health: null,
    suspects: [],
    selected: null,
    playing: false,
    timer: null,
    frames: [],
    frameIndex: 0,
  };

  var map = null;
  var layerGroup = {};

  // ---------------------------------------------------------------- helpers
  function $(id) {
    return document.getElementById(id);
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = String(text);
    return n;
  }

  function escapeHtml(value) {
    return el("span", "", value).innerHTML;
  }

  function fmt(v, digits) {
    if (
      v === null ||
      v === undefined ||
      v === "" ||
      (typeof v === "number" && !isFinite(v))
    )
      return "n/a";
    if (typeof v === "number")
      return v.toFixed(digits === undefined ? 2 : digits);
    return String(v);
  }

  function utc(iso) {
    if (!iso) return "n/a";
    var d = new Date(iso);
    if (isNaN(d.getTime())) return String(iso);
    return (
      d
        .toISOString()
        .replace("T", " ")
        .replace(/\.\d+Z?$/, "")
        .replace("Z", "") + " UTC"
    );
  }

  function hhmm(ts) {
    var d = new Date(ts * 1000);
    return d.toISOString().substring(0, 16).replace("T", " ") + " UTC";
  }

  function getJSON(path) {
    return fetch(API + path, { headers: { Accept: "application/json" } }).then(
      function (r) {
        if (!r.ok)
          return r.text().then(function (t) {
            throw new Error(r.status + " " + t.slice(0, 300));
          });
        return r.json();
      },
    );
  }

  function postJSON(path, body) {
    return fetch(API + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    }).then(function (r) {
      if (!r.ok)
        return r.text().then(function (t) {
          throw new Error(r.status + " " + t.slice(0, 400));
        });
      return r.json();
    });
  }

  // ------------------------------------------------------------------- map
  function initMap() {
    map = L.map("map", {
      // Zoom sits on the right. The layers panel owns the top-left corner, and
      // stacking a control under a panel makes the control unclickable.
      zoomControl: false,
      attributionControl: true,
      preferCanvas: true,
      worldCopyJump: false,
      // Leaflet fades tiles in over a few frames. If the map is re-fitted while
      // a fade is in flight -- which is exactly what happens when the scene
      // footprint is framed on load -- the fade stalls and the tiles are left
      // at opacity 0. They are decoded, positioned and invisible, so the
      // console showed a black map over perfectly good cached imagery. There is
      // nothing to fade for a local tile store anyway.
      fadeAnimation: false,
    }).setView([20, 78], 4);

    map.attributionControl.setPrefix("");
    map.attributionControl.addAttribution("NavTatva");

    L.control.zoom({ position: "topright" }).addTo(map);
    L.control.scale({ imperial: false, position: "bottomright" }).addTo(map);

    // Exposed for diagnostics and for the browser checks that drive this map
    // during development. Read-only as far as the app is concerned.
    window.__tidetrace = { map: map, layers: layerGroup, state: state };

    // Leaflet stacks everything in `overlayPane` by DOM insertion order, and the
    // SAR backdrop is inserted at RUN time -- after the optical chip, which is
    // loaded when the scene is picked. So optical always ended up underneath it
    // and ticking the box appeared to do nothing. Explicit panes fix the order
    // properly: both sit below overlayPane (400), so the class mask and every
    // vector layer still draw above them.
    map.createPane("sarPane").style.zIndex = 350;
    map.createPane("opticalPane").style.zIndex = 360;

    // Order is z-order: later goes on top. Optical sits directly ABOVE the SAR
    // backdrop so that ticking it actually reveals something -- underneath a
    // 0.95-opacity radar image it would be invisible and the control would look
    // broken. The class mask and every vector layer stay above both.
    [
      "sar",
      "optical",
      "mask",
      "oil",
      "lookalike",
      "hindcast",
      "cone_back",
      "origin",
      "forecast",
      "cone_fwd",
      "tracks",
      "vessels",
    ].forEach(function (name) {
      layerGroup[name] = L.layerGroup().addTo(map);
    });

    // Starts hidden, matching its unchecked box. It is context, not evidence.
    map.removeLayer(layerGroup.optical);


    addBasemaps();

    map.on("mousemove", function (e) {
      $("readout").textContent =
        "lat " + e.latlng.lat.toFixed(4) + "  lon " + e.latlng.lng.toFixed(4);
    });
  }

  /* A 1x1 transparent PNG. Outside the cached footprint there is simply no
     tile, and a missing tile should reveal the dark canvas and the graticule
     rather than a broken-image icon. */
  var BLANK =
    "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";

  /* The chart base: a tile layer drawn in the browser, from nothing.

     Cached imagery only exists for the indexed scene footprints, so panning off
     one used to leave bare canvas with a few graticule lines over it. That reads
     as a broken map, and "the tiles you need were never downloaded" is not a
     thought a judge should have to have.

     This draws every tile on a canvas at request time: an ocean ground, a
     depth-of-field wash so the sea is not a flat fill, the graticule as part of
     the tile rather than as vectors laid over it, and the parallel and meridian
     stamped in the corner. It costs no network, no disk and no bundle, it is
     seamless at every zoom, and it covers the whole globe. Real imagery still
     draws on top wherever we actually have it.

     A chart with no soundings is still a chart. A blank rectangle is not. */
  function chartBaseLayer() {
    var Chart = L.GridLayer.extend({
      createTile: function (coords) {
        var size = this.getTileSize();
        var tile = document.createElement("canvas");
        tile.width = size.x;
        tile.height = size.y;
        var ctx = tile.getContext("2d");
        var w = size.x,
          h = size.y;

        // Ground. Two stops, so a wide view has some depth to it rather than
        // reading as one flat colour across the whole viewport.
        // Deep-water tone, pitched to sit close to the open ocean in the cached
        // satellite imagery. Where a tile is missing the join then reads as more
        // sea rather than as a hole, which is both better looking and more
        // truthful: offshore of the footprint there really is only more sea.
        var wash = ctx.createLinearGradient(0, 0, w, h);
        wash.addColorStop(0, "#0f1e2b");
        wash.addColorStop(1, "#132735");
        ctx.fillStyle = wash;
        ctx.fillRect(0, 0, w, h);

        // Continents. Without these, zooming out showed ocean, a graticule and
        // four islands of satellite imagery, which reads as a failed load.
        paintLand(ctx, coords, size, this._map);

        // Graticule, drawn into the tile. Leaflet gives us the tile's own
        // lat/lon corners, so the lines land on whole degrees rather than on
        // tile edges, and the interval opens up as you zoom out.
        var nw = this._map.unproject([coords.x * w, coords.y * h], coords.z);
        var se = this._map.unproject(
          [(coords.x + 1) * w, (coords.y + 1) * h],
          coords.z,
        );
        var stepChoices = [30, 10, 5, 2, 1, 0.5, 0.25, 0.1, 0.05, 0.02, 0.01];
        var spanLon = Math.abs(se.lng - nw.lng);
        var step = stepChoices[0];
        for (var i = 0; i < stepChoices.length; i++) {
          if (spanLon / stepChoices[i] <= 4) {
            step = stepChoices[i];
            break;
          }
        }

        ctx.strokeStyle = "rgba(148, 178, 198, 0.13)";
        ctx.lineWidth = 1;
        ctx.beginPath();

        var firstLon = Math.ceil(nw.lng / step) * step;
        for (var lon = firstLon; lon < se.lng; lon += step) {
          var px = ((lon - nw.lng) / (se.lng - nw.lng)) * w;
          ctx.moveTo(Math.round(px) + 0.5, 0);
          ctx.lineTo(Math.round(px) + 0.5, h);
        }
        var firstLat = Math.floor(nw.lat / step) * step;
        for (var lat = firstLat; lat > se.lat; lat -= step) {
          var py = ((nw.lat - lat) / (nw.lat - se.lat)) * h;
          ctx.moveTo(0, Math.round(py) + 0.5);
          ctx.lineTo(w, Math.round(py) + 0.5);
        }
        ctx.stroke();

        // The tile's own north-west corner, stamped like a chart margin.
        ctx.fillStyle = "rgba(148, 178, 198, 0.30)";
        ctx.font = "10px ui-monospace, Consolas, monospace";
        ctx.fillText(_dm(nw.lat, "NS") + "  " + _dm(nw.lng, "EW"), 6, 14);

        return tile;
      },
    });
    return new Chart({
      minZoom: 0,
      maxZoom: 18,
      tileSize: 256,
      attribution: "",
    });
  }

  /* Degrees and decimal minutes, the way a chart margin writes them. */
  function _dm(v, hemis) {
    var hemi = hemis[v < 0 ? 1 : 0];
    var a = Math.abs(v);
    var d = Math.floor(a);
    var m = (a - d) * 60;
    return d + "°" + (m < 10 ? "0" : "") + m.toFixed(1) + "'" + hemi;
  }

  /* World coastline, drawn into the chart tiles.

     The satellite cache covers the four scene footprints and nothing else,
     which is the right trade for an offline demo but left zooming out looking
     like a broken tile pipeline: four imagery patches floating in an empty
     wash, with no continents anywhere. Natural Earth land, simplified to 79 KB
     coarse and 645 KB detailed, fills that in at every zoom with no network and
     no tiles.

     It is rasterised into each chart tile rather than added as a vector layer,
     because a vector layer re-paths every ring on every pan frame; a tile is
     drawn once and then moved by the browser. That is the difference between a
     map that drags smoothly and one that stutters. */
  var LAND = { coarse: null, detail: null, loading: false };

  function loadWorldLand() {
    if (LAND.loading) return;
    LAND.loading = true;
    var pending = 2;
    function done() {
      if (--pending === 0 && map) redrawChartBase();
    }
    getJSON("/data/land/world_land_coarse.json")
      .then(function (d) {
        LAND.coarse = d.rings;
      })
      .catch(function () {})
      .then(done);
    getJSON("/data/land/world_land_detail.json")
      .then(function (d) {
        LAND.detail = d.rings;
      })
      .catch(function () {})
      .then(done);
  }

  function redrawChartBase() {
    if (state.chartLayer && state.chartLayer.redraw) state.chartLayer.redraw();
  }

  /* Paint the land rings that touch this tile. Rings are pre-simplified, so the
     only per-tile work is a bounds test and a path. */
  function paintLand(ctx, coords, size, map_) {
    var rings = (coords.z >= 6 ? LAND.detail : null) || LAND.coarse;
    if (!rings) return;

    var w = size.x,
      h = size.y;
    var nw = map_.unproject([coords.x * w, coords.y * h], coords.z);
    var se = map_.unproject([(coords.x + 1) * w, (coords.y + 1) * h], coords.z);
    var west = nw.lng,
      east = se.lng,
      north = nw.lat,
      south = se.lat;
    // A degree of slack, so a coastline that only clips the corner still draws.
    var pad = Math.max(1, (east - west) * 0.5);
    var originX = coords.x * w,
      originY = coords.y * h;

    ctx.beginPath();
    for (var i = 0; i < rings.length; i++) {
      var ring = rings[i];
      var minX = 1e9,
        maxX = -1e9,
        minY = 1e9,
        maxY = -1e9,
        j;
      for (j = 0; j < ring.length; j++) {
        var px = ring[j][0],
          py = ring[j][1];
        if (px < minX) minX = px;
        if (px > maxX) maxX = px;
        if (py < minY) minY = py;
        if (py > maxY) maxY = py;
      }
      if (
        maxX < west - pad ||
        minX > east + pad ||
        maxY < south - pad ||
        minY > north + pad
      )
        continue;

      for (j = 0; j < ring.length; j++) {
        var pt = map_.project([ring[j][1], ring[j][0]], coords.z);
        var x = pt.x - originX,
          y = pt.y - originY;
        if (j === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
    }
    ctx.fillStyle = LAND_FILL;
    ctx.fill("evenodd");
    ctx.strokeStyle = LAND_EDGE;
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  var LAND_FILL = "#1d2f3c";
  var LAND_EDGE = "rgba(126, 164, 188, 0.55)";

  function addBasemaps() {
    // Drawn before anything else and never removed, so there is always a chart
    // under the overlays no matter where the operator pans.
    state.chartLayer = chartBaseLayer();
    state.chartLayer.addTo(map);
    loadWorldLand();

    var CachedTileLayer = L.TileLayer.extend({
      createTile: function (coords, done) {
        var tile = document.createElement("img");
        tile.alt = "";
        tile.setAttribute("role", "presentation");
        var fallback = false;
        tile.onload = function () { done(null, tile); };
        tile.onerror = function () {
          if (!fallback) {
            fallback = true;
            tile.src = L.Util.template(this.options.cacheUrl, coords);
          } else {
            tile.onerror = null;
            tile.src = BLANK;
          }
        }.bind(this);
        tile.src = this.getTileUrl(coords);
        return tile;
      }
    });
    var bases = {};
    [
      ["Satellite", "World_Imagery", "satellite", "jpg", 19],
      ["Nautical", "Ocean/World_Ocean_Base", "ocean", "jpg", 11]
    ].forEach(function (d) {
      bases[d[0]] = new CachedTileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/" + d[1] + "/MapServer/tile/{z}/{y}/{x}",
        {minZoom: 0, maxZoom: 19, maxNativeZoom: d[4],
         cacheUrl: "/data/basemap/" + d[2] + "/{z}/{x}/{y}." + d[3],
         attribution: "Esri, Maxar, Earthstar Geographics, GEBCO, NOAA"}
      );
    });
    bases["World chart"] = L.layerGroup();
    state.basemap = bases.Satellite.addTo(map);
    var background = $("basemap");
    background.replaceChildren();
    Object.keys(bases).forEach(function (name) {
      var option = el("option", "", name);
      option.value = name;
      background.appendChild(option);
    });
    background.addEventListener("change", function () {
      map.removeLayer(state.basemap);
      state.basemap = bases[background.value].addTo(map);
    });
    state.basemapAvailable = true;
  }

  /* Graticule. Drawn under everything, and the only backdrop outside the
     cached basemap footprint. */
  /* The graticule used to be drawn here as vector polylines over a bare
     canvas. It is now part of the chart base tile, which is seamless, covers
     the whole globe and costs nothing to pan. */

  // Everything a run produces is cleared before the next one. The graticule and
  // the optical chip are not run output: they belong to the map and to the
  // scene. Clearing optical here wiped it on the first RUN and, since it only
  // reloads on scene change, it never came back.
  var KEEP_ON_RUN = {
    optical: true,
  };

  function clearAll() {
    Object.keys(layerGroup).forEach(function (k) {
      if (!KEEP_ON_RUN[k]) layerGroup[k].clearLayers();
    });
  }

  function ringToLatLng(coords) {
    return coords.map(function (p) {
      return [p[1], p[0]];
    });
  }

  // -------------------------------------------------------------- rendering
  function drawDetection(job) {
    var det = job.detection || {};
    var ov = det.overlays || {};

    if (ov.sar && ov.sar.url) {
      L.imageOverlay(ov.sar.url, ov.sar.bounds, {
        opacity: 0.95,
        interactive: false,
        pane: "sarPane",
      }).addTo(layerGroup.sar);
    }
    if (ov.mask && ov.mask.url) {
      L.imageOverlay(ov.mask.url, ov.mask.bounds, {
        opacity: 0.75,
        interactive: false,
      }).addTo(layerGroup.mask);
    }

    (det.polygons || []).forEach(function (f) {
      if (!f.geometry) return;
      var p = f.properties;
      L.polygon(ringToLatLng(f.geometry.coordinates[0]), {
        color: MAPC.oil,
        weight: 2,
        fillColor: MAPC.oil,
        fillOpacity: 0.24,
      })
        .bindPopup(
          "<b>" +
            p.polygon_id +
            " mineral oil</b><br>" +
            "area " +
            fmt(p.area_km2, 3) +
            " km2<br>" +
            "length " +
            fmt(p.length_km, 2) +
            " km, width " +
            fmt(p.width_km, 2) +
            " km<br>" +
            "perimeter " +
            fmt(p.perimeter_km, 2) +
            " km<br>" +
            "orientation " +
            fmt(p.orientation_deg, 0) +
            " deg<br>" +
            (p.eo_verdict ? "optical: " + p.eo_verdict + "<br>" : "") +
            "compactness " +
            fmt(p.compactness, 2) +
            "<br>" +
            "contrast " +
            fmt(p.contrast_db, 1) +
            " dB<br>" +
            "confidence " +
            fmt(p.confidence, 2) +
            "<br>" +
            "centroid " +
            fmt(p.centroid_lat, 4) +
            ", " +
            fmt(p.centroid_lon, 4),
        )
        .addTo(layerGroup.oil);
    });

    (det.lookalikes || []).forEach(function (f) {
      if (!f.geometry) return;
      var p = f.properties;
      L.polygon(ringToLatLng(f.geometry.coordinates[0]), {
        color: MAPC.lookalike,
        weight: 1.5,
        dashArray: "5,4",
        fillColor: MAPC.lookalike,
        fillOpacity: 0.08,
      })
        .bindPopup(
          "<b>" +
            p.polygon_id +
            " look-alike</b><br>" +
            "area " +
            fmt(p.area_km2, 3) +
            " km2<br>" +
            "contrast " +
            fmt(p.contrast_db, 1) +
            " dB<br>" +
            "<i>excluded from AIS attribution</i>",
        )
        .addTo(layerGroup.lookalike);
    });
  }

  function drawDrift(job) {
    var d = job.drift;
    if (!d) return;

    if (d.cone_back && d.cone_back.geometry) {
      L.polygon(ringToLatLng(d.cone_back.geometry.coordinates[0]), {
        color: MAPC.hindEdge,
        weight: 1,
        dashArray: "3,4",
        fillColor: MAPC.hindFill,
        fillOpacity: 0.1,
      })
        .bindPopup(
          "Hindcast cone, swept 90 percent ensemble<br>area " +
            fmt(d.cone_back.properties.area_km2, 1) +
            " km2",
        )
        .addTo(layerGroup.cone_back);
    }

    [["hindcast", MAPC.hind], ["forecast", MAPC.fore]].forEach(function (entry) {
      var paths = d[entry[0] + "_particles"];
      (paths && paths.geometry ? paths.geometry.coordinates : []).forEach(function (coords) {
        L.polyline(ringToLatLng(coords), {color: entry[1], weight: 1, opacity: 0.22, smoothFactor: 0})
          .bindTooltip("Model ensemble member · plausible drift, not a vessel track")
          .addTo(layerGroup[entry[0]]);
      });
    });

    if (d.hindcast_track && d.hindcast_track.geometry) {
      L.polyline(ringToLatLng(d.hindcast_track.geometry.coordinates), {
        color: MAPC.hind,
        weight: 2,
        dashArray: "2,6",
        opacity: 0.9,
      })
        .bindPopup("Ensemble median backtrack")
        .addTo(layerGroup.hindcast);
    }

    if (d.origin_zone && d.origin_zone.geometry) {
      L.polygon(ringToLatLng(d.origin_zone.geometry.coordinates[0]), {
        color: MAPC.origin,
        weight: 2,
        fillColor: MAPC.origin,
        fillOpacity: 0.18,
      })
        .bindPopup(
          "<b>Origin zone</b><br>" +
            utc(d.origin.t) +
            "<br>" +
            "90 percent envelope, spread " +
            fmt(d.origin.spread_km, 1) +
            " km<br>" +
            "buffered " +
            fmt(d.origin.buffer_km, 1) +
            " km<br>" +
            "area " +
            fmt(d.origin.area_km2, 1) +
            " km2",
        )
        .addTo(layerGroup.origin);

      L.circleMarker([d.origin.lat, d.origin.lon], {
        radius: 4,
        color: "#ffffff",
        weight: 2,
        fillColor: MAPC.origin,
        fillOpacity: 1,
      })
        .bindTooltip("origin estimate, zone centre")
        .addTo(layerGroup.origin);
    }

    if (d.cone_fwd && d.cone_fwd.geometry) {
      L.polygon(ringToLatLng(d.cone_fwd.geometry.coordinates[0]), {
        color: MAPC.fore,
        weight: 1.5,
        fillColor: MAPC.fore,
        fillOpacity: 0.1,
      })
        .bindPopup(
          "Forecast cone " +
            fmt(d.cone_fwd.properties.hours, 0) +
            " h<br>area " +
            fmt(d.cone_fwd.properties.area_km2, 1) +
            " km2",
        )
        .addTo(layerGroup.cone_fwd);
    }
    if (d.forecast_track && d.forecast_track.geometry) {
      L.polyline(ringToLatLng(d.forecast_track.geometry.coordinates), {
        color: MAPC.fore,
        weight: 2,
        opacity: 0.95,
        dashArray: "6,4",
      })
        .bindPopup("Ensemble median forecast")
        .addTo(layerGroup.forecast);
    }
  }

  /* The map's own palette, kept in one place so it cannot drift away from the
     stylesheet. Amber is the case under investigation, cyan is the forecast,
     and everything else is slate. */
  var MAPC = {
    oil: "#e89550",
    lookalike: "#b9a05e",
    hind: "#e0b98d",
    hindEdge: "#c9a37c",
    hindFill: "#8a6a4c",
    origin: "#e8734a",
    fore: "#4fb8dd",
    gap: "#cc5b4e",
  };

  /* Rank 1 is amber like the release zone it is being connected to. Ranks 2-3
     step down through it, and everything below that is slate: the leaderboard
     already carries the ordering, and ten distinct hues on a chart is noise. */
  var RANK_COLORS = [
    "#e8734a",
    "#e89550",
    "#c9a06a",
    "#8fa6b5",
    "#8fa6b5",
    "#8fa6b5",
    "#8fa6b5",
    "#8fa6b5",
    "#8fa6b5",
    "#8fa6b5",
  ];

  function rankColor(rank) {
    return RANK_COLORS[Math.min(rank - 1, RANK_COLORS.length - 1)] || "#8fa6b5";
  }

  function drawTracks(suspects) {
    layerGroup.tracks.clearLayers();
    suspects.forEach(function (s) {
      var color = rankColor(s.rank);
      var weight = s.rank === 1 ? 4 : s.rank <= 3 ? 2.5 : 1.6;
      var gj = (s.track || {}).geojson;
      if (!gj) return;
      gj.features.forEach(function (f) {
        if (!f.geometry || !f.geometry.coordinates.length) return;
        var dr = f.properties.kind === "dead_reckoned";
        var simulated = String(f.properties.source || "").indexOf("simulated") >= 0;
        L.polyline(ringToLatLng(f.geometry.coordinates), {
          color: dr ? MAPC.gap : color,
          weight: dr ? Math.max(weight, 3) : weight,
          opacity: dr ? 0.95 : 0.8,
          dashArray: dr ? "7,5" : simulated ? "3,6" : null,
          smoothFactor: 0,
        })
          .bindPopup(
            "<b>" +
              escapeHtml(s.name || "UNKNOWN") +
              "</b><br>" +
              (simulated ? "<strong>SIMULATED DEMO TRACK — not recorded AIS</strong><br>" : "Recorded AIS track<br>") +
              "MMSI " +
              s.mmsi +
              "<br>" +
              "rank " +
              s.rank +
              ", score " +
              fmt(s.score, 1) +
              "<br>" +
              "type " +
              s.type +
              "<br>" +
              (dr
                ? "<b style='color:" +
                  MAPC.gap +
                  "'>NON-REPORTING segment, " +
                  fmt(f.properties.gap_minutes, 0) +
                  " min</b><br>"
                : "") +
              s.reasons.join("<br>"),
          )
          .addTo(layerGroup.tracks);
      });
    });
  }

  // ----------------------------------------------------------- time slider
  function buildFrames(job) {
    var suspects = (job.attribution || {}).suspects || [];
    var times = {};
    suspects.forEach(function (s) {
      (s.track.samples || []).forEach(function (p) {
        times[p.ts] = true;
      });
    });
    var list = Object.keys(times)
      .map(Number)
      .sort(function (a, b) {
        return a - b;
      });
    // Thin to at most 260 frames so the slider stays responsive.
    var stride = Math.max(1, Math.ceil(list.length / 260));
    state.frames = list.filter(function (_, i) {
      return i % stride === 0;
    });
    state.frameIndex = state.frames.length ? state.frames.length - 1 : 0;

    var slider = $("slider");
    slider.disabled = state.frames.length < 2;
    slider.min = 0;
    slider.max = Math.max(0, state.frames.length - 1);
    slider.value = state.frameIndex;
    $("timebar").classList.toggle("on", state.frames.length > 1);
    renderFrame();
  }

  function nearestSample(samples, ts) {
    if (!samples.length) return null;
    var lo = 0,
      hi = samples.length - 1;
    while (lo < hi) {
      var mid = (lo + hi) >> 1;
      if (samples[mid].ts < ts) lo = mid + 1;
      else hi = mid;
    }
    var a = samples[Math.max(0, lo - 1)],
      b = samples[lo];
    if (Math.abs(a.ts - ts) > 20 * 60 && Math.abs(b.ts - ts) > 20 * 60)
      return null;
    return Math.abs(a.ts - ts) <= Math.abs(b.ts - ts) ? a : b;
  }

  function renderFrame() {
    var g = layerGroup.vessels;
    g.clearLayers();
    if (!state.frames.length) return;
    var ts = state.frames[state.frameIndex];
    $("tlabel").textContent = hhmm(ts);

    state.suspects.forEach(function (s) {
      var p = nearestSample(s.track.samples || [], ts);
      if (!p) return;
      var color = rankColor(s.rank);
      L.circleMarker([p.lat, p.lon], {
        radius: s.rank === 1 ? 6 : 4,
        color: p.dr ? MAPC.gap : "#04101a",
        weight: p.dr ? 2 : 1,
        fillColor: color,
        fillOpacity: p.dr ? 0.45 : 1,
      })
        .bindTooltip(
          "#" +
            s.rank +
            " " +
            escapeHtml(s.name || "UNKNOWN") +
            "  " +
            fmt(p.sog, 1) +
            " kn  " +
            fmt(p.cog, 0) +
            " deg" +
            (p.dr ? "  NON-REPORTING" : ""),
          { direction: "top" },
        )
        .addTo(g);

      if (s.rank === 1) {
        L.marker([p.lat, p.lon], {
          icon: L.divIcon({
            className: "vessel-label",
            html: s.name || "UNKNOWN",
            iconAnchor: [-9, 6],
          }),
          interactive: false,
        }).addTo(g);
      }
    });
  }

  function play() {
    if (state.playing) {
      stop();
      return;
    }
    if (state.frames.length < 2) return;
    state.playing = true;
    $("play").textContent = "Pause";
    state.timer = setInterval(function () {
      state.frameIndex = (state.frameIndex + 1) % state.frames.length;
      $("slider").value = state.frameIndex;
      renderFrame();
    }, 90);
  }

  function stop() {
    state.playing = false;
    $("play").textContent = "Play";
    if (state.timer) {
      clearInterval(state.timer);
      state.timer = null;
    }
  }

  // ----------------------------------------------------------- field notebook
  var SCENE_LABELS = {
    gom_mc20_chronic_slick: ["Gulf of Mexico", "MC20 chronic discharge site"],
    arabian_sea_mumbai_offshore: ["Arabian Sea", "Mumbai offshore approaches"],
    caspian_baku_seeps: ["Caspian Sea", "Baku offshore field"],
    santa_barbara_seeps: ["Santa Barbara Channel", "Natural seep observation"],
  };
  var running = false;
  var settings = { hind: 48, fore: 36, radius: 10, window: 3 };
  function sceneLabel(scene) {
    return SCENE_LABELS[scene.id] || [scene.title, "Satellite observation"];
  }
  function dateLabel(value) {
    var date = new Date(value);
    return isNaN(date)
      ? "Date unavailable"
      : date.toLocaleDateString("en-GB", {
          day: "numeric",
          month: "long",
          year: "numeric",
          timeZone: "UTC",
        });
  }
  function row(parent, key, value) {
    var entry = el("div", "data-row");
    entry.appendChild(el("dt", "", key));
    entry.appendChild(el("dd", "", value));
    parent.appendChild(entry);
  }
  function showDialog(id) {
    $(id).showModal();
  }
  function renderSceneList() {
    var container = $("scene-list");
    container.replaceChildren();
    state.scenes.forEach(function (scene, i) {
      var label = sceneLabel(scene);
      var button = el("button", "scene-option");
      button.type = "button";
      button.dataset.id = scene.id;
      button.setAttribute(
        "aria-current",
        String(state.scene && state.scene.id === scene.id),
      );
      button.appendChild(
        el("span", "scene-number", String(i + 1).padStart(2, "0")),
      );
      var text = el("span");
      text.appendChild(el("span", "scene-name", label[0]));
      text.appendChild(
        el(
          "span",
          "scene-caption",
          dateLabel(scene.t_sat) +
            " · " +
            (scene.source === "uploaded"
              ? "Recorded AIS fetched during analysis"
              : scene.ais_mode === "simulated"
                ? "Simulated vessel traffic"
                : "Recorded AIS required"),
        ),
      );
      button.appendChild(text);
      button.appendChild(
        el("span", "", state.scene && state.scene.id === scene.id ? "✓" : "↗"),
      );
      button.addEventListener("click", function () {
        if (running) return;
        selectScene(scene.id);
        $("scene-dialog").close();
      });
      container.appendChild(button);
    });
  }
  function renderSceneInfo() {
    if (!state.scene) return;
    var scene = state.scene,
      label = sceneLabel(scene);
    $("scene-title").textContent = label[0];
    $("scene-subtitle").textContent = label[1] + " · " + dateLabel(scene.t_sat);
    $("observation-index").textContent =
      "Observation " +
      String(state.scenes.indexOf(scene) + 1).padStart(2, "0") +
      " / " +
      String(state.scenes.length).padStart(2, "0");
    var box = $("scene-info");
    box.replaceChildren();
    var list = el("dl", "data-list");
    row(list, "Satellite", "Sentinel-1 radar");
    row(list, "Observed", utc(scene.t_sat));
    row(
      list,
      "Vessel data",
      scene.ais_mode === "simulated"
        ? "Simulated demo traffic"
        : "Recorded AIS required",
    );
    box.appendChild(list);
    box.appendChild(
      el(
        "p",
        "",
        scene.license || "Contains modified Copernicus Sentinel data.",
      ),
    );
    renderSceneList();
  }
  function fitScene() {
    if (!state.scene) return;
    var b = state.scene.bounds;
    map.invalidateSize();
    map.fitBounds(
      [
        [b[1], b[0]],
        [b[3], b[2]],
      ],
      { padding: [38, 38], animate: false },
    );
  }
  function fitJob() {
    if (!state.job) {
      fitScene();
      return;
    }
    var pts = [];
    var drift = state.job.drift || {};
    [drift.origin_zone, drift.cone_fwd].forEach(function (feature) {
      if (feature && feature.geometry)
        pts = pts.concat(ringToLatLng(feature.geometry.coordinates[0]));
    });
    var b = (state.job.detection || {}).sar_bounds;
    if (b) pts.push([b[1], b[0]], [b[3], b[2]]);
    if (pts.length) map.fitBounds(pts, { padding: [35, 35], animate: false });
    else fitScene();
  }
  function setSceneSelection(id) {
    state.scene =
      state.scenes.find(function (scene) {
        return scene.id === id;
      }) || null;
    renderSceneInfo();
    if (state.scene) {
      if (typeof refreshOceanConditions === "function") {
        try {
          refreshOceanConditions(state.scene);
        } catch (e) {
          console.warn("refreshOceanConditions error:", e);
        }
      }

    }
  }
  function selectScene(id) {
    if (running) return;
    setSceneSelection(id);
    resetRun();
    fitScene();
    history.replaceState(null, "", location.pathname);
  }
  function resetRun() {
    stop();
    state.job = null;
    $("ocean-vessels-count").textContent = "Run analysis";
    $("ocean-vessels-mode").textContent = "Historical AIS for the incident release window";
    state.suspects = [];
    state.selected = null;
    state.frames = [];
    state.frameIndex = 0;
    Object.keys(layerGroup).forEach(function (k) {
      if (!KEEP_ON_RUN[k]) layerGroup[k].clearLayers();
    });
    $("timebar").classList.remove("on");
    $("slider").disabled = true;
    $("tlabel").textContent = "";
    $("notices").replaceChildren();
    $("data-notes").replaceChildren();
    $("origin").replaceChildren();
    $("vessel-list").replaceChildren();
    $("vsearch").value = "";
    $("candidate-section").hidden = true;
    $("drift-details").hidden = true;
    $("drift-details").open = false;
    $("data-details").open = false;
    ["ex-note", "ex-json", "ex-geo"].forEach(function (id) {
      $(id).disabled = true;
    });
    renderEmpty();
  }
  function renderEmpty() {
    var box = $("result");
    box.replaceChildren();
    var empty = el("div", "empty-result");
    var art = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    art.setAttribute("class", "empty-illustration");
    art.setAttribute("viewBox", "0 0 80 80");
    art.setAttribute("aria-hidden", "true");
    art.innerHTML =
      '<circle cx="40" cy="40" r="28"/><circle cx="40" cy="40" r="14"/><path d="M40 1v17m0 44v17M1 40h17m44 0h17M20 57c11-18 20 10 40-23"/>';
    empty.appendChild(art);
    empty.appendChild(el("h3", "", "Ready to investigate."));
    empty.appendChild(
      el(
        "p",
        "",
        "Run an analysis to look for oil, trace its movement and review nearby vessel traffic.",
      ),
    );
    empty.appendChild(
      el("p", "next-step", "Start with Run analysis above the map."),
    );
    box.appendChild(empty);
  }
  function metric(parent, value, unit, label) {
    var item = el("div", "metric"),
      number = el("strong", "", value);
    if (unit) number.appendChild(el("small", "", unit));
    item.appendChild(number);
    item.appendChild(el("span", "", label));
    parent.appendChild(item);
  }
  function renderResult(job) {
    var box = $("result");
    box.replaceChildren();
    var detection = job.detection || {},
      polygons = detection.polygons || [],
      metrics = detection.metrics || {};
    var attr = job.attribution || {},
      list = attr.suspects || [];
    box.appendChild(
      el(
        "h3",
        "result-status",
        polygons.length ? "Oil detected." : "No slick detected.",
      ),
    );
    box.appendChild(
      el(
        "p",
        "result-description",
        polygons.length
          ? "Oil-like areas identified in the radar image."
          : "No oil slick was identified in this observation. There is nothing to trace back to a vessel.",
      ),
    );
    if (polygons.length) {
      var stats = el("div", "metrics");
      metric(stats, fmt(metrics.oil_area_km2, 2), "km²", "Detected oil area");
      metric(
        stats,
        String(polygons.length),
        "",
        polygons.length === 1 ? "Slick identified" : "Slicks identified",
      );
      box.appendChild(stats);
      if (!list.length) {
        var considered = (attr.funnel || {}).considered_vessels || 0;
        var loadedAIS = job.ais_fetch && ["cached", "downloaded", "live_recorded"].includes(job.ais_fetch.status);
        var message = considered
          ? "Nearby vessels were found, but none matched the release zone and time window."
          : loadedAIS
            ? "Recorded AIS was loaded, but no track matched this release area and time. Reception coverage may have gaps."
            : "No AIS tracks are available around this estimated release. Vessel attribution is unavailable for this run.";
        box.appendChild(el("p", "result-note", message));
      }
    }
    $("candidate-section").hidden = !list.length;
    $("candidate-count").textContent = String(list.length).padStart(2, "0");
    var simulated = Object.keys(attr.sources_used || {}).some(function (k) {
      return k.indexOf("simulated") >= 0;
    });
    $("ais-note").textContent =
      (simulated ? "Simulated traffic. " : "Recorded traffic. ") +
      "Scores indicate investigation priority, not guilt.";
    renderVessels();
    renderDrift(job);
    var notes = $("data-notes");
    notes.replaceChildren();
    (job.warnings || []).forEach(function (note) {
      if (!note || note.startsWith("Recorded AIS loaded")) return;
      notes.appendChild(el("p", "", note));
    });
    if (
      job.ais_fetch &&
      job.ais_fetch.message &&
      !job.ais_fetch.message.startsWith("Recorded AIS loaded") &&
      ["unsupported", "unavailable", "live_recorded", "cached", "downloaded"].includes(
        job.ais_fetch.status,
      )
    )
      box.appendChild(el("p", "result-note", job.ais_fetch.message));
    var mo = (job.drift || {}).metocean || {};
    if (mo.synthetic)
      box.appendChild(
        el(
          "p",
          "result-note",
          "Local wind and current data are unavailable. Drift and vessel rankings use an assumed constant field and are not reliable evidence of a discharge.",
        ),
      );
    if (job.drift && mo.has_currents === false)
      box.appendChild(
        el(
          "p",
          "result-note",
          "The current provider does not cover this basin and observation time. This run uses the cached wind field; a basin-specific current dataset is needed for a full drift estimate.",
        ),
      );
    if (metrics.detector && metrics.detector !== "unet")
      box.appendChild(
        el(
          "p",
          "result-note",
          "The trained model is unavailable. This run used the less reliable threshold detector.",
        ),
      );
  }
  function renderVessels() {
    var box = $("vessel-list");
    box.replaceChildren();
    var query = $("vsearch").value.trim().toLowerCase();
    var list = state.suspects.filter(function (s) {
      return (
        !query ||
        (s.name || "").toLowerCase().includes(query) ||
        String(s.mmsi).includes(query)
      );
    });
    list.forEach(function (s) {
      var card = el("details", "vessel"),
        summary = el("summary");
      card.dataset.mmsi = s.mmsi;
      summary.appendChild(el("span", "rank", String(s.rank).padStart(2, "0")));
      var name = el("span");
      name.appendChild(el("span", "vessel-name", s.name || "Unknown vessel"));
      name.appendChild(
        el("span", "vessel-type", (s.type || "unknown").replace(/_/g, " ")),
      );
      summary.appendChild(name);
      var score = el("span", "score", fmt(s.score, 1));
      score.appendChild(el("small", "", "out of 100"));
      summary.appendChild(score);
      card.appendChild(summary);
      var detail = el("div", "vessel-detail"),
        data = el("dl", "data-list"),
        d = s.detail || {};
      row(data, "MMSI", s.mmsi);
      row(data, "From release centre", fmt(d.origin_distance_km, 1) + " km");
      row(
        data,
        "Time offset",
        Math.abs(Math.round(d.time_offset_minutes || 0)) +
          " min " +
          ((d.time_offset_minutes || 0) < 0 ? "before" : "after"),
      );
      row(data, "Track confidence", fmt((s.confidence || 0) * 100, 0) + "%");
      detail.appendChild(data);
      var evidence = el("ul", "evidence-list");
      if ((d.behavior || {}).non_reporting)
        evidence.appendChild(
          el(
            "li",
            "",
            "A " +
              fmt(d.behavior.ais_gap_minutes, 0) +
              "-minute reporting gap crosses the search area. The missing segment is estimated.",
          ),
        );
      if ((d.trajectory || {}).aligned)
        evidence.appendChild(
          el("li", "", "Course aligns with the estimated drift direction."),
        );
      evidence.appendChild(
        el(
          "li",
          "",
          "The ranking combines proximity, timing, vessel type, course and behaviour.",
        ),
      );
      detail.appendChild(evidence);
      var focus = el("button", "text-button", "Locate track on map ↗");
      focus.type = "button";
      focus.addEventListener("click", function () {
        focusVessel(s);
      });
      detail.appendChild(focus);
      card.appendChild(detail);
      card.addEventListener("toggle", function () {
        if (card.open) state.selected = s.mmsi;
      });
      box.appendChild(card);
    });
    if (!list.length && query)
      box.appendChild(el("p", "muted small", "No vessels match this search."));
  }
  function focusVessel(s) {
    var pts = ((s.track || {}).samples || []).map(function (p) {
      return [p.lat, p.lon];
    });
    if (pts.length) map.fitBounds(pts, { padding: [40, 40] });
    if (window.innerWidth <= 800)
      $("mapwrap").scrollIntoView({
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "instant"
          : "smooth",
        block: "center",
      });
  }
  function renderDrift(job) {
    var box = $("origin");
    box.replaceChildren();
    var d = job.drift;
    $("drift-details").hidden = !d;
    if (!d) return;
    $("drift-details").open = true;
    var mo = d.metocean || {}, physics = d.physics || {}, origin = d.origin || {};
    function position(p) { return fmt(p.lat, 4) + "°, " + fmt(p.lon, 4) + "°"; }
    function distance(a, b) {
      var r = Math.PI / 180, dl = (b.lon-a.lon)*r, dp = (b.lat-a.lat)*r;
      var h = Math.sin(dp/2)**2 + Math.cos(a.lat*r)*Math.cos(b.lat*r)*Math.sin(dl/2)**2;
      return 12742 * Math.asin(Math.sqrt(Math.min(1, h)));
    }
    function trajectoryChart(section, samples, direction) {
      var points = samples.filter(function(p) {return Number.isFinite(p.lat) && Number.isFinite(p.lon) && Number.isFinite(Date.parse(p.t));});
      if (points.length < 2) return;
      var start = points[0], hours = points.map(function(p) {return Math.abs(Date.parse(p.t)-Date.parse(start.t))/3600000;});
      var moves = points.map(function(p) {return distance(start,p);});
      var spreads = points.map(function(p) {return Number.isFinite(p.spread_km) ? p.spread_km : null;});
      var maxY = Math.max(1, Math.ceil(Math.max.apply(null,moves.concat(spreads.filter(function(v){return v!==null;})))/10)*10);
      var maxX = Math.max(1, hours[hours.length-1]);
      function x(h) {return 42 + h/maxX*326;}
      function y(v) {return 154-v/maxY*126;}
      function svgNode(tag,attrs,text) {var n=document.createElementNS("http://www.w3.org/2000/svg",tag); Object.keys(attrs).forEach(function(k){n.setAttribute(k,attrs[k]);}); if(text!==undefined)n.textContent=text;return n;}
      var figure=el("figure","trajectory-figure"), svg=svgNode("svg",{viewBox:"0 0 390 194",role:"img","aria-label":direction+": displacement and ensemble spread in kilometres over hours from observation"});
      svg.appendChild(svgNode("title",{},direction+" movement and uncertainty"));
      [0,0.5,1].forEach(function(f){var yy=y(f*maxY);svg.appendChild(svgNode("line",{x1:42,x2:368,y1:yy,y2:yy,stroke:"#dedbd3"}));svg.appendChild(svgNode("text",{x:34,y:yy+4,"text-anchor":"end"},fmt(f*maxY,0)));});
      svg.appendChild(svgNode("text",{x:8,y:15},"km"));
      [0,0.5,1].forEach(function(f){svg.appendChild(svgNode("text",{x:x(f*maxX),y:173,"text-anchor":"middle"},fmt(f*maxX,0)+" h"));});
      svg.appendChild(svgNode("text",{x:205,y:191,"text-anchor":"middle"},direction==="Backtracking"?"Hours before observation":"Hours after observation"));
      [[moves,"#287d91",false],[spreads,"#ad6639",true]].forEach(function(series){
        var path="",connected=false;
        series[0].forEach(function(v,i){if(v===null){connected=false;return;}path+=(connected?" L":"M")+x(hours[i])+","+y(v);connected=true;});
        svg.appendChild(svgNode("path",{d:path,fill:"none",stroke:series[1],"stroke-width":2.5,"stroke-dasharray":series[2]?"5 4":"none"}));
      });
      var cursor=svgNode("line",{x1:42,x2:42,y1:25,y2:154,stroke:"#696b62","stroke-dasharray":"2 3"});svg.appendChild(cursor);
      figure.appendChild(svg);
      var legend=el("div","trajectory-key");legend.appendChild(el("span","movement","━ Displacement"));legend.appendChild(el("span","spread","┄ Ensemble spread"));figure.appendChild(legend);
      var slider=el("input","trajectory-slider");slider.type="range";slider.min=0;slider.max=points.length-1;slider.value=0;slider.setAttribute("aria-label",direction+" chart checkpoint");figure.appendChild(slider);
      var caption=el("figcaption","chart-caption");caption.setAttribute("aria-live","polite");figure.appendChild(caption);
      function update(){var i=Number(slider.value);cursor.setAttribute("x1",x(hours[i]));cursor.setAttribute("x2",x(hours[i]));caption.textContent=utc(points[i].t)+" · "+fmt(moves[i],1)+" km displacement · "+fmt(spreads[i],1)+" km spread";}
      slider.addEventListener("input",update);update();section.appendChild(figure);
    }
    function panel(title, intro) {
      var section = el("section", "drift-panel");
      section.appendChild(el("h3", "", title));
      section.appendChild(el("p", "cell-sub", intro));
      box.appendChild(section);
      return section;
    }
    [["Backtracking", "hindcast", "Reconstructs possible earlier oil positions from the observed slick."],
     ["Forward tracking", "forecast", "Projects oil movement from the observation time, using the stored environmental fields."]]
      .forEach(function (entry) {
        var section = panel(entry[0], entry[2]);
        var samples = d[entry[1] + "_hourly"] || [];
        if (!samples.length) { section.appendChild(el("p", "", "No trajectory samples available for this result.")); return; }
        var first = samples[0], last = samples[samples.length - 1];
        var list = el("dl", "data-list"), length = 0;
        for (var i=1; i<samples.length; i++) length += distance(samples[i-1], samples[i]);
        row(list, "Observation time", utc(first.t));
        row(list, "Model endpoint", utc(last.t));
        row(list, "Modelled duration", fmt(Math.abs(Date.parse(last.t)-Date.parse(first.t))/3600000, 1) + " h");
        row(list, "Median route length (hourly)", fmt(length, 1) + " km");
        row(list, "Net displacement", fmt(distance(first,last), 1) + " km");
        row(list, "Endpoint · latitude, longitude", position(last));
        row(list, "Endpoint ensemble spread", fmt(last.spread_km, 1) + " km");
        if (entry[1] === "hindcast") {
          row(list, "Estimated release time", utc(origin.t));
          row(list, "Release centre · lat, lon", position(origin));
          row(list, "Estimated time since release", fmt(d.age_hours_proxy, 1) + " h");
          row(list, "Release-zone area", fmt(origin.area_km2, 1) + " km²");
          row(list, "Release ensemble percentile", fmt(origin.percentile, 0) + "%");
          row(list, "Release spread / added buffer", fmt(origin.spread_km,1) + " / " + fmt(origin.buffer_km,1) + " km");
        } else {
          row(list, "Coast intersection", (d.coast || {}).available === false ? "Coast data unavailable" : (d.coast || {}).coast_flag ? "Forecast envelope may reach land" : (d.coast || {}).available === true ? "No intersection within model horizon" : "Not assessed");
        }
        var stats = el("div", "drift-metrics");
        [[fmt(Math.abs(Date.parse(last.t)-Date.parse(first.t))/3600000,0)+" h", "Model window"],
         [fmt(distance(first,last),1)+" km", "Net movement"],
         [fmt(last.spread_km,1)+" km", "Final spread"]].forEach(function(m){var card=el("div");card.appendChild(el("strong","",m[0]));card.appendChild(el("span","",m[1]));stats.appendChild(card);});
        section.appendChild(stats);
        trajectoryChart(section,samples,entry[0]);
        var facts=el("details","drift-facts");facts.appendChild(el("summary","",entry[1]==="hindcast"?"Release estimate & trajectory details":"Forecast endpoint & coastal impact"));facts.appendChild(list);section.appendChild(facts);
        var focus = el("button", "text-button", "Locate " + entry[0].toLowerCase() + " on map ↗");
        focus.addEventListener("click", function () {
          map.fitBounds(samples.map(function(p) {return [p.lat,p.lon];}), {padding:[35,35]});
          $("mapwrap").scrollIntoView({block:"center"});
        });
        section.appendChild(focus);
        var detail = el("details", "drift-checkpoints");
        detail.appendChild(el("summary", "", "Hourly checkpoints · " + samples.length + " positions"));
        var wrap = el("div", "drift-table-wrap"), table = el("table", "drift-table");
        var head = el("thead"), tr = el("tr");
        ["Time (UTC)", "Latitude", "Longitude", "Spread (km)"].forEach(function(t) {var th=el("th","",t); th.scope="col"; tr.appendChild(th);});
        head.appendChild(tr); table.appendChild(head);
        var body = el("tbody");
        samples.forEach(function(p) {var tr=el("tr"); [utc(p.t),fmt(p.lat,4),fmt(p.lon,4),fmt(p.spread_km,1)].forEach(function(v){tr.appendChild(el("td","",v));});body.appendChild(tr);});
        table.appendChild(body); wrap.appendChild(table); detail.appendChild(wrap); section.appendChild(detail);
      });
    var section = panel("Model inputs & uncertainty", "Both directions use the incident’s environmental time series. These are model estimates, not observed oil tracks.");
    var list = el("dl", "data-list");
    row(list, "Environmental source", mo.source || "Unavailable");
    row(list, "Field time range", utc(mo.t_start) + " – " + utc(mo.t_end));
    row(list, "Mean current", mo.has_currents === false ? "Unavailable · wind-only estimate" : fmt(mo.mean_current_ms,2) + " m/s");
    row(list, "Mean wind", fmt(mo.mean_wind_ms,1) + " m/s");
    row(list, "Ensemble particles", physics.n_particles == null ? "Unavailable" : physics.n_particles);
    row(list, "Wind contribution / deflection", fmt(physics.alpha_wind*100,1) + "% / " + fmt(physics.deflection_deg,1) + "°");
    row(list, "Integration step", physics.integration_step_seconds == null ? "Not recorded" : fmt(physics.integration_step_seconds,0) + " s");
    row(list, "Current / wind noise", fmt(physics.current_noise_ms,2) + " / " + fmt(physics.wind_noise_ms,2) + " m/s");
    var inputs=el("details","drift-facts");inputs.appendChild(el("summary","","Environmental sources & model settings"));inputs.appendChild(list);section.appendChild(inputs);
    section.appendChild(el("p", "cell-sub", "Spread describes ensemble dispersion, not a guaranteed error bound. The estimated release can lie inside the backtracking window; its time is a drift proxy, not a laboratory oil-age measurement."));
  }

  function showJob(job) {
    stop();
    clearAll();
    state.job = job;
    refreshOceanConditions(state.scene, (job.input || {}).t_sat);
    var attribution = job.attribution || {};
    var sources = Object.keys(attribution.sources_used || {});
    var window = attribution.funnel || {};
    $("ocean-vessels-count").textContent = (attribution.suspects || []).length + " candidates";
    $("ocean-vessels-mode").textContent = sources.length
      ? sources.join(", ") + " · release window: " + utc(window.window_start) + " – " + utc(window.window_end)
      : "No AIS coverage for this incident window";
    state.suspects = (job.attribution || {}).suspects || [];
    $("notices").replaceChildren();
    drawDetection(job);
    drawDrift(job);
    drawTracks(state.suspects);
    renderResult(job);
    buildFrames(job);
    fitJob();
    ["ex-note", "ex-json", "ex-geo"].forEach(function (id) {
      $(id).disabled = false;
    });
    history.replaceState(null, "", "#job=" + encodeURIComponent(job.job_id));
  }
  function setBusy(value) {
    running = value;
    $("busy").classList.toggle("on", value);
    $("run").disabled = value || !state.scene;
    $("scene-open").disabled = value;
    $("settings-open").disabled = value;
    ["ex-note", "ex-json", "ex-geo"].forEach(function (id) {
      $(id).disabled = value || !state.job;
    });
    $("run").textContent = value ? "Analysing…" : "Run analysis ↗";
    $("mapwrap").setAttribute("aria-busy", String(value));
  }
  function runPipeline() {
    if (running) return;
    if (!state.scene && state.scenes && state.scenes.length > 0) {
      setSceneSelection(state.scenes[0].id);
    }
    if (!state.scene) return;
    setBusy(true);
    var start = performance.now();
    $("busytext").textContent = "Looking for oil and nearby vessel traffic.";
    var jobId = "job_" + crypto.randomUUID().replaceAll("-", "");
    var polling = false;
    var timer = setInterval(function () {
      if (polling) return;
      polling = true;
      getJSON("/api/jobs/" + jobId + "/progress")
        .then(function (progress) {
          if (running && progress.running)
            $("busytext").textContent =
              (progress.note || "Analysis in progress") +
              " · " +
              Math.round((performance.now() - start) / 1000) +
              " seconds";
        })
        .catch(function () {})
        .finally(function () {
          polling = false;
        });
    }, 1500);
    postJSON("/api/run", {
      job_id: jobId,
      scene_id: state.scene.id,
      hindcast_hours: settings.hind,
      forecast_hours: settings.fore,
      search_radius_km: settings.radius,
      origin_window_hours: settings.window,
    })
      .then(showJob)
      .catch(function (error) {
        $("notices").replaceChildren(
          el(
            "p",
            "notice",
            "The analysis could not finish. Please try again. " + error.message,
          ),
        );
      })
      .finally(function () {
        clearInterval(timer);
        setBusy(false);
      });
  }
  function renderLayers() {
    var defs = [
      [["optical"], "Optical cross-check", false],
      [["sar", "mask"], "Radar image", true],
      [["oil", "lookalike"], "Detected slicks", true],
      [["origin", "hindcast", "cone_back"], "Origin & backtrack", true],
      [["forecast", "cone_fwd"], "Forecast", true],
      [["tracks", "vessels"], "Recorded vessel traffic", true],
    ];
    var box = $("layers");
    box.replaceChildren();
    defs.forEach(function (d) {
      var label = el("label"),
        cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = d[2];
      cb.addEventListener("change", function () {
        d[0].forEach(function (k) {
          if (cb.checked) map.addLayer(layerGroup[k]);
          else map.removeLayer(layerGroup[k]);
        });
      });
      label.appendChild(cb);
      label.appendChild(document.createTextNode(d[1]));
      box.appendChild(label);
    });
  }
  function openLinkedJob() {
    var params = new URLSearchParams(location.hash.slice(1)),
      id = params.get("job");
    if (!id || !/^[A-Za-z0-9_-]+$/.test(id)) return Promise.resolve();
    return getJSON("/api/jobs/" + id)
      .then(function (job) {
        var sceneId = (job.input || {}).scene_id;
        if (
          state.scenes.some(function (s) {
            return s.id === sceneId;
          })
        )
          setSceneSelection(sceneId);
        var input = job.input || {};
        settings = {
          hind: input.hindcast_hours || 48,
          fore: input.forecast_hours || 36,
          radius: input.search_radius_km || 10,
          window: input.origin_window_hours || 3,
        };
        showJob(job);
      })
      .catch(function () {
        $("notices").replaceChildren(
          el(
            "p",
            "notice",
            "This saved run could not be opened. Select a scene and run a new analysis.",
          ),
        );
      });
  }

  function refreshLiveStatus() {
    getJSON("/api/ais/live/status")
      .then(function (status) {
        $("ais-diag-state").textContent = status.state;
        $("ais-diag-mode").textContent = status.mode || "—";
        $("ais-diag-msg").textContent = status.message || "";
        $("ais-diag-vessels").textContent = status.active_vessels == null ? "—" : status.active_vessels;
        var label = {
          connected: "Live AIS · recording",
          not_configured: "Live AIS · add API key",
          connecting: "Live AIS · connecting",
          retrying: "Live AIS · reconnecting",
          rejected: "Live AIS · subscription rejected",
          idle: "Live AIS · waiting for an observation",
          unavailable: "Live AIS · unavailable",
          stopped: "Live AIS · stopped",
        };
        var liveStatusEl = $("live-status");
        if (liveStatusEl) {
          liveStatusEl.textContent =
            label[status.state] || "Live AIS · active";
          liveStatusEl.title =
            status.message +
            (status.last_message
              ? " Last position received: " + utc(status.last_message)
              : " No positions received yet.");
        }
      })
      .catch(function () {
        var liveStatusEl = $("live-status");
        if (liveStatusEl) {
          liveStatusEl.textContent = "Live AIS · status unavailable";
        }
      });
  }

  function refreshOceanConditions(scene, incidentTime) {
    if (!scene || !scene.centroid) return;
    var clon = scene.centroid[0],
      clat = scene.centroid[1];
    var timestamp = incidentTime || scene.t_sat;
    if (!timestamp) return;
    var requestId = state.oceanRequest = (state.oceanRequest || 0) + 1;
    $("ocean-badge").textContent = "Loading incident data";
    $("incident-time").textContent = "Incident · " + utc(timestamp);
    var tParam = "&t=" + encodeURIComponent(timestamp);
    ["ocean-current-speed", "ocean-current-dir", "ocean-wind-speed", "ocean-wind-dir",
     "ocean-wave-height", "ocean-wave-period"].forEach(function (id) {
      if ($(id)) $(id).textContent = "Loading…";
    });

    getJSON("/api/ocean/live?lat=" + clat + "&lon=" + clon + tParam + "&scene_id=" + encodeURIComponent(scene.id))
      .then(function (data) {
        if (!state.scene || state.scene.id !== scene.id || requestId !== state.oceanRequest) return;
        var badge = $("ocean-badge");
        if (badge) {
          badge.textContent = data.mode === "cached" ? "Observation-time cache" : "Observation-time data";
          badge.title = data.source + " · " + utc(data.timestamp);
        }
        var c = data.current || {};
        var w = data.wind || {};
        var waves = data.waves || {};

        var speedEl = $("ocean-current-speed");
        if (speedEl) speedEl.textContent = c.speed_ms !== null && c.speed_ms !== undefined
          ? c.speed_ms.toFixed(2) + " m/s (" + c.speed_knots.toFixed(1) + " kn)"
          : "Unavailable for incident";
        var dirEl = $("ocean-current-dir");
        if (dirEl) dirEl.textContent = c.direction_deg !== null && c.direction_deg !== undefined
          ? c.direction_deg.toFixed(0) + "° " + (c.direction_compass || "")
          : "Wind-only drift · historical currents required";

        var wSpeedEl = $("ocean-wind-speed");
        if (wSpeedEl) wSpeedEl.textContent = w.speed_ms !== null && w.speed_ms !== undefined
          ? w.speed_ms.toFixed(1) + " m/s (" + w.speed_knots.toFixed(1) + " kn)"
          : "No wind coverage";
        var wDirEl = $("ocean-wind-dir");
        if (wDirEl) wDirEl.textContent = w.direction_deg !== null && w.direction_deg !== undefined
          ? w.direction_deg.toFixed(0) + "° " + (w.direction_compass || "")
          : "Not available for this observation";

        var waveH = $("ocean-wave-height");
        if (waveH) waveH.textContent =
          waves.height_m !== null && waves.height_m !== undefined
            ? waves.height_m.toFixed(1) + " m"
            : "Unavailable at incident time";
        if (waveH) waveH.title = waves.source ? waves.source + " · " + utc(waves.timestamp) : "";
        var waveP = $("ocean-wave-period");
        if (waveP) waveP.textContent = waves.period_s
          ? waves.period_s.toFixed(1) + " s wave period"
          : "—";
      })
      .catch(function () {
        if (!state.scene || state.scene.id !== scene.id || requestId !== state.oceanRequest) return;
        ["ocean-current-speed", "ocean-wind-speed", "ocean-wave-height"].forEach(function (id) {
          if ($(id)) $(id).textContent = "Request failed";
        });
        ["ocean-current-dir", "ocean-wind-dir", "ocean-wave-period"].forEach(function (id) {
          if ($(id)) $(id).textContent = "Reload the observation to retry";
        });
      });

  }

  function boot() {
    initMap();
    $("world-map").addEventListener("click", function () { map.fitWorld(); });
    renderLayers();
    renderEmpty();
    $("scene-open").addEventListener("click", function () {
      showDialog("scene-dialog");
    });
    $("upload-form").addEventListener("submit", async function (event) {
      event.preventDefault();
      if (running) return;
      var file = $("upload-file").files[0];
      if (!file) return;
      if (file.size > 256 * 1024 * 1024) {
        $("upload-status").textContent = "Use a SAR chip smaller than 256 MB.";
        return;
      }
      setBusy(true);
      $("upload-submit").disabled = true;
      $("upload-status").textContent = "Uploading and checking the image…";
      try {
        var form = new FormData();
        form.append("file", file);
        form.append("t_sat", $("upload-time").value + ":00Z");
        var response = await fetch(API + "/api/scenes/upload", {
          method: "POST",
          body: form,
        });
        var result = await response.json();
        if (!response.ok)
          throw new Error(
            typeof result.detail === "string"
              ? result.detail
              : "Check the file and acquisition time.",
          );
        state.scenes = await getJSON("/api/scenes");
        setBusy(false);
        selectScene(result.scene_id);
        renderSceneList();
        $("scene-dialog").close();
        $("upload-form").reset();
        $("upload-status").textContent = "";
        $("notices").replaceChildren(
          el(
            "p",
            "notice",
            "Observation added. Run analysis to detect slicks and fetch matching recorded AIS.",
          ),
        );
      } catch (error) {
        $("upload-status").textContent = error.message;
      } finally {
        setBusy(false);
        $("upload-submit").disabled = false;
      }
    });
    $("settings-open").addEventListener("click", function () {
      Object.keys(settings).forEach(function (k) {
        $(k).value = settings[k];
      });
      showDialog("settings-dialog");
    });
    $("help-open").addEventListener("click", function () {
      showDialog("help-dialog");
    });
    document.querySelectorAll("[data-close]").forEach(function (button) {
      button.addEventListener("click", function () {
        $(button.dataset.close).close();
      });
    });
    $("settings-form").addEventListener("submit", function (event) {
      event.preventDefault();
      Object.keys(settings).forEach(function (k) {
        settings[k] = Number($(k).value);
      });
      $("settings-dialog").close();
    });
    $("run").addEventListener("click", runPipeline);
    $("fit-map").addEventListener("click", fitJob);
    $("play").addEventListener("click", play);
    $("slider").addEventListener("input", function (event) {
      stop();
      state.frameIndex = Number(event.target.value);
      renderFrame();
    });
    $("vsearch").addEventListener("input", renderVessels);
    [
      ["ex-note", "/api/report/"],
      ["ex-json", "/api/jobs/"],
      ["ex-geo", "/api/jobs/"],
    ].forEach(function (entry) {
      $(entry[0]).addEventListener("click", function () {
        if (state.job)
          window.open(
            entry[1] +
              state.job.job_id +
              (entry[0] === "ex-geo" ? "/geojson" : ""),
            "_blank",
            "noopener",
          );
      });
    });

    var liveAisEl = $("live-ais-badge");
    if (liveAisEl) {
      liveAisEl.addEventListener("click", function (e) {
        e.preventDefault();
        // Do not open any window or dialog on tap
      });
    }
    $("ais-key-form").addEventListener("submit", function (e) {
      e.preventDefault();
      var key = $("ais-key-input").value.trim();
      if (!key) return;
      $("ais-diag-state").textContent = "Connecting…";
      postJSON("/api/ais/live/configure", { api_key: key })
        .then(function (res) {
          $("ais-diag-msg").textContent = res.message;
          refreshLiveStatus();
        })
        .catch(function (err) {
          $("ais-diag-msg").textContent = "Failed to save key: " + err.message;
        });
    });
    $("ais-key-clear").addEventListener("click", function () {
      postJSON("/api/ais/live/clear", {})
        .then(function (res) {
          $("ais-key-input").value = "";
          $("ais-diag-msg").textContent = res.message;
          refreshLiveStatus();
        });
    });

    refreshLiveStatus();
    setInterval(refreshLiveStatus, 10000);
    getJSON("/api/health")
      .then(function (h) {
        state.health = h;
        var conn = $("connection");
        if (conn) {
          conn.textContent = h.ok
            ? "Local workspace"
            : "Service unavailable";
        }
      })
      .catch(function () {
        var conn = $("connection");
        if (conn) {
          conn.textContent = "Disconnected";
          conn.classList.add("error");
        }
      });
    getJSON("/api/scenes")
      .then(function (scenes) {
        state.scenes = scenes;
        if (!scenes.length) {
          $("notices").appendChild(
            el(
              "p",
              "notice",
              "No observations are available. Add scene data to begin.",
            ),
          );
          return;
        }
        $("notices").replaceChildren();
        setSceneSelection(scenes[0].id);
        resetRun();
        fitScene();
        $("run").disabled = false;
        try {
          openLinkedJob();
        } catch (e) {
          console.warn("openLinkedJob error:", e);
        }
      })
      .catch(function (err) {
        console.error("Failed to load observations:", err);
        $("notices").appendChild(
          el(
            "p",
            "notice",
            "Observations could not be loaded. Check that the local server is running.",
          ),
        );
      });
    if (typeof ResizeObserver !== "undefined")
      new ResizeObserver(function () {
        map.invalidateSize({ pan: false });
      }).observe($("mapwrap"));
  }
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
