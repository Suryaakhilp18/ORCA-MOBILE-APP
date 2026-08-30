import { StyleSheet, Text, View } from "react-native";
import { WebView } from "react-native-webview";

import { MapWidgetT } from "@/src/api";
import { colors, fonts, radius, spacing } from "@/src/theme";

// Inline MapLibre GL JS map rendered in a WebView (open-source, no paid SDK).
// Renders base OSM raster tiles + boundary polygons + SST/chl heatmap + markers.
function buildHtml(widget: MapWidgetT) {
  const w = JSON.stringify(widget);
  return `<!DOCTYPE html><html><head>
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet"/>
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<style>
 html,body,#map{margin:0;padding:0;height:100%;width:100%;background:#0A0E17}
 .mk{width:16px;height:16px;border:2px solid #0A0E17;box-sizing:border-box;box-shadow:0 0 0 1px rgba(255,255,255,0.35)}
 .maplibregl-popup-content{border-radius:8px;border:1px solid #1E2A3A;background:#0F1520;color:#E6EDF3;font-family:monospace;font-size:12px;padding:6px 8px}
 .maplibregl-popup-anchor-top .maplibregl-popup-tip{border-bottom-color:#0F1520}
 .maplibregl-popup-anchor-bottom .maplibregl-popup-tip{border-top-color:#0F1520}
</style></head><body><div id="map"></div>
<script>
var W = ${w};
try {
var map = new maplibregl.Map({
  container:'map',
  style:{version:8,sources:{base:{type:'raster',tiles:['https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png','https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png'],tileSize:256,attribution:'© OpenStreetMap © CARTO'}},layers:[{id:'base',type:'raster',source:'base'}]},
  center:[W.center.lon,W.center.lat],
  zoom:8, attributionControl:false
});
map.on('load',function(){
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
  });
  var bounds=new maplibregl.LngLatBounds();
  (W.markers||[]).forEach(function(m){
    var el=document.createElement('div');el.className='mk';
    var c='#3B9EFF';
    if(m.kind==='pfz'||m.kind==='route_safe')c='#3FD07F';
    if(m.kind==='route_unsafe')c='#FF5B6E';
    el.style.background=c;
    if(m.kind==='user'){el.style.borderRadius='50%';el.style.background='#FFFFFF';}
    new maplibregl.Marker({element:el}).setLngLat([m.lon,m.lat]).setPopup(new maplibregl.Popup({offset:12,closeButton:false}).setText(m.label)).addTo(map);
    bounds.extend([m.lon,m.lat]);
  });
  try{ if(!bounds.isEmpty()) map.fitBounds(bounds,{padding:46,maxZoom:11,duration:0});}catch(e){}
});
} catch(e){ document.body.innerHTML='<div style="font-family:monospace;padding:16px">Map unavailable</div>'; }
</script></body></html>`;
}

export default function MapWidget({ widget }: { widget: MapWidgetT }) {
  return (
    <View testID="map-widget" style={styles.wrap}>
      <View style={styles.header}>
        <Text style={styles.headerText}>MAP · MapLibre</Text>
      </View>
      <View style={styles.mapBox}>
        <WebView
          originWhitelist={["*"]}
          source={{ html: buildHtml(widget) }}
          javaScriptEnabled
          domStorageEnabled
          scrollEnabled={false}
          nestedScrollEnabled
          style={styles.web}
          androidLayerType="hardware"
        />
      </View>
      <View style={styles.legend}>
        <Legend color={colors.onSurface} label="You" round />
        <Legend color={colors.success} label="PFZ / Safe" />
        <Legend color={colors.error} label="Hazard / Restricted" />
      </View>
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
  mapBox: { height: 240, width: "100%" },
  web: { flex: 1, backgroundColor: colors.bg },
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
});
