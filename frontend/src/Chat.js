/**
 * Chat.js — Interfaz principal del asistente de restaurantes de Madrid.
 *
 * Estructura del archivo:
 *   1. CONFIGURACIÓN       — URL de la API y constantes
 *   2. UTILIDADES          — Funciones auxiliares (formateo, historial local)
 *   3. COMPONENTES UI      — PlatosColapsables, TarjetaRestaurante, MensajeMarkdown,
 *                            BurbujaMensaje, IndicadorCarga, PanelHistorial
 *   4. MODAL DE DETALLE    — ModalRestaurante (componente extraído del Chat principal)
 *   5. CHAT PRINCIPAL      — Componente Chat con estado, lógica y layout
 */

import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import MapaRestaurantes from "./MapaRestaurantes";

// ═══════════════════════════════════════════════════════════════════════════════
// 1. CONFIGURACIÓN
// ═══════════════════════════════════════════════════════════════════════════════

/** URL base del backend FastAPI desplegado en Render. */
const API_URL = "https://nlp-restaurantes-madrid.onrender.com";

/** Clave para persistir el historial de conversaciones en localStorage. */
const HISTORIAL_KEY = "restaurantes_madrid_historial";

/** Máximo de sesiones guardadas en el historial local. */
const MAX_SESIONES = 50;

// ═══════════════════════════════════════════════════════════════════════════════
// 2. UTILIDADES
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Convierte el rango de precio del backend ("euro euro") al símbolo visual ("€€").
 */
function formatearPrecio(rango) {
  if (!rango) return "";
  const mapa = {
    "euro": "€",
    "euro euro": "€€",
    "euro euro euro": "€€€",
    "euro euro euro euro": "€€€€",
  };
  return mapa[rango.toLowerCase().trim()] || rango;
}

/**
 * Carga el historial de conversaciones guardado en localStorage.
 * Devuelve array vacío si no hay nada o si el JSON está corrupto.
 */
function cargarHistorialGuardado() {
  try { return JSON.parse(localStorage.getItem(HISTORIAL_KEY) || "[]"); }
  catch { return []; }
}

/**
 * Guarda una sesión de conversación al inicio del historial local.
 * Limita el array a MAX_SESIONES entradas para no sobrecargar localStorage.
 */
