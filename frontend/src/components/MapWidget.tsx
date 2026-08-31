import { Asset } from "expo-asset";
import * as FileSystem from "expo-file-system";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { WebView } from "react-native-webview";

import { MapWidgetT } from "@/src/api";
import { colors, fonts, radius, spacing } from "@/src/theme";

const CARTO_KEY = process.env.EXPO_PUBLIC_CARTO_KEY || "";
const LOAD_TIMEOUT_MS = 9000;

// MapLibre GL JS + CSS are bundled as LOCAL assets (not fetched from a CDN
// at runtime). Loading the map engine from an external CDN inside the
// WebView proved unreliable on real devices/networks in the field — the
// exact same class of failure as an earlier CDN font-loading bug. Bundling
// it locally guarantees the map engine always initialises offline-first;
// only the basemap TILE IMAGES (CARTO PNGs) need live network access, and
// those fail gracefully to a plain grid rather than breaking the widget.
const MAPLIBRE_JS_ASSET = require("../../assets/maplibre/maplibre-gl.js.html");
const MAPLIBRE_CSS_ASSET = require("../../assets/maplibre/maplibre-gl.css.html");

type Libs = { js: string; css: string } | null;
let cachedLibs: Libs = null;
let loadingLibs: Promise<Libs> | null = null;

async function loadMapLibs(): Promise<Libs> {
  if (cachedLibs) return cachedLibs;
  if (loadingLibs) return loadingLibs;
  loadingLibs = (async () => {
    try {
      const [jsAsset, cssAsset] = await Promise.all([
        Asset.fromModule(MAPLIBRE_JS_ASSET).downloadAsync(),
        Asset.fromModule(MAPLIBRE_CSS_ASSET).downloadAsync(),
      ]);
      const jsUri = jsAsset.localUri || jsAsset.uri;
      const cssUri = cssAsset.localUri || cssAsset.uri;
      const [js, css] = await Promise.all([
        FileSystem.readAsStringAsync(jsUri),
        FileSystem.readAsStringAsync(cssUri),
      ]);
      cachedLibs = { js, css };
      return cachedLibs;
    } catch {
      return null; // caller falls back to CDN <link>/<script src> tags
    }
  })();
  return loadingLibs;
}

