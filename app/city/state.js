// Walk Through Time, city page: What the page knows and shows, shared by every module: S.data (the index), S.features, S.map, S.active (ticked layers)…
// One object, so that any module can read and change it (an imported variable cannot be reassigned).
export const S = {
  city: null,            // cities/<city>.json
  data: null,            // data/<city>.json: the index, layers, pins, areas
  features: [],          // one per building: { properties, full } (full: its card file has been merged in)
  map: null,             // the MapLibre map
  stats: null,           // { total, known, estimated }
  hist: null,            // buildings per year, for the count under the slider
  layers: [],            // layer metadata
  groups: new Map(),     // group key -> { key, title, count, items, layer }
  active: new Set(),     // ticked group keys
  entitiesAt: {},        // building index -> [{name, bs}] for people and stories with several places
  selectedId: null,      // the building whose card is open
  sheetKind: null,       // what the sheet shows: layers, map or card
  litOn: null,           // the building lit up while its plaque is open
  places: null,          // { name, bs, i }: the set of places shown in the strip
  pins: {},              // marker key -> maplibregl.Marker, for the places strip
  playing: null,         // Play running
  showUnknown: true,     // buildings with no date shown
  periodsOff: new Set(), // periods (their labels) hidden from the map: the Map sheet's legend
  cardFiles: {},         // card file number -> Promise
  osmIds: null,          // OpenStreetMap id of every building, loaded for links that name one
};
