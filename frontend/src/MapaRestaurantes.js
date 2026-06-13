import { useEffect, useRef } from "react";

export default function MapaRestaurantes({ restaurantes }) {
  const mapRef = useRef(null);
  const instanceRef = useRef(null);
  const markersRef = useRef([]);

  useEffect(() => {
    if (instanceRef.current) return;

    // Cargar Leaflet CSS
    if (!document.getElementById("leaflet-css")) {
      const link = document.createElement("link");
      link.id = "leaflet-css";
      link.rel = "stylesheet";
      link.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
      document.head.appendChild(link);
    }

    // Cargar Leaflet JS
    const script = document.createElement("script");
    script.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
    script.onload = () => {
      const L = window.L;
      const map = L.map(mapRef.current, {
        center: [40.4168, -3.7038],
        zoom: 13,
        zoomControl: true,
      });

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '© <a href="https://www.openstreetmap.org/">OpenStreetMap</a>',
        maxZoom: 19,
      }).addTo(map);

      instanceRef.current = map;

      // Geolocalización del usuario
      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition((pos) => {
          const { latitude, longitude } = pos.coords;
          const iconUser = L.divIcon({
            className: "",
            html: `<div style="width:14px;height:14px;background:#c8a96e;border:2px solid #fff;border-radius:50%;box-shadow:0 0 0 3px #c8a96e44"></div>`,
            iconSize: [14, 14],
            iconAnchor: [7, 7],
          });
          L.marker([latitude, longitude], { icon: iconUser })
            .addTo(map)
            .bindPopup("<b>Tu ubicación</b>")
            .openPopup();
        });
      }

      // Añadir marcadores iniciales si ya hay restaurantes
      if (restaurantes && restaurantes.length > 0) {
        addMarkers(L, map, restaurantes);
      }
    };
    document.head.appendChild(script);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Actualizar marcadores cuando cambian los restaurantes
  useEffect(() => {
    const L = window.L;
    const map = instanceRef.current;
    if (!L || !map || !restaurantes) return;

    // Limpiar marcadores anteriores
    markersRef.current.forEach(m => map.removeLayer(m));
    markersRef.current = [];

    if (restaurantes.length > 0) {
      addMarkers(L, map, restaurantes);
      // Centrar mapa en los restaurantes recomendados
      const bounds = L.latLngBounds(restaurantes.map(r => [r.latitud, r.longitud]));
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [restaurantes]);

  function addMarkers(L, map, lista) {
    lista.forEach((r, i) => {
      const iconRest = L.divIcon({
        className: "",
        html: `<div style="
          background:#111;border:2px solid #c8a96e;border-radius:50% 50% 50% 0;
          width:28px;height:28px;transform:rotate(-45deg);
          display:flex;align-items:center;justify-content:center;
          box-shadow:0 2px 6px rgba(0,0,0,0.4)">
          <span style="transform:rotate(45deg);font-size:13px">🍽</span>
        </div>`,
        iconSize: [28, 28],
        iconAnchor: [14, 28],
        popupAnchor: [0, -30],
      });
      const marker = L.marker([r.latitud, r.longitud], { icon: iconRest })
        .addTo(map)
        .bindPopup(`
          <div style="font-family:'DM Sans',sans-serif;min-width:160px">
            <div style="font-weight:600;font-size:13px;color:#111;margin-bottom:4px">${r.nombre}</div>
            <div style="font-size:12px;color:#888;margin-bottom:2px">⭐ ${r.valoracion}</div>
            <div style="font-size:11px;color:#aaa">${r.direccion}</div>
          </div>
        `);
      markersRef.current.push(marker);
    });
  }

  return (
    <div style={{
      borderRadius: 12, overflow: "hidden",
      border: "1px solid #2a2a2a", marginTop: 12,
    }}>
      <div style={{
        background: "#161616", borderBottom: "1px solid #2a2a2a",
        padding: "8px 14px", fontSize: 11, color: "#666",
        display: "flex", alignItems: "center", gap: 6,
      }}>
        <span style={{ color: "#c8a96e" }}>◎</span>
        {restaurantes && restaurantes.length > 0
          ? `${restaurantes.length} restaurante${restaurantes.length > 1 ? "s" : ""} en el mapa`
          : "Mapa de Madrid"}
      </div>
      <div ref={mapRef} style={{ height: 380, width: "100%" }} />
    </div>
  );
}