// Renders base CARTO Voyager raster tiles + boundary polygons + SST/chl
// heatmap + markers. Reports success/failure back to React Native via
// postMessage so a broken map is never silently blank.
function buildHtml(widget: MapWidgetT, libs: Libs) {
  const w = JSON.stringify(widget);
  const tileUrl = CARTO_KEY
    ? `https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=${encodeURIComponent(CARTO_KEY)}`
    : "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png";
  const cssTag = libs ? `<style>${libs.css}</style>` : (
    `<link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet"/>`
  );
  const jsTag = libs ? `<script>${libs.js}</script>` : (
    `<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>`
  );
  return `<!DOCTYPE html><html><head>
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
${cssTag}
${jsTag}
<style>
 html,body{margin:0;padding:0;height:100%;width:100%;overflow:hidden;background:#0A0E17}
 #map{position:absolute;inset:0;height:100%;width:100%;overflow:hidden}
 .mk{width:16px;height:16px;border:2px solid #0A0E17;box-sizing:border-box;box-shadow:0 0 0 1px rgba(255,255,255,0.35)}
 .maplibregl-popup-content{border-radius:8px;border:1px solid #1E2A3A;background:#0F1520;color:#E6EDF3;font-family:monospace;font-size:12px;padding:6px 8px}
 .maplibregl-popup-anchor-top .maplibregl-popup-tip{border-bottom-color:#0F1520}
 .maplibregl-popup-anchor-bottom .maplibregl-popup-tip{border-top-color:#0F1520}
 .maplibregl-ctrl-attrib{font-size:9px !important;background:rgba(10,14,23,0.55) !important}
 .maplibregl-ctrl-attrib a{color:#AEB9C7 !important}
 .maplibregl-canvas{border-radius:0 !important}
</style></head><body><div id="map"></div>
<script>
function post(msg){ try{ window.ReactNativeWebView.postMessage(JSON.stringify(msg)); }catch(e){} }
window.onerror = function(msg){ post({type:'error', message:String(msg)}); };
var W = ${w};
try {
  if (typeof maplibregl === 'undefined') throw new Error('maplibregl failed to load');
  var map = new maplibregl.Map({
    container:'map',
    style:{version:8,sources:{base:{type:'raster',tiles:['${tileUrl}'],tileSize:256,attribution:'© OpenStreetMap contributors © CARTO'}},layers:[{id:'base',type:'raster',source:'base'}]},
    center:[W.center.lon,W.center.lat],
    zoom:8, attributionControl:true, maxZoom:18, minZoom:2
  });
  map.dragRotate.disable();
  map.touchZoomRotate.disableRotation();
  map.on('error', function(e){ post({type:'error', message: (e && e.error && e.error.message) || 'tile error'}); });
  map.on('load',function(){
    try {
      (W.layers||[]).forEach(function(l,i){
        if(l.type==='boundary' && l.features){
          var fc={type:'FeatureCollection',features:l.features.filter(function(b){return b.geometry;}).map(function(b){return {type:'Feature',properties:{restricted:!!b.restricted,name:b.name},geometry:b.geometry};})};
          map.addSource('b'+i,{type:'geojson',data:fc});
          map.addLayer({id:'bf'+i,type:'fill',source:'b'+i,paint:{'fill-color':['case',['get','restricted'],'#FF5B6E','#E9B44C'],'fill-opacity':0.22}});
          map.addLayer({id:'bl'+i,type:'line',source:'b'+i,paint:{'line-color':['case',['get','restricted'],'#FF5B6E','#E9B44C'],'line-width':2}});
        }
        if(l.type==='heatmap' && l.grid){
          var metric=l.metric;
          var vals=l.grid.map(function(p){return metric==='chl'?p.chl_mg_m3:p.sst_c;});
          var mn=Math.min.apply(null,vals),mx=Math.max.apply(null,vals),mid=(mn+mx)/2;
          var fc={type:'FeatureCollection',features:l.grid.map(function(p){return {type:'Feature',properties:{v:metric==='chl'?p.chl_mg_m3:p.sst_c},geometry:{type:'Point',coordinates:[p.lon,p.lat]}};})};
          map.addSource('h'+i,{type:'geojson',data:fc});
          map.addLayer({id:'hc'+i,type:'circle',source:'h'+i,paint:{'circle-radius':22,'circle-blur':1,'circle-opacity':0.55,'circle-color':['interpolate',['linear'],['get','v'],mn,'#3FD07F',mid,'#E9B44C',mx,'#FF5B6E']}});
        }
        if(l.type==='route_line' && l.segments){
          var fc={type:'FeatureCollection',features:l.segments.map(function(s){return {type:'Feature',properties:{unsafe:!!s.unsafe},geometry:{type:'LineString',coordinates:[s.a,s.b]}};})};
          map.addSource('rt'+i,{type:'geojson',data:fc});
          map.addLayer({id:'rtcase'+i,type:'line',source:'rt'+i,layout:{'line-cap':'round','line-join':'round'},paint:{'line-color':['case',['get','unsafe'],'#FF5B6E','#3FD07F'],'line-width':5,'line-opacity':0.9}});
        }
      });
      var bounds=new maplibregl.LngLatBounds();
      (W.markers||[]).forEach(function(m){
        var el=document.createElement('div');el.className='mk';
        var c='#3B9EFF';
        if(m.kind==='pfz'||m.kind==='route_safe')c='#3FD07F';
        if(m.kind==='route_unsafe')c='#FF5B6E';
        if(m.kind==='route_start'){c='#FFFFFF';el.style.borderRadius='50%';el.style.width='20px';el.style.height='20px';}
        if(m.kind==='route_end'){c='#3B9EFF';el.style.width='20px';el.style.height='20px';el.style.transform='rotate(45deg)';}
        if(m.kind==='pfz_recommended'){c='#E9B44C';el.style.width='24px';el.style.height='24px';el.style.borderRadius='50%';el.style.border='3px solid #FFFFFF';el.style.boxShadow='0 0 0 3px rgba(233,180,76,0.4)';}
        el.style.background=c;
        if(m.kind==='user'){el.style.borderRadius='50%';el.style.background='#FFFFFF';}
        new maplibregl.Marker({element:el}).setLngLat([m.lon,m.lat]).setPopup(new maplibregl.Popup({offset:12,closeButton:false}).setText(m.label)).addTo(map);
        bounds.extend([m.lon,m.lat]);
      });
      try{ if(!bounds.isEmpty()) map.fitBounds(bounds,{padding:46,maxZoom:11,duration:0});}catch(e){}
      map.resize();
      post({type:'ready'});
    } catch(e){ post({type:'error', message:String(e && e.message || e)}); }
  });
} catch(e){
  post({type:'error', message:String(e && e.message || e)});
  document.body.innerHTML='<div style="font-family:monospace;padding:16px;color:#AEB9C7">Map unavailable</div>';
}
</script></body></html>`;
}

