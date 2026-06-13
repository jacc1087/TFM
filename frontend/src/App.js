import { useState, useRef, useEffect } from "react";

const API_URL = "https://web-production-26d535.up.railway.app";

const sugerencias = [
  "Quiero un restaurante peruano",
  "Busco algo romántico para una cena especial",
  "¿Dónde puedo comer croquetas?",
  "Necesito un sitio apto para niños",
  "El más recomendado por los clientes",
  "Algo con buena relación calidad-precio",
];

export default function App() {
  const [mensajes, setMensajes] = useState([
    {
      rol: "asistente",
      texto: "¡Hola! Soy tu asistente de restaurantes en Madrid. ¿Qué tipo de restaurante estás buscando?",
    },
  ]);
  const [historial, setHistorial] = useState([]);
  const [input, setInput] = useState("");
  const [cargando, setCargando] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [mensajes, cargando]);

  const enviar = async (texto) => {
    const consulta = texto || input.trim();
    if (!consulta || cargando) return;
    setInput("");
    setMensajes((prev) => [...prev, { rol: "usuario", texto: consulta }]);
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
      const respuesta = data.respuesta || "Sin respuesta del servidor.";

      setHistorial((prev) => [
        ...prev,
        { role: "user", content: consulta },
        { role: "assistant", content: respuesta },
      ]);

      setMensajes((prev) => [
        ...prev,
        { rol: "asistente", texto: respuesta },
      ]);
    } catch (e) {
      setMensajes((prev) => [
        ...prev,
        {
          rol: "asistente",
          texto: `⚠️ ${e.message || "Error conectando con el servidor. Inténtalo de nuevo."}`,
        },
      ]);
    } finally {
      setCargando(false);
    }
  };

  return (
    <div style={styles.root}>
      {/* Header */}
      <header style={styles.header}>
        <div style={styles.headerInner}>
          <span style={styles.logo}>🍽</span>
          <div>
            <div style={styles.titulo}>Restaurantes Madrid</div>
            <div style={styles.subtitulo}>Powered by Gemini · ChromaDB · RAG</div>
          </div>
        </div>
      </header>

      {/* Chat */}
      <main style={styles.chat}>
        {mensajes.map((m, i) => (
          <div key={i} style={{ ...styles.burbuja, ...(m.rol === "usuario" ? styles.burbujaUsuario : styles.burbujaAsistente) }}>
            {m.rol === "asistente" && <span style={styles.avatar}>🤖</span>}
            <div style={{ ...styles.texto, ...(m.rol === "usuario" ? styles.textoUsuario : styles.textoAsistente) }}>
              {m.texto.split("\n").map((linea, j) => (
                <span key={j}>
                  {linea.replace(/\*\*/g, "")}
                  <br />
                </span>
              ))}
            </div>
          </div>
        ))}

        {cargando && (
          <div style={{ ...styles.burbuja, ...styles.burbujaAsistente }}>
            <span style={styles.avatar}>🤖</span>
            <div style={styles.puntos}>
              <span style={{ ...styles.punto, animationDelay: "0s" }} />
              <span style={{ ...styles.punto, animationDelay: "0.2s" }} />
              <span style={{ ...styles.punto, animationDelay: "0.4s" }} />
            </div>
            <span style={styles.esperando}>Consultando restaurantes...</span>
          </div>
        )}
        <div ref={bottomRef} />
      </main>

      {/* Sugerencias */}
      {mensajes.length === 1 && (
        <div style={styles.sugerencias}>
          {sugerencias.map((s, i) => (
            <button key={i} style={styles.chip} onClick={() => enviar(s)}>
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <footer style={styles.footer}>
        <div style={styles.inputWrap}>
          <input
            style={styles.input}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && enviar()}
            placeholder="¿Qué tipo de restaurante buscas?"
            disabled={cargando}
          />
          <button style={{ ...styles.boton, opacity: cargando ? 0.5 : 1 }} onClick={() => enviar()} disabled={cargando}>
            ➤
          </button>
        </div>
      </footer>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@400;500&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #0f0f0f; font-family: 'DM Sans', sans-serif; }
        @keyframes bounce {
          0%, 80%, 100% { transform: translateY(0); }
          40% { transform: translateY(-6px); }
        }
      `}</style>
    </div>
  );
}

const styles = {
  root: {
    display: "flex",
    flexDirection: "column",
    height: "100vh",
    maxWidth: 680,
    margin: "0 auto",
    background: "#111",
    color: "#f0ece4",
  },
  header: {
    padding: "16px 20px",
    borderBottom: "1px solid #2a2a2a",
    background: "#111",
    position: "sticky",
    top: 0,
    zIndex: 10,
  },
  headerInner: {
    display: "flex",
    alignItems: "center",
    gap: 12,
  },
  logo: { fontSize: 32 },
  titulo: {
    fontFamily: "'DM Serif Display', serif",
    fontSize: 20,
    color: "#f0ece4",
    letterSpacing: "-0.3px",
  },
  subtitulo: {
    fontSize: 11,
    color: "#666",
    letterSpacing: "0.5px",
    textTransform: "uppercase",
    marginTop: 2,
  },
  chat: {
    flex: 1,
    overflowY: "auto",
    padding: "20px 16px",
    display: "flex",
    flexDirection: "column",
    gap: 16,
  },
  burbuja: {
    display: "flex",
    alignItems: "flex-start",
    gap: 10,
    maxWidth: "85%",
  },
  burbujaUsuario: {
    alignSelf: "flex-end",
    flexDirection: "row-reverse",
  },
  burbujaAsistente: {
    alignSelf: "flex-start",
  },
  avatar: { fontSize: 22, flexShrink: 0, marginTop: 2 },
  texto: {
    padding: "12px 16px",
    borderRadius: 16,
    fontSize: 14,
    lineHeight: 1.6,
  },
  textoUsuario: {
    background: "#c8a96e",
    color: "#111",
    borderTopRightRadius: 4,
  },
  textoAsistente: {
    background: "#1e1e1e",
    color: "#e8e4dc",
    borderTopLeftRadius: 4,
    border: "1px solid #2a2a2a",
  },
  puntos: {
    background: "#1e1e1e",
    border: "1px solid #2a2a2a",
    borderRadius: 16,
    borderTopLeftRadius: 4,
    padding: "14px 18px",
    display: "flex",
    gap: 6,
    alignItems: "center",
  },
  punto: {
    width: 7,
    height: 7,
    borderRadius: "50%",
    background: "#c8a96e",
    display: "inline-block",
    animation: "bounce 1.2s infinite ease-in-out",
  },
  esperando: {
    fontSize: 12,
    color: "#666",
    alignSelf: "center",
    marginLeft: 4,
    fontStyle: "italic",
  },
  sugerencias: {
    padding: "0 16px 12px",
    display: "flex",
    flexWrap: "wrap",
    gap: 8,
  },
  chip: {
    background: "transparent",
    border: "1px solid #333",
    color: "#aaa",
    borderRadius: 20,
    padding: "6px 14px",
    fontSize: 12,
    cursor: "pointer",
    transition: "all 0.2s",
  },
  footer: {
    padding: "12px 16px 20px",
    borderTop: "1px solid #2a2a2a",
    background: "#111",
  },
  inputWrap: {
    display: "flex",
    gap: 10,
    alignItems: "center",
  },
  input: {
    flex: 1,
    background: "#1e1e1e",
    border: "1px solid #333",
    borderRadius: 24,
    padding: "12px 18px",
    color: "#f0ece4",
    fontSize: 14,
    outline: "none",
  },
  boton: {
    background: "#c8a96e",
    border: "none",
    borderRadius: "50%",
    width: 44,
    height: 44,
    fontSize: 16,
    cursor: "pointer",
    color: "#111",
    fontWeight: "bold",
    flexShrink: 0,
  },
};
