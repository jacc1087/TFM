import { useNavigate } from "react-router-dom";

const sugerencias = [
  "Restaurante italiano en Madrid",
  "Cocido madrileño",
  "Quiero comer cachopo",
  "Croquetas cerca de Malasaña",
  "Restaurante japonés con terraza",
  "Cena romántica para dos",
  "Mejor relación calidad-precio",
  "Asador con buen chuletón",
  "Cocina fusión en Madrid",
];

const stack = [
  { icon: "◎", label: "nlptown/bert", desc: "Análisis de sentimiento" },
  { icon: "◈", label: "Python · FastAPI", desc: "Backend y motor NLP" },
  { icon: "❖", label: "React", desc: "Interfaz de usuario" },
  { icon: "▲", label: "Render", desc: "Despliegue backend" },
  { icon: "△", label: "Vercel", desc: "Despliegue frontend" },
];

export default function Landing() {
  const navigate = useNavigate();

  const ir = (consulta) => {
    if (consulta) sessionStorage.setItem("consulta_inicial", consulta);
    navigate("/app");
  };

  return (
    <div style={s.root}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@400;500&display=swap');
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #111; font-family: 'DM Sans', sans-serif; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-thumb { background: #2a2a2a; border-radius: 4px; }
        .chip-btn:hover { border-color: #c8a96e !important; color: #c8a96e !important; }
        .nav-link:hover { color: #c8a96e !important; }
        .step-card:hover { border-color: #c8a96e22 !important; }
        .tech-card:hover { border-color: #c8a96e44 !important; }
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(14px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .fu1 { animation: fadeUp 0.55s ease both; }
        .fu2 { animation: fadeUp 0.55s 0.12s ease both; }
        .fu3 { animation: fadeUp 0.55s 0.24s ease both; }
        .fu4 { animation: fadeUp 0.55s 0.36s ease both; }
        @keyframes flowPulse {
          0%, 100% { opacity: 0.4; }
          50% { opacity: 1; }
        }
        .flow-arrow { animation: flowPulse 2s ease-in-out infinite; }
      `}</style>

      {/* Nav */}
      <nav style={s.nav}>
        <div style={s.navLogo}>
          <div style={s.logoBox}>🍽</div>
          <span style={s.navTitle}>Restaurantes Madrid</span>
        </div>
        <div style={{ display: "flex", gap: 28, alignItems: "center" }}>
          <a href="#como" style={s.navLink} className="nav-link">Cómo funciona</a>
          <a href="#tech" style={s.navLink} className="nav-link">Tecnología</a>
        </div>
      </nav>

      {/* Hero */}
      <section style={s.hero}>
        <p className="fu1" style={s.eyebrow}>180 restaurantes · 16.500+ reseñas reales</p>
        <h1 className="fu2" style={s.heroTitle}>
          Encuentra tu restaurante<br />ideal en <span style={{ color: "#c8a96e", fontStyle: "italic" }}>Madrid</span>
        </h1>
        <p className="fu3" style={s.heroSub}>
          Dile qué buscas. El asistente analiza miles de reseñas reales
          con NLP para recomendarte el sitio perfecto.
        </p>
        <div className="fu4" style={s.chips}>
          {sugerencias.map((sg, i) => (
            <button key={i} style={s.chip} className="chip-btn" onClick={() => ir(sg)}>
              {sg}
            </button>
          ))}
        </div>
        <div className="fu4" style={{ display: "flex", justifyContent: "center", marginTop: 32 }}>
          <button style={s.ctaBtn} onClick={() => ir()}>
            Abrir el asistente →
          </button>
        </div>
      </section>

      {/* Stats */}
      <section style={s.statsWrap}>
        {[
          { n: "180", l: "Restaurantes indexados" },
          { n: "+16.500", l: "Reseñas analizadas" },
          { n: "17", l: "Criterios de búsqueda" },
        ].map((stat, i) => (
          <div key={i} style={{ ...s.stat, borderRight: i < 2 ? "1px solid #1e1e1e" : "none" }}>
            <div style={s.statN}>{stat.n}</div>
            <div style={s.statL}>{stat.l}</div>
          </div>
        ))}
      </section>

      {/* Cómo funciona — diagrama de flujo */}
      <section id="como" style={{ ...s.section, borderTop: "1px solid #1a1a1a" }}>
        <div style={s.sectionLabel}>Cómo funciona</div>
        <h2 style={s.sectionTitle}>De las reseñas a la recomendación</h2>
        <FlujoProceso />
      </section>

      {/* Stack */}
      <section id="tech" style={{ ...s.section, borderTop: "1px solid #1a1a1a" }}>
        <div style={s.sectionLabel}>Tecnología</div>
        <h2 style={s.sectionTitle}>Stack utilizado</h2>
        <div style={s.techGrid}>
          {stack.map((t, i) => (
            <div key={i} style={s.techCard} className="tech-card">
              <span style={s.techIcon}>{t.icon}</span>
              <div>
                <div style={s.techLabel}>{t.label}</div>
                <div style={s.techDesc}>{t.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* CTA final */}
      <section style={{ ...s.section, borderTop: "1px solid #1a1a1a", textAlign: "center" }}>
        <h2 style={{ ...s.sectionTitle, marginBottom: 10 }}>¿Listo para buscar?</h2>
        <p style={{ fontSize: 14, color: "#555", marginBottom: 28, lineHeight: 1.6 }}>
          Cuéntale al asistente qué te apetece y encuentra tu próximo restaurante en segundos.
        </p>
        <button style={s.ctaBtn} onClick={() => ir()}>
          Abrir el asistente →
        </button>
      </section>

      <footer style={s.footer}>
        <span style={{ color: "#333" }}>Proyecto académico · 2026</span>
      </footer>
    </div>
  );
}

// ── Diagrama de flujo del proceso ─────────────────────────────────────────────
function FlujoProceso() {
  const pasos = [
    {
      icon: "🕸",
      titulo: "Scraping",
      desc: "Reseñas reales de los 180 restaurantes mejor valorados de Madrid",
      color: "#2a1f0a",
      border: "#c8a96e33",
      tag: "Datos",
    },
    {
      icon: "🧠",
      titulo: "Análisis NLP",
      desc: "nlptown/bert clasifica el sentimiento de cada reseña: positivo, neutro o negativo",
      color: "#0a1a2a",
      border: "#4a8ac833",
      tag: "nlptown/bert",
    },
    {
      icon: "🔍",
      titulo: "Extracción",
      desc: "Bigramas y whitelist detectan platos, criterios cualitativos y personal destacado",
      color: "#0a1f0a",
      border: "#4ac84a33",
      tag: "Python",
    },
    {
      icon: "💬",
      titulo: "Búsqueda",
      desc: "El usuario escribe su consulta y el motor NLP la interpreta y filtra resultados",
      color: "#1a0a2a",
      border: "#8a4ac833",
      tag: "FastAPI · React",
    },
  ];

  return (
    <div>
      {/* Desktop: horizontal */}
      <div style={{ display: "flex", alignItems: "stretch", gap: 0, overflowX: "auto" }}>
        {pasos.map((p, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", flex: 1, minWidth: 0 }}>
            {/* Tarjeta */}
            <div style={{
              flex: 1,
              background: p.color,
              border: `1px solid ${p.border}`,
              borderRadius: 14,
              padding: "20px 18px",
              minHeight: 160,
              display: "flex",
              flexDirection: "column",
              gap: 8,
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <span style={{ fontSize: 22 }}>{p.icon}</span>
                <span style={{
                  fontSize: 10, color: "#666", border: "1px solid #222",
                  borderRadius: 8, padding: "2px 8px", letterSpacing: "0.5px",
                }}>{p.tag}</span>
              </div>
              <div style={{ fontSize: 14, fontWeight: 500, color: "#f0ece4" }}>{p.titulo}</div>
              <div style={{ fontSize: 12, color: "#555", lineHeight: 1.6 }}>{p.desc}</div>
            </div>
            {/* Flecha entre pasos */}
            {i < pasos.length - 1 && (
              <div className="flow-arrow" style={{
                flexShrink: 0,
                width: 28,
                textAlign: "center",
                fontSize: 16,
                color: "#c8a96e",
              }}>→</div>
            )}
          </div>
        ))}
      </div>

      {/* Nota de resultado */}
      <div style={{
        marginTop: 20,
        background: "#161616",
        border: "1px solid #1e1e1e",
        borderRadius: 10,
        padding: "14px 20px",
        display: "flex",
        alignItems: "center",
        gap: 12,
      }}>
        <span style={{ fontSize: 20 }}>🍽</span>
        <div>
          <div style={{ fontSize: 13, color: "#c8a96e", fontWeight: 500 }}>Resultado</div>
          <div style={{ fontSize: 12, color: "#555", lineHeight: 1.6 }}>
            Lista ordenada de restaurantes con valoración, criterios cualitativos, platos más mencionados y frases reales de clientes.
          </div>
        </div>
      </div>
    </div>
  );
}

const s = {
  root: { background: "#111", color: "#f0ece4", minHeight: "100vh" },
  nav: {
    position: "sticky", top: 0, zIndex: 100,
    background: "#111111ee", backdropFilter: "blur(10px)",
    borderBottom: "1px solid #1e1e1e",
    padding: "13px 48px",
    display: "flex", alignItems: "center", justifyContent: "space-between",
  },
  navLogo: { display: "flex", alignItems: "center", gap: 10 },
  logoBox: {
    width: 34, height: 34, borderRadius: 8,
    background: "#1a1505", border: "1px solid #c8a96e22",
    display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16,
  },
  navTitle: { fontFamily: "'DM Serif Display', serif", fontSize: 16, color: "#f0ece4" },
  navLink: { fontSize: 13, color: "#555", textDecoration: "none", transition: "color 0.2s" },
  hero: {
    background: "#0f0f0f",
    padding: "88px 24px 72px",
    textAlign: "center",
    borderBottom: "1px solid #1a1a1a",
  },
  eyebrow: {
    fontSize: 11, letterSpacing: "2px", color: "#c8a96e44",
    textTransform: "uppercase", marginBottom: 18,
  },
  heroTitle: {
    fontFamily: "'DM Serif Display', serif",
    fontSize: "clamp(34px, 5.5vw, 52px)",
    lineHeight: 1.12, color: "#f0ece4",
    marginBottom: 18, letterSpacing: "-0.5px",
  },
  heroSub: {
    fontSize: 15, color: "#555", lineHeight: 1.75,
    maxWidth: 460, margin: "0 auto 32px",
  },
  ctaBtn: {
    background: "#c8a96e", color: "#111", border: "none",
    padding: "13px 28px", borderRadius: 28,
    fontSize: 15, fontWeight: 500, cursor: "pointer",
    fontFamily: "'DM Sans', sans-serif",
    transition: "background 0.2s",
  },
  chips: {
    display: "flex", flexWrap: "wrap", gap: 8,
    justifyContent: "center",
  },
  chip: {
    background: "transparent", border: "1px solid #2a2a2a",
    color: "#666", borderRadius: 20, padding: "9px 20px",
    fontSize: 13, cursor: "pointer", transition: "all 0.2s",
    fontFamily: "'DM Sans', sans-serif",
  },
  statsWrap: {
    display: "grid", gridTemplateColumns: "repeat(3, 1fr)",
    background: "#0f0f0f", borderBottom: "1px solid #1a1a1a",
  },
  stat: { padding: "28px 24px", textAlign: "center" },
  statN: {
    fontFamily: "'DM Serif Display', serif",
    fontSize: 32, color: "#c8a96e", marginBottom: 4,
  },
  statL: { fontSize: 11, color: "#444", letterSpacing: "0.3px" },
  section: { maxWidth: 860, margin: "0 auto", padding: "64px 24px" },
  sectionLabel: {
    fontSize: 11, letterSpacing: "2px", color: "#c8a96e",
    textTransform: "uppercase", marginBottom: 10,
  },
  sectionTitle: {
    fontFamily: "'DM Serif Display', serif",
    fontSize: 26, color: "#f0ece4", marginBottom: 36, letterSpacing: "-0.3px",
  },
  techGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
    gap: 10,
  },
  techCard: {
    background: "#161616", border: "1px solid #1e1e1e",
    borderRadius: 12, padding: "14px 16px",
    display: "flex", alignItems: "center", gap: 12,
    transition: "border-color 0.2s",
    cursor: "default",
  },
  techIcon: { color: "#c8a96e", fontSize: 18, flexShrink: 0 },
  techLabel: { fontSize: 13, color: "#ccc", fontWeight: 500 },
  techDesc: { fontSize: 11, color: "#444", marginTop: 2 },
  footer: {
    borderTop: "1px solid #1a1a1a",
    padding: "18px", textAlign: "center", fontSize: 11,
  },
};