// react-native-webview renders as a permanent no-op on the web platform
// (it can never fire onMessage/onError/load), so the interactive
// MapLibre WebView is native-only. On web we render a lightweight,
// always-visible coordinate list instead of a spinner that times out
// after LOAD_TIMEOUT_MS with a dead-end "Map failed to load" — this is
// what makes PFZ zones (and every other marker) locatable from a browser
// preview, not just from the Expo Go / native app.
function markerColor(kind: string) {
  if (kind === "pfz" || kind === "route_safe") return colors.success;
  if (kind === "pfz_recommended") return colors.warning;
  if (kind === "route_unsafe") return colors.error;
  if (kind === "route_start") return colors.onSurface;
  if (kind === "route_end") return colors.brand;
  if (kind === "user") return colors.onSurface;
  return colors.brand;
}

const hasRoute = (widget: MapWidgetT) =>
  (widget.markers || []).some((m) => m.kind?.startsWith("route_"));
const hasNamedRoute = (widget: MapWidgetT) =>
  (widget.markers || []).some((m) => m.kind === "route_start" || m.kind === "route_end");
const hasRecommendedPfz = (widget: MapWidgetT) =>
  (widget.markers || []).some((m) => m.kind === "pfz_recommended");

function WebMarkerList({ widget }: { widget: MapWidgetT }) {
  const markers = widget.markers || [];
  const unsafeCount = markers.filter((m) => m.kind === "route_unsafe").length;
  const isRoute = hasRoute(widget);
  return (
    <View style={styles.webListBox}>
      {isRoute && (
        <Text style={[styles.webListRouteBanner, unsafeCount > 0 && styles.webListRouteBannerUnsafe]}>
          {unsafeCount > 0
            ? `⚠ ROUTE PASSES THROUGH ${unsafeCount} UNSAFE STRETCH${unsafeCount > 1 ? "ES" : ""}`
            : "✓ ROUTE CLEAR — NO HAZARDS DETECTED"}
        </Text>
      )}
      {markers.length === 0 ? (
        <Text style={styles.webListEmpty}>No map markers for this answer.</Text>
      ) : (
        markers.map((m, i) => (
          <View key={`${m.label}-${i}`} style={styles.webListRow}>
            <View style={[styles.dot, { backgroundColor: markerColor(m.kind), borderRadius: m.kind === "user" || m.kind === "route_start" || m.kind === "pfz_recommended" ? 8 : 0 }]} />
            <View style={styles.webListText}>
              <Text style={[styles.webListLabel, m.kind === "route_unsafe" && { color: colors.error }, m.kind === "pfz_recommended" && { color: colors.warning }]}>
                {m.label}
              </Text>
              <Text style={styles.webListCoords}>
                {m.lat.toFixed(4)}, {m.lon.toFixed(4)}
              </Text>
            </View>
          </View>
        ))
      )}
      <Text style={styles.webListHint}>
        Interactive map renders in the mobile app (Expo Go) — showing coordinates here.
      </Text>
    </View>
  );
}

export default function MapWidget({ widget }: { widget: MapWidgetT }) {
  const isWeb = Platform.OS === "web";
  const [libs, setLibs] = useState<Libs | undefined>(undefined);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [retryKey, setRetryKey] = useState(0);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (isWeb) return;
    let alive = true;
    loadMapLibs().then((l) => {
      if (alive) setLibs(l);
    });
    return () => {
      alive = false;
    };
  }, [isWeb]);

  useEffect(() => {
    if (isWeb || libs === undefined) return;
    setStatus("loading");
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => setStatus("error"), LOAD_TIMEOUT_MS);
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [isWeb, libs, retryKey]);

  const onMessage = useCallback((e: any) => {
    try {
      const msg = JSON.parse(e.nativeEvent.data);
      if (msg.type === "ready") {
        if (timeoutRef.current) clearTimeout(timeoutRef.current);
        setStatus("ready");
      } else if (msg.type === "error") {
        if (timeoutRef.current) clearTimeout(timeoutRef.current);
        setStatus("error");
      }
    } catch {
      /* ignore malformed messages */
    }
  }, []);

  const retry = useCallback(() => setRetryKey((k) => k + 1), []);
  const isRoute = hasRoute(widget);

  return (
    <View testID="map-widget" style={styles.wrap}>
      <View style={styles.header}>
        <Text style={styles.headerText}>
          {isRoute ? "MAP · ROUTE PLAN" : "MAP · MapLibre + CARTO"}
        </Text>
      </View>
      {isWeb ? (
        <WebMarkerList widget={widget} />
      ) : (
        <View style={styles.mapBox}>
          {libs !== undefined && (
            <WebView
              key={retryKey}
              testID="map-webview"
              originWhitelist={["*"]}
              source={{ html: buildHtml(widget, libs), baseUrl: "https://orca.local/" }}
              javaScriptEnabled
              domStorageEnabled
              mixedContentMode="always"
              scrollEnabled={false}
              nestedScrollEnabled
              style={styles.web}
              androidLayerType="hardware"
              onMessage={onMessage}
              onError={() => setStatus("error")}
            />
          )}
          {status !== "ready" && (
            <View style={styles.overlay} pointerEvents={status === "error" ? "auto" : "none"}>
              {status === "loading" ? (
                <ActivityIndicator color={colors.brand} />
              ) : (
                <View style={styles.errorBox}>
                  <Text style={styles.errorText}>Map failed to load</Text>
                  <Pressable testID="map-retry" style={styles.retryBtn} onPress={retry}>
                    <Text style={styles.retryText}>RETRY</Text>
                  </Pressable>
                </View>
              )}
            </View>
          )}
        </View>
      )}
      <View style={styles.legend}>
        {hasNamedRoute(widget) ? (
          <>
            <Legend color={colors.onSurface} label="Start" round />
            <Legend color={colors.brand} label="Destination" />
            <Legend color={colors.success} label="Safe stretch" />
            <Legend color={colors.error} label="Unsafe stretch" />
          </>
        ) : hasRecommendedPfz(widget) ? (
          <>
            <Legend color={colors.onSurface} label="You" round />
            <Legend color={colors.warning} label="Recommended PFZ" />
            <Legend color={colors.success} label="Other PFZ / Safe path" />
            <Legend color={colors.error} label="Unsafe stretch" />
          </>
        ) : (
          <>
            <Legend color={colors.onSurface} label="You" round />
            <Legend color={colors.success} label="PFZ / Safe" />
            <Legend color={colors.error} label="Hazard / Restricted" />
          </>
        )}
      </View>
      <Text style={styles.attribution}>© OpenStreetMap contributors · © CARTO</Text>
    </View>
  );
}