function guardarSesion(sesion) {
  try {
    const h = cargarHistorialGuardado();
    h.unshift(sesion);
    localStorage.setItem(HISTORIAL_KEY, JSON.stringify(h.slice(0, MAX_SESIONES)));
  } catch (e) {
    console.warn("No se pudo guardar historial:", e);
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// 3. COMPONENTES UI
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Lista colapsable de platos secundarios.
 * Muestra un botón "Otras sugerencias (N)" que expande/colapsa el resto de platos.
 */
function PlatosColapsables({ platos, frecs, renderChip }) {
  const [abierto, setAbierto] = useState(false);
  return (
    <div>
      <button
        onClick={() => setAbierto(v => !v)}
        style={{
          background: "transparent", border: "1px solid #2a2a2a",
          borderRadius: 16, padding: "4px 12px", fontSize: 11,
          color: "#666", cursor: "pointer", marginBottom: abierto ? 8 : 0,
          display: "flex", alignItems: "center", gap: 5,
        }}
      >
        {abierto ? "▲" : "▼"} {abierto ? "Ocultar" : "Otras sugerencias"} ({platos.length})
      </button>
      {abierto && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {platos.map((p, i) => renderChip(p, i, false))}
        </div>
      )}
    </div>
  );
}

/**
 * Tarjeta compacta de restaurante que aparece en el hilo del chat.
 * Al hacer clic abre el modal de detalle con toda la información del restaurante.
 */
function TarjetaRestaurante({ bloque, onVerDetalle, restaurantesData, consulta, abrirModal }) {
  const palabrasZona = [
    "cerca", "estoy", "barrio", "zona", "por",
    "en malasaña", "en chueca", "en lavapiés", "en lavapies", "en salamanca",
    "en retiro", "en sol", "en chamberi", "en chamberí", "en centro",
    "en moncloa", "en tetuan", "en tetuán", "en vallecas", "en carabanchel",
    "en arganzuela", "en latina", "en tetuan",
  ];
  const consultaLower = (consulta || "").toLowerCase();
  const pidioZona = palabrasZona.some(p => consultaLower.includes(p));
  const key     = bloque.nombre.toLowerCase();
  const datos   = restaurantesData && restaurantesData[key];
  const distancia = datos?.distancia_km || bloque.distancia;

  /** Abre el modal con los datos completos del restaurante. */
  const handleClick = () => {
    if (abrirModal) {
      abrirModal(bloque);
    } else if (datos) {
      let platosFrecuencia = {};
      let perfilCliente = {};
      try { platosFrecuencia = datos.platos_frecuencia ? JSON.parse(datos.platos_frecuencia) : {}; } catch (e) {}
      try { perfilCliente = datos.perfil_cliente ? JSON.parse(datos.perfil_cliente) : {}; } catch (e) {}
      onVerDetalle({
        nombre: datos.nombre, valoracion: datos.valoracion, votaciones: datos.votaciones,
        precio: datos.rango_precio, direccion: datos.direccion, resumen: datos.resumen,
        positivos: datos.aspectos_positivos || [], negativos: datos.aspectos_negativos || [],
        platos: datos.platos_destacados || [], platosFrecuencia, perfilCliente,
        consulta: consulta || "", tokens: datos.tokens || [], dato: datos.dato_curioso || "",
        badges: [
          datos.buena_comida && "Buena comida", datos.buen_servicio && "Buen servicio",
          datos.buen_ambiente && "Buen ambiente", datos.espera_corta && "Servicio rápido",
          datos.buena_relacion_precio_calidad && "Buena relación calidad-precio",
          datos.apto_mascotas && "Admite mascotas",
          datos.terraza_exterior && "Terraza exterior", datos.recomendable_en_pareja && "Romántico",
          datos.buenas_vistas && "Buenas vistas", datos.acceso_minusvalidos && "Accesible",
          datos.buen_postre && "Buenos postres",
          datos.buena_relacion_calidad_precio && "Buena relación calidad-precio",
          datos.apto_grupos && "Apto para grupos", datos.opciones_veganas && "Opciones veganas",
          datos.apto_celiaco && "Sin gluten",
        ].filter(Boolean),
        avisos: [
          datos.aviso_espera_larga && "Espera larga",
          datos.aviso_precio_elevado && "Precio elevado",
          datos.aviso_servicio_mejorable && "Servicio mejorable",
        ].filter(Boolean),
        frasesCriterios: datos.frases_criterios || {},
        servicioFrases: datos.servicio_frases || "",
        personalDestacado: datos.personal_destacado || "",
        resenasDestacadas: datos.resenas_destacadas || "",
      });
    }
  };

  return (
    <div style={{
      background: "#1a1a1a", border: "1px solid #2a2a2a",
      borderRadius: 12, padding: "14px 16px", margin: "8px 0",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
        <div style={{ fontFamily: "'DM Serif Display', serif", fontSize: 15, color: "#c8a96e" }}>
          {bloque.nombre}
        </div>
        <div style={{ fontSize: 11, color: "#666", flexShrink: 0, marginLeft: 8 }}>
          {bloque.valoracion && "⭐ " + bloque.valoracion}
          {bloque.precio && " · " + formatearPrecio(bloque.precio)}
        </div>
      </div>
      {pidioZona && distancia && (
        <div style={{ fontSize: 11, color: "#555", marginBottom: 6 }}>📍 {distancia} km</div>
      )}
      <button onClick={handleClick} style={{
        background: "transparent", border: "1px solid #2a2a2a",
        color: "#c8a96e", borderRadius: 16, padding: "5px 14px",
        fontSize: 12, cursor: "pointer", fontFamily: "'DM Sans', sans-serif",
      }}>
        Ver detalles →
      </button>
    </div>
  );
}

/**
 * Renderiza una línea de texto con soporte básico de markdown:
 * convierte **texto** en negrita dorada.
 */
function parsearLinea(linea, idx) {
  const partes = linea.split(/(\*\*[^*]+\*\*)/g);
  return (
    <span key={idx}>
      {partes.map((p, i) =>
        p.startsWith("**") && p.endsWith("**")
          ? <strong key={i} style={{ color: "#c8a96e", fontWeight: 600 }}>{p.slice(2, -2)}</strong>
          : p
      )}
    </span>
  );
}

/**
 * Renderiza texto markdown enriquecido en el hilo del chat:
 * encabezados ##/###, listas con guiones, separadores, emojis especiales y párrafos.
 */
function MensajeMarkdown({ texto }) {
  const lineas = texto.split("\n");
  const elementos = [];
  let i = 0;

  while (i < lineas.length) {
    const linea = lineas[i];

    if (!linea.trim()) {
      elementos.push(<div key={i} style={{ height: 8 }} />);
      i++; continue;
    }
    if (linea.startsWith("### ")) {
      elementos.push(
        <p key={i} style={{ fontFamily: "'DM Serif Display', serif", fontSize: 15, color: "#c8a96e", margin: "14px 0 4px" }}>
          {linea.slice(4)}
        </p>
      );
      i++; continue;
    }
    if (linea.startsWith("## ")) {
      elementos.push(
        <p key={i} style={{ fontFamily: "'DM Serif Display', serif", fontSize: 17, color: "#e8c97e", margin: "16px 0 6px" }}>
          {linea.slice(3)}
        </p>
      );
      i++; continue;
    }
    if (linea.trim() === "---") {
      elementos.push(<hr key={i} style={{ border: "none", borderTop: "1px solid #2a2a2a", margin: "12px 0" }} />);
      i++; continue;
    }
    if (linea.match(/^[-•*]\s/)) {
      const items = [];
      while (i < lineas.length && lineas[i].match(/^[-•*]\s/)) {
        items.push(lineas[i].replace(/^[-•*]\s/, ""));
        i++;
      }
      elementos.push(
        <ul key={`ul-${i}`} style={{ margin: "6px 0", paddingLeft: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 4 }}>
          {items.map((item, j) => (
            <li key={j} style={{ display: "flex", gap: 8, alignItems: "flex-start", fontSize: 13.5, lineHeight: 1.55, color: "#ccc8c0" }}>
              <span style={{ color: "#c8a96e", flexShrink: 0, marginTop: 2 }}>·</span>
              {parsearLinea(item, j)}
            </li>
          ))}
        </ul>
      );
      continue;
    }
    const emojiMatch = linea.match(/^([✅⚠️💡🍽️📍⭐])\s*(.*)/u);
    if (emojiMatch) {
      const colores   = { "✅": "#2d6a4f", "⚠️": "#7a5c1e", "💡": "#1e4f6a" };
      const bgColores = { "✅": "#0d2018", "⚠️": "#1e1608", "💡": "#08151e" };
      const emoji     = emojiMatch[1];
      elementos.push(
        <div key={i} style={{
          background: bgColores[emoji] || "#1a1a1a",
          border: `1px solid ${colores[emoji] || "#333"}22`,
          borderLeft: `3px solid ${colores[emoji] || "#c8a96e"}`,
          borderRadius: "0 8px 8px 0", padding: "8px 12px", margin: "6px 0",
          fontSize: 13.5, lineHeight: 1.55, color: "#ccc8c0",
        }}>
          <span style={{ marginRight: 6 }}>{emoji}</span>
          {parsearLinea(emojiMatch[2], i)}
        </div>
      );
      i++; continue;
    }
    elementos.push(
      <p key={i} style={{ margin: "4px 0", fontSize: 13.5, lineHeight: 1.6, color: "#ccc8c0" }}>
        {parsearLinea(linea, i)}
      </p>
    );
    i++;
  }
  return <div>{elementos}</div>;
}

/**
 * Parsea la respuesta de texto del backend y construye tarjetas de restaurante
 * detectando bloques con formato **Nombre**, seguidos de valoración, precio y distancia.
 * Si no hay bloques parseables, usa el fallback de restaurantesDelMensaje.
 */
function MensajeCompacto({ texto, onVerDetalle, restaurantesData, consulta, restaurantesDelMensaje }) {
  const lineas  = texto.split("\n");
  const bloques = [];
  let intro   = [];
  let current = null;

  for (const linea of lineas) {
    const lineaLimpia   = linea.replace(/^[\s·\-*•]+/, "").trim();
    const esNombrePuro  = lineaLimpia.match(/^#{1,3}\s+(.+)/) || (lineaLimpia.startsWith("**") && lineaLimpia.endsWith("**") && lineaLimpia.length < 60);
    const esNombreConDatos = !esNombrePuro && lineaLimpia.match(/^\*\*(.+?)\*\*[,\s]/);

    if (esNombrePuro || esNombreConDatos) {
      if (current) bloques.push(current);
      let nombre = "";
      if (esNombrePuro) {
        nombre = lineaLimpia.replace(/^#+\s+/, "").replace(/\*\*/g, "").trim();
      } else {
        nombre = esNombreConDatos[1].trim();
      }
      const ultimaIntro = intro.length > 0 ? intro[intro.length - 1] : "";
      const dIntro = ultimaIntro.match(/([\d]+[.,][\d]+)\s*km/i);
      current = { nombre, lineas: [], valoracion: "", precio: "", distancia: dIntro ? dIntro[1] : "" };
      const vInline = lineaLimpia.match(/Valoraci[oó]n[^\d]*([\d.]+)/i);
      const pInline = lineaLimpia.match(/Rango[^:]*:\s*(€+)/i) || lineaLimpia.match(/(€+)/);
      const dInline = lineaLimpia.match(/([\d]+[.,][\d]+)\s*km/);
      if (vInline) current.valoracion = vInline[1];
      if (pInline) current.precio = pInline[1];
      if (dInline) current.distancia = dInline[1];
    } else if (current) {
      current.lineas.push(linea);
      const vMatch = linea.match(/Valoraci[oó]n[^\d]*([\d.]+)/i) || linea.match(/⭐\s*([\d.]+)/);
      const pMatch = linea.match(/Rango[^:]*:\s*(€+)/i) || linea.match(/precio[^:]*:\s*(€+)/i);
      const dMatch = linea.match(/([\d]+[.,][\d]+)\s*km/i);
      if (vMatch && !current.valoracion) current.valoracion = vMatch[1];
      if (pMatch && !current.precio) current.precio = pMatch[1];
      if (dMatch && !current.distancia) current.distancia = dMatch[1];
    } else {
      intro.push(linea);
    }
  }
  if (current) bloques.push(current);

  // Fallback: usar directamente los datos estructurados del mensaje
  if (bloques.length === 0 && restaurantesDelMensaje && restaurantesDelMensaje.length > 0) {
    const introTextoFallback = texto.split("\n").slice(0, 2).filter(l => l.trim() && !l.includes("**")).join(" ").trim();
    return (
      <div>
        {introTextoFallback && (
          <p style={{ fontSize: 13.5, color: "#ccc", lineHeight: 1.6, marginBottom: 14 }}>{introTextoFallback}</p>
        )}
        {restaurantesDelMensaje.map((datos, i) => {
          const bloqueSintetico = { nombre: datos.nombre, valoracion: datos.valoracion, precio: datos.rango_precio, distancia: datos.distancia_km, lineas: [] };
          return <TarjetaRestaurante key={i} bloque={bloqueSintetico} onVerDetalle={onVerDetalle} restaurantesData={restaurantesData} consulta={consulta} />;
        })}
      </div>
    );
  }

  if (bloques.length === 0) return <MensajeMarkdown texto={texto} />;

  const introTexto = intro.filter(l => l.trim()).join(" ").trim();

  /** Construye el objeto de detalle y abre el modal para un bloque dado. */
  const abrirModal = (bloque) => {
    const key   = bloque.nombre.toLowerCase();
    const datos = restaurantesData && restaurantesData[key];
    if (datos) {
      let platosFrecuencia = {};
      let perfilCliente = {};
      try { platosFrecuencia = datos.platos_frecuencia ? (typeof datos.platos_frecuencia === "string" ? JSON.parse(datos.platos_frecuencia) : datos.platos_frecuencia) : {}; } catch (e) {}
      try { perfilCliente = datos.perfil_cliente ? (typeof datos.perfil_cliente === "string" ? JSON.parse(datos.perfil_cliente) : datos.perfil_cliente) : {}; } catch (e) {}
      onVerDetalle({
        nombre: datos.nombre, valoracion: datos.valoracion, votaciones: datos.votaciones,
        precio: datos.rango_precio, direccion: datos.direccion, resumen: datos.resumen,
        positivos: datos.aspectos_positivos || [], negativos: datos.aspectos_negativos || [],
        platos: datos.platos_destacados || [], platosFrecuencia, perfilCliente,
        consulta: consulta || "", tokens: datos.tokens || [], dato: datos.dato_curioso || "",
        badges: [
          datos.buena_comida && "Buena comida", datos.buen_servicio && "Buen servicio",
          datos.buen_ambiente && "Buen ambiente", datos.espera_corta && "Servicio rápido",
          datos.buena_relacion_precio_calidad && "Buena relación calidad-precio",
          datos.apto_mascotas && "Admite mascotas", datos.terraza_exterior && "Terraza exterior",
          datos.recomendable_en_pareja && "Romántico", datos.buenas_vistas && "Buenas vistas",
          datos.acceso_minusvalidos && "Accesible", datos.buen_postre && "Buenos postres",
          datos.buena_relacion_calidad_precio && "Buena relación calidad-precio",
          datos.apto_grupos && "Apto para grupos", datos.opciones_veganas && "Opciones veganas",
          datos.apto_celiaco && "Sin gluten",
        ].filter(Boolean),
        avisos: [
          datos.aviso_espera_larga && "Espera larga",
          datos.aviso_precio_elevado && "Precio elevado",
          datos.aviso_servicio_mejorable && "Servicio mejorable",
        ].filter(Boolean),
        frasesCriterios: datos.frases_criterios || {},
        servicioFrases: datos.servicio_frases || "",
        personalDestacado: datos.personal_destacado || "",
        resenasDestacadas: datos.resenas_destacadas || "",
      });
    } else {
      const resumenLinea = bloque.lineas.find(l => l.length > 40 && !l.startsWith("#") && !l.toLowerCase().includes("valoraci"));
      onVerDetalle({ nombre: bloque.nombre, valoracion: bloque.valoracion, precio: bloque.precio, resumen: resumenLinea || "", positivos: [], negativos: [], platos: [], dato: "", badges: [] });
    }
  };

  return (
    <div>
      {introTexto && (
        <p style={{ fontSize: 13.5, color: "#ccc", marginBottom: 12, lineHeight: 1.6 }}>{introTexto}</p>
      )}
      {bloques.map((bloque, i) => (
        <TarjetaRestaurante key={i} bloque={bloque} onVerDetalle={onVerDetalle} restaurantesData={restaurantesData} consulta={consulta} abrirModal={abrirModal} />
      ))}
    </div>
  );
}

/**
 * Burbuja de mensaje del hilo del chat.
 * Los mensajes del asistente usan MensajeCompacto para parsear restaurantes.
 * Los mensajes del usuario se muestran en texto simple.
 */
function BurbujaMensaje({ mensaje, onVerDetalle, restaurantesData, consulta, restaurantesDelMensaje }) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 40);
    return () => clearTimeout(t);
  }, []);

  const esUsuario = mensaje.rol === "usuario";
  return (
    <div style={{
      display: "flex", alignItems: "flex-start", gap: 10,
      maxWidth: esUsuario ? "88%" : "96%",
      alignSelf: esUsuario ? "flex-end" : "flex-start",
      flexDirection: esUsuario ? "row-reverse" : "row",
      opacity: visible ? 1 : 0,
      transform: visible ? "translateY(0)" : "translateY(8px)",
      transition: "opacity 0.25s ease, transform 0.25s ease",
    }}>
      {!esUsuario && (
        <div style={{
          width: 30, height: 30, borderRadius: "50%",
          background: "#1e1e1e", border: "1px solid #2a2a2a",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 15, flexShrink: 0, marginTop: 2,
        }}>🤖</div>
      )}
      <div style={{
        padding: esUsuario ? "10px 16px" : "14px 16px",
        borderRadius: esUsuario ? "16px 4px 16px 16px" : "4px 16px 16px 16px",
        background: esUsuario ? "#c8a96e" : "#161616",
        color: esUsuario ? "#111" : "#e8e4dc",
        border: esUsuario ? "none" : "1px solid #272727",
        fontSize: 14, lineHeight: 1.6,
        maxWidth: "100%", width: esUsuario ? "auto" : "100%",
      }}>
        {esUsuario
          ? <span style={{ fontWeight: 500 }}>{mensaje.texto}</span>
          : <MensajeCompacto texto={mensaje.texto} onVerDetalle={onVerDetalle} restaurantesData={restaurantesData} consulta={consulta} restaurantesDelMensaje={restaurantesDelMensaje} />
        }
      </div>
    </div>
  );
}

/**
 * Indicador animado de tres puntos que se muestra mientras el backend responde.
 */
function IndicadorCarga() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, alignSelf: "flex-start" }}>
      <div style={{
        width: 30, height: 30, borderRadius: "50%",
        background: "#1e1e1e", border: "1px solid #2a2a2a",
        display: "flex", alignItems: "center", justifyContent: "center", fontSize: 15,
      }}>🤖</div>
      <div style={{
        background: "#161616", border: "1px solid #272727",
        borderRadius: "4px 16px 16px 16px", padding: "14px 18px",
        display: "flex", alignItems: "center", gap: 10,
      }}>
        <div style={{ display: "flex", gap: 5 }}>
          {[0, 0.18, 0.36].map((delay, i) => (
            <span key={i} style={{
              width: 6, height: 6, borderRadius: "50%", background: "#c8a96e",
              display: "inline-block",
              animation: `bounce 1.1s ${delay}s infinite ease-in-out`,
            }} />
          ))}
        </div>
        <span style={{ fontSize: 12, color: "#555", fontStyle: "italic" }}>Consultando restaurantes...</span>
      </div>
    </div>
  );
}