function Legend({
  color,
  label,
  round,
}: {
  color: string;
  label: string;
  round?: boolean;
}) {
  return (
    <View style={styles.legendItem}>
      <View
        style={[
          styles.dot,
          { backgroundColor: color, borderRadius: round ? 8 : 0 },
        ]}
      />
      <Text style={styles.legendText}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    overflow: "hidden",
    marginTop: spacing.sm,
    backgroundColor: colors.surface,
  },
  header: {
    backgroundColor: colors.surfaceInverse,
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.sm,
  },
  headerText: {
    fontFamily: fonts.mono,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 1,
    color: colors.brand,
  },
  mapBox: { height: 240, width: "100%", overflow: "hidden" },
  web: { flex: 1, backgroundColor: colors.bg },
  overlay: {
    position: "absolute",
    inset: 0,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.bg,
  },
  errorBox: { alignItems: "center", gap: spacing.sm },
  errorText: {
    fontFamily: fonts.mono,
    fontSize: 11,
    color: colors.muted,
  },
  retryBtn: {
    borderWidth: 1,
    borderColor: colors.brand,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  retryText: {
    fontFamily: fonts.mono,
    fontSize: 11,
    fontWeight: "700",
    color: colors.brand,
  },
  webListBox: {
    padding: spacing.sm,
    gap: spacing.xs,
    backgroundColor: colors.bg,
  },
  webListRouteBanner: {
    fontFamily: fonts.mono,
    fontSize: 10,
    fontWeight: "700",
    color: colors.success,
    paddingBottom: spacing.xs,
    letterSpacing: 0.5,
  },
  webListRouteBannerUnsafe: {
    color: colors.error,
  },
  webListEmpty: {
    fontFamily: fonts.mono,
    fontSize: 11,
    color: colors.muted,
    paddingVertical: spacing.sm,
  },
  webListRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingVertical: spacing.xs,
    borderBottomWidth: 1,
    borderColor: colors.border,
  },
  webListText: { flex: 1 },
  webListLabel: {
    fontFamily: fonts.mono,
    fontSize: 12,
    fontWeight: "700",
    color: colors.onSurface,
  },
  webListCoords: {
    fontFamily: fonts.mono,
    fontSize: 10,
    color: colors.muted,
    marginTop: 2,
  },
  webListHint: {
    fontFamily: fonts.mono,
    fontSize: 9,
    color: colors.muted,
    paddingTop: spacing.xs,
  },
  legend: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.md,
    padding: spacing.sm,
    borderTopWidth: 1,
    borderColor: colors.border,
  },
  legendItem: { flexDirection: "row", alignItems: "center", gap: spacing.xs },
  dot: { width: 12, height: 12, borderWidth: 1, borderColor: colors.border },
  legendText: { fontFamily: fonts.mono, fontSize: 10, color: colors.onSurface },
  attribution: {
    fontFamily: fonts.mono,
    fontSize: 9,
    color: colors.muted,
    paddingHorizontal: spacing.sm,
    paddingBottom: spacing.sm,
  },
});