/**
 * Panel lateral con el historial de conversaciones guardadas en localStorage.
 * Permite cargar una sesión anterior o borrar todo el historial.
 */
function PanelHistorial({ onCerrar, onCargarSesion }) {
  const sesiones = cargarHistorialGuardado();

  const limpiarTodo = () => {
    if (window.confirm("¿Borrar todo el historial?")) {
      localStorage.removeItem(HISTORIAL_KEY);
      onCerrar();
    }
  };

  return (
    <div style={{
      position: "fixed", inset: 0, background: "#000000cc",
      zIndex: 100, display: "flex", justifyContent: "flex-end",
    }} onClick={onCerrar}>
      <div style={{
        width: 340, height: "100%", background: "#0f0f0f",
        borderLeft: "1px solid #2a2a2a", overflowY: "auto",
        padding: "20px 16px", display: "flex", flexDirection: "column", gap: 12,
      }} onClick={e => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
          <span style={{ fontFamily: "'DM Serif Display', serif", fontSize: 17, color: "#f0ece4" }}>Historial</span>
          <div style={{ display: "flex", gap: 8 }}>
            {sesiones.length > 0 && (
              <button onClick={limpiarTodo} style={{
                background: "transparent", border: "1px solid #3a2a2a",
                color: "#666", borderRadius: 12, padding: "4px 10px", fontSize: 11, cursor: "pointer",
              }}>Borrar todo</button>
            )}
            <button onClick={onCerrar} style={{
              background: "transparent", border: "1px solid #2a2a2a",
              color: "#666", borderRadius: 12, padding: "4px 10px", fontSize: 11, cursor: "pointer",
            }}>✕</button>
          </div>
        </div>
        {sesiones.length === 0 ? (
          <div style={{ color: "#444", fontSize: 13, marginTop: 20, textAlign: "center" }}>
            Aún no hay conversaciones guardadas
          </div>
        ) : sesiones.map((sesion, i) => (
          <div key={i} onClick={() => onCargarSesion(sesion)} style={{
            background: "#161616", border: "1px solid #2a2a2a",
            borderRadius: 10, padding: "12px 14px", cursor: "pointer",
          }}
            onMouseEnter={e => e.currentTarget.style.borderColor = "#c8a96e44"}
            onMouseLeave={e => e.currentTarget.style.borderColor = "#2a2a2a"}
          >
            <div style={{ fontSize: 11, color: "#444", marginBottom: 6 }}>
              {new Date(sesion.fecha).toLocaleString("es-ES", {
                day: "2-digit", month: "2-digit", year: "numeric",
                hour: "2-digit", minute: "2-digit",
              })}
              <span style={{ marginLeft: 8, color: "#333" }}>· {sesion.turnos} pregunta{sesion.turnos !== 1 ? "s" : ""}</span>
            </div>
            {sesion.preguntas.map((p, j) => (
              <div key={j} style={{
                fontSize: 12, color: "#888", marginBottom: 3,
                whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
              }}>
                <span style={{ color: "#c8a96e55", marginRight: 5 }}>→</span>{p}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// 4. MODAL DE DETALLE
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Keywords que deben aparecer en las frases justificativas de cada criterio.
 * Si ningún trozo de la frase las contiene, no se muestra esa sección.
 * Evita mostrar frases irrelevantes asignadas erróneamente por el pipeline.
 */
const KEYWORDS_CRITERIO = {
  mascotas:           ["perro","mascota","peludo","admiten","dog","pet","can","animal"],
  terraza:            ["terraza","exterior","aire libre","patio","velador","fuera"],
  vistas:             ["vista","panorámica","azotea","rooftop","mirador","horizonte"],
  musica_directo:     ["música","directo","concierto","actuación","jazz","flamenco","en vivo","banda"],
  romantico:          ["romántico","íntimo","intimo","romantico","pareja","velas","cena romántica","amor"],
  buen_postre:        ["postre","tarta","helado","tiramisú","tiramisu","mousse","brownie","coulant","flan"],
  precio_calidad:     ["precio","calidad","económico","asequible","relación","barato","razonable"],
  grupos_grandes:     ["grupo","celebración","cumpleaños","empresa","evento","varios","reserva"],
  vegano_vegetariano: ["vegano","vegana","vegetariano","vegetariana","sin carne","plant","verdura"],
  sin_gluten:         ["gluten","celiaco","celiaca","celíaco","sin gluten"],
};

/** Etiquetas visuales para cada criterio en el modal. */
const ETIQUETAS_CRITERIO = {
  mascotas:           "🐾 Admite mascotas",
  terraza:            "☀️ Terraza",
  vistas:             "🏙️ Vistas",
  romantico:          "🕯️ Romántico",
  musica_directo:     "🎵 Música en directo",
  buen_postre:        "🍮 Buenos postres",
  precio_calidad:     "💶 Buena relación calidad-precio",
  grupos_grandes:     "🎉 Grupos y celebraciones",
  vegano_vegetariano: "🌿 Opciones veganas",
  sin_gluten:         "🌾 Sin gluten",
};

/**
 * Modal de detalle de un restaurante.
 * Muestra: nombre, valoración, dirección, badges de criterios, resumen,
 * frases de clientes por criterio, platos destacados con frecuencia y
 * aspectos negativos a tener en cuenta.
 */
function ModalRestaurante({ restaurante, onCerrar }) {
  if (!restaurante) return null;

  // Frases de criterios: filtrar las que no tienen keywords relevantes
  const frases = restaurante.frasesCriterios || {};
  const entradasFrases = Object.entries(frases).filter(([k, v]) => {
    if (k === "ninos") return false;
    if (!v || !v.trim() || ["nan", "none", ""].includes(v.trim().toLowerCase())) return false;
    const keywords = KEYWORDS_CRITERIO[k];
    if (!keywords) return true;
    // Exigir que al menos un trozo contenga una keyword real
    return v.toLowerCase().split("|").some(trozo => keywords.some(kw => trozo.includes(kw)));
  });

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 1000,
      background: "rgba(0,0,0,0.75)", backdropFilter: "blur(4px)",
      display: "flex", alignItems: "center", justifyContent: "center", padding: 16,
    }} onClick={onCerrar}>
      <div style={{
        background: "#161616", border: "1px solid #2a2a2a",
        borderRadius: 16, padding: 24, maxWidth: 480, width: "100%",
        maxHeight: "80vh", overflowY: "auto",
        boxShadow: "0 20px 60px rgba(0,0,0,0.6)",
      }} onClick={e => e.stopPropagation()}>

        {/* Cabecera: nombre, valoración, dirección */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontFamily: "'DM Serif Display', serif", fontSize: 20, color: "#f0ece4", marginBottom: 4 }}>
              {restaurante.nombre}
            </div>
            <div style={{ fontSize: 12, color: "#666", display: "flex", gap: 10, flexWrap: "wrap" }}>
              {restaurante.valoracion > 0 && (
                <span>⭐ {restaurante.valoracion}{restaurante.votaciones > 0 && ` (${restaurante.votaciones} votos)`}</span>
              )}
              {restaurante.precio && <span>{formatearPrecio(restaurante.precio)}</span>}
            </div>
            {restaurante.direccion && (
              <div style={{ fontSize: 11, color: "#444", marginTop: 3 }}>📍 {restaurante.direccion}</div>
            )}
          </div>
          <button onClick={onCerrar} style={{
            background: "transparent", border: "none", color: "#555",
            fontSize: 20, cursor: "pointer", padding: "0 4px", flexShrink: 0,
          }}>✕</button>
        </div>

        {/* Badges de criterios positivos */}
        {restaurante.badges && restaurante.badges.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 8 }}>
            {restaurante.badges.map((b, i) => (
              <span key={i} style={{
                background: "#0d1f12", border: "1px solid #1a3a20",
                borderRadius: 12, padding: "3px 10px", fontSize: 11, color: "#4caf82",
              }}>✓ {b}</span>
            ))}
          </div>
        )}

        {/* Avisos negativos */}
        {restaurante.avisos && restaurante.avisos.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 14 }}>
            {restaurante.avisos.map((a, i) => (
              <span key={i} style={{
                background: "#1f0d0d", border: "1px solid #3a1a1a",
                borderRadius: 12, padding: "3px 10px", fontSize: 11, color: "#e05555",
              }}>⚠ {a}</span>
            ))}
          </div>
        )}

        {/* Resumen NLP */}
        {restaurante.resumen && (
          <p style={{ fontSize: 13.5, color: "#ccc", lineHeight: 1.65, marginBottom: 14, fontStyle: "italic" }}>
            "{restaurante.resumen}"
          </p>
        )}

        {/* Lo que dicen los clientes — frases reales filtradas por keyword */}
        {entradasFrases.length > 0 && (
          <div style={{ marginBottom: 14 }}>
            <div style={{
              fontSize: 11, color: "#c8a96e", fontWeight: 600,
              letterSpacing: "1px", textTransform: "uppercase", marginBottom: 10,
            }}>
              Lo que dicen los clientes
            </div>
            {entradasFrases.map(([criterio, texto]) => (
              <div key={criterio} style={{
                marginBottom: 8, background: "#111", borderRadius: 8,
                padding: "8px 12px", borderLeft: "2px solid #1a3a20",
              }}>
                <div style={{ fontSize: 11, color: "#4caf82", fontWeight: 600, marginBottom: 4 }}>
                  {ETIQUETAS_CRITERIO[criterio] || criterio}
                </div>
                {texto.split("|")
                  .filter(frase => {
                    const keywords = KEYWORDS_CRITERIO[criterio];
                    if (!keywords) return true;
                    return keywords.some(kw => frase.toLowerCase().includes(kw));
                  })
                  .slice(0, 2)
                  .map((frase, i) => (
                    <div key={i} style={{ fontSize: 12, color: "#888", fontStyle: "italic", lineHeight: 1.5 }}>
                      "{frase.trim().substring(0, 120)}"
                    </div>
                  ))}
              </div>
            ))}
          </div>
        )}

        {/* Platos destacados con frecuencia de mención */}
        {restaurante.platos && restaurante.platos.length > 0 && (() => {
          const frecs = restaurante.platosFrecuencia || {};
          const stopwords = ["quiero","comer","busco","estoy","en","cerca","de","un","una","los","las","donde","puedo","hay","con","para","que","me","ir","a","restaurante","haya","buen","buena","buenos"];
          const palabrasConsulta = (restaurante.tokens && restaurante.tokens.length > 0)
            ? restaurante.tokens.map(t => t.toLowerCase())
            : (restaurante.consulta || "").toLowerCase().split(/\s+/).filter(p => p.length > 3 && !stopwords.includes(p));

          const platosOrdenados = [...restaurante.platos].sort((a, b) => {
            const aEsBuscado = palabrasConsulta.some(p => a.toLowerCase().includes(p));
            const bEsBuscado = palabrasConsulta.some(p => b.toLowerCase().includes(p));
            if (aEsBuscado && !bEsBuscado) return -1;
            if (!aEsBuscado && bEsBuscado) return 1;
            const keyA = Object.keys(frecs).find(k => k.toLowerCase().includes(a.toLowerCase()) || a.toLowerCase().includes(k.toLowerCase()));
            const keyB = Object.keys(frecs).find(k => k.toLowerCase().includes(b.toLowerCase()) || b.toLowerCase().includes(k.toLowerCase()));
            return (frecs[keyB] || 0) - (frecs[keyA] || 0);
          });

          const platosBuscados = platosOrdenados.filter(p => palabrasConsulta.some(w => p.toLowerCase().includes(w)));
          const platosResto    = platosOrdenados.filter(p => !palabrasConsulta.some(w => p.toLowerCase().includes(w)));
          const hayBuscados    = platosBuscados.length > 0;

          /** Renderiza un chip de plato con su frecuencia de mención. */
          const renderChip = (p, i, destacado) => {
            const key = Object.keys(frecs).find(k => k.toLowerCase().includes(p.toLowerCase()) || p.toLowerCase().includes(k.toLowerCase()));
            const n   = key ? frecs[key] : null;
            return (
              <span key={i} style={{
                background: destacado ? "#2a1f00" : "#111",
                border: destacado ? "1px solid #c8a96e88" : "1px solid #2a2a2a",
                borderRadius: 10, padding: "4px 12px",
                fontSize: destacado ? 13 : 12,
                color: destacado ? "#c8a96e" : "#888",
                fontWeight: destacado ? 500 : 400,
              }}>
                {p}
                {n ? <span style={{ color: destacado ? "#c8a96eaa" : "#c8a96e55", fontSize: 11, marginLeft: 4 }}>({n}/90 reseñas)</span> : null}
              </span>
            );
          };

          return (
            <div style={{ background: "#1a1505", borderLeft: "3px solid #c8a96e44", borderRadius: "0 8px 8px 0", padding: "10px 14px", marginBottom: 10 }}>
              {hayBuscados ? (
                <>
                  <div style={{ fontSize: 12, color: "#c8a96e", fontWeight: 500, marginBottom: 8 }}>🍽 Plato buscado</div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: platosResto.length > 0 ? 10 : 0 }}>
                    {platosBuscados.map((p, i) => renderChip(p, i, true))}
                  </div>
                  {platosResto.length > 0 && <PlatosColapsables platos={platosResto} frecs={frecs} renderChip={renderChip} />}
                </>
              ) : (
                <>
                  <div style={{ fontSize: 12, color: "#c8a96e", fontWeight: 500, marginBottom: 6 }}>🍽 Platos recomendados</div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {platosOrdenados.map((p, i) => renderChip(p, i, false))}
                  </div>
                </>
              )}
            </div>
          );
        })()}

        {/* Aspectos negativos a tener en cuenta */}
        {restaurante.negativos && restaurante.negativos.length > 0 && (
          <div style={{ background: "#1e1608", borderLeft: "3px solid #7a5c1e", borderRadius: "0 8px 8px 0", padding: "10px 14px", marginBottom: 10 }}>
            <div style={{ fontSize: 12, color: "#c8963e", fontWeight: 500, marginBottom: 6 }}>⚠️ A tener en cuenta</div>
            {restaurante.negativos.map((n, i) => (
              <div key={i} style={{ fontSize: 13, color: "#aaa", marginBottom: 3 }}>· {n}</div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// 5. CHAT PRINCIPAL
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Componente principal de la aplicación de chat.
 * Gestiona el estado global: mensajes, historial API, mapa, modal de detalle
 * e historial persistente. Orquesta la comunicación con el backend FastAPI.
 */
export default function Chat() {
  const navigate = useNavigate();

  // Estado del chat
  const [mensajes, setMensajes] = useState([{
    rol: "asistente",
    texto: "¡Hola! Soy tu asistente de restaurantes en Madrid.\n¿Qué tipo de restaurante estás buscando hoy?",
  }]);
  const [historial, setHistorial]             = useState([]);  // historial para el API (context window)
  const [input, setInput]                     = useState("");
  const [cargando, setCargando]               = useState(false);
  const [inputFocus, setInputFocus]           = useState(false);

  // Estado del mapa
  const [mapaRestaurantes, setMapaRestaurantes] = useState([]);
  const [mostrarMapa, setMostrarMapa]           = useState(false);

  // Estado del modal y datos de restaurantes
  const [modalRestaurante, setModalRestaurante]   = useState(null);
  const [restaurantesData, setRestaurantesData]   = useState({});

  // Panel de historial de sesiones
  const [mostrarHistorial, setMostrarHistorial] = useState(false);

  // Refs
  const bottomRef            = useRef(null);
  const inputRef             = useRef(null);
  const preguntasSesionRef   = useRef([]);

  // Auto-scroll al fondo cuando llega un mensaje nuevo
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [mensajes, cargando]);

  // Procesar consulta inicial pasada desde la Landing page
  const consultaInicial = sessionStorage.getItem("consulta_inicial") || "";
  useEffect(() => {
    if (consultaInicial) {
      sessionStorage.removeItem("consulta_inicial");
      enviar(consultaInicial);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * Envía una consulta al backend y procesa la respuesta.
   * Actualiza mensajes, historial API, datos del mapa y persiste la sesión.
   */
  const enviar = async (texto) => {
    const consulta = (texto || input).trim();
    if (!consulta || cargando) return;
    setInput("");
    preguntasSesionRef.current.push(consulta);
    setMensajes(prev => [...prev, { rol: "usuario", texto: consulta }]);
    setCargando(true);
    try {
      const res = await fetch(`${API_URL}/recomendar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ consulta, historial }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Error ${res.status}`);
      }
      const data = await res.json();
      const respuesta     = data.respuesta || "Sin respuesta del servidor.";
      const consultaActual = data.consulta_usuario || consulta;

      // Actualizar historial para el contexto del API
      setHistorial(prev => [
        ...prev,
        { role: "user", content: consulta },
        { role: "assistant", content: respuesta },
      ]);

      // Persistir sesión en localStorage
      guardarSesion({
        fecha:         new Date().toISOString(),
        turnos:        preguntasSesionRef.current.length,
        preguntas:     [...preguntasSesionRef.current],
        conversacion:  [...historial, { role: "user", content: consulta }, { role: "assistant", content: respuesta }],
      });

      // Añadir mensaje al hilo del chat
      setMensajes(prev => [...prev, { rol: "asistente", texto: respuesta, consulta: consultaActual, restaurantes: data.restaurantes || [] }]);

      // Actualizar mapa y datos de restaurantes si hay resultados
      if (data.restaurantes && data.restaurantes.length > 0) {
        setMapaRestaurantes(data.restaurantes);
        const nuevo = {};
        data.restaurantes.forEach(r => { nuevo[r.nombre.toLowerCase()] = r; });
        setRestaurantesData(nuevo);
      }
    } catch (e) {
      setMensajes(prev => [...prev, {
        rol: "asistente",
        texto: `⚠️ ${e.message || "Error conectando con el servidor. Inténtalo de nuevo."}`,
      }]);
    } finally {
      setCargando(false);
      inputRef.current?.focus();
    }
  };

  /** Reinicia la conversación a su estado inicial. */
  const nuevaBusqueda = () => {
    setMensajes([{ rol: "asistente", texto: "¡Hola! ¿Qué tipo de restaurante estás buscando hoy?" }]);
    setHistorial([]);
    setMapaRestaurantes([]);
    setMostrarMapa(false);
    preguntasSesionRef.current = [];
  };

  const hayConversacion = mensajes.length > 1;

  return (
    <div style={s.root}>
      {/* Header con navegación y controles */}
      <header style={s.header}>
        <div style={s.headerInner}>
          <div style={s.logoWrap}><span style={{ fontSize: 26 }}>🍽</span></div>
          <div>
            <div style={s.titulo}>Restaurantes Madrid</div>
            <div style={s.subtitulo}>NLP · nlptown · análisis local</div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button style={s.btnNuevo} onClick={() => navigate("/")}>← Inicio</button>
          {mapaRestaurantes.length > 0 && (
            <button
              style={{ ...s.btnNuevo, borderColor: mostrarMapa ? "#c8a96e" : "#2a2a2a", color: mostrarMapa ? "#c8a96e" : "#666" }}
              onClick={() => setMostrarMapa(m => !m)}
            >
              {mostrarMapa ? "Ocultar mapa" : "Ver mapa"}
            </button>
          )}
          {hayConversacion && (
            <button style={s.btnNuevo} onClick={nuevaBusqueda}>Nueva búsqueda</button>
          )}
          <button style={s.btnNuevo} onClick={() => setMostrarHistorial(true)}>Historial</button>
        </div>
      </header>

      {/* Hilo del chat */}
      <main style={s.chat}>
        {mensajes.map((m, i) => (
          <BurbujaMensaje
            key={i} mensaje={m} index={i}
            onVerDetalle={setModalRestaurante}
            restaurantesData={restaurantesData}
            consulta={m.consulta || ""}
            restaurantesDelMensaje={m.restaurantes || []}
          />
        ))}
        {cargando && <IndicadorCarga />}
        <div ref={bottomRef} />
      </main>

      {/* Mapa de restaurantes (toggle) */}
      {mostrarMapa && mapaRestaurantes.length > 0 && (
        <div style={{ padding: "0 16px 8px", background: "#0f0f0f" }}>
          <MapaRestaurantes restaurantes={mapaRestaurantes} />
        </div>
      )}

      {/* Input de texto */}
      <footer style={s.footer}>
        <div style={{
          ...s.inputWrap,
          border: inputFocus ? "1px solid #c8a96e55" : "1px solid #272727",
          boxShadow: inputFocus ? "0 0 0 3px #c8a96e11" : "none",
          transition: "border 0.2s, box-shadow 0.2s",
        }}>
          <input
            ref={inputRef} style={s.input} value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === "Enter" && !e.shiftKey && enviar()}
            onFocus={() => setInputFocus(true)}
            onBlur={() => setInputFocus(false)}
            placeholder="¿Qué tipo de restaurante buscas?"
            disabled={cargando} maxLength={300}
          />
          {input.length > 200 && (
            <span style={{ fontSize: 11, color: input.length > 280 ? "#c8a96e" : "#444", flexShrink: 0, marginRight: 4 }}>
              {300 - input.length}
            </span>
          )}
          <button
            style={{ ...s.boton, opacity: cargando || !input.trim() ? 0.35 : 1, transition: "opacity 0.2s" }}
            onClick={() => enviar()} disabled={cargando || !input.trim()} aria-label="Enviar"
          >➤</button>
        </div>
        <p style={s.hint}>Puedes preguntar por cocina, ambiente, platos, barrio o nombre del restaurante</p>
      </footer>

      {/* Modal de detalle del restaurante */}
      <ModalRestaurante restaurante={modalRestaurante} onCerrar={() => setModalRestaurante(null)} />

      {/* Panel lateral de historial de sesiones */}
      {mostrarHistorial && (
        <PanelHistorial
          onCerrar={() => setMostrarHistorial(false)}
          onCargarSesion={(sesion) => {
            setMensajes([
              { rol: "asistente", texto: "¡Hola! Soy tu asistente de restaurantes en Madrid.\n¿Qué tipo de restaurante estás buscando hoy?" },
              ...sesion.conversacion.map(m => ({
                rol: m.role === "user" ? "usuario" : "asistente",
                texto: m.content,
              }))
            ]);
            setHistorial(sesion.conversacion);
            preguntasSesionRef.current = [...sesion.preguntas];
            setMostrarHistorial(false);
          }}
        />
      )}

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:ital,wght@0,400;0,500;1,400&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #0c0c0c; font-family: 'DM Sans', sans-serif; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #2a2a2a; border-radius: 4px; }
        @keyframes bounce {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.5; }
          40% { transform: translateY(-5px); opacity: 1; }
        }
      `}</style>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// ESTILOS
// ═══════════════════════════════════════════════════════════════════════════════

const s = {
  root:       { display: "flex", flexDirection: "column", height: "100vh", maxWidth: 700, margin: "0 auto", background: "#0f0f0f", color: "#f0ece4" },
  header:     { padding: "14px 20px", borderBottom: "1px solid #1e1e1e", background: "#0f0f0f", position: "sticky", top: 0, zIndex: 10, display: "flex", alignItems: "center", justifyContent: "space-between" },
  headerInner:{ display: "flex", alignItems: "center", gap: 12 },
  logoWrap:   { width: 42, height: 42, borderRadius: 10, background: "#1a1505", border: "1px solid #c8a96e22", display: "flex", alignItems: "center", justifyContent: "center" },
  titulo:     { fontFamily: "'DM Serif Display', serif", fontSize: 18, color: "#f0ece4", letterSpacing: "-0.3px" },
  subtitulo:  { fontSize: 10, color: "#444", letterSpacing: "0.8px", textTransform: "uppercase", marginTop: 2 },
  btnNuevo:   { background: "transparent", border: "1px solid #2a2a2a", color: "#666", borderRadius: 20, padding: "5px 14px", fontSize: 12, cursor: "pointer" },
  chat:       { flex: 1, overflowY: "auto", padding: "20px 16px", display: "flex", flexDirection: "column", gap: 14 },
  footer:     { padding: "10px 16px 16px", borderTop: "1px solid #1e1e1e", background: "#0f0f0f" },
  inputWrap:  { display: "flex", gap: 8, alignItems: "center", background: "#161616", borderRadius: 28, padding: "4px 4px 4px 16px" },
  input:      { flex: 1, background: "transparent", border: "none", color: "#f0ece4", fontSize: 14, outline: "none", padding: "8px 0", fontFamily: "'DM Sans', sans-serif" },
  boton:      { background: "#c8a96e", border: "none", borderRadius: "50%", width: 38, height: 38, fontSize: 14, cursor: "pointer", color: "#111", fontWeight: "bold", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center" },
  hint:       { fontSize: 11, color: "#333", textAlign: "center", marginTop: 8, letterSpacing: "0.2px" },
};
