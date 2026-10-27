import { NavLink, Outlet } from "react-router";

const LINKS = [
  { to: "/", label: "Oggi", icon: "☀︎", end: true },
  { to: "/calendario", label: "Calendario", icon: "▦", end: false },
  { to: "/piante", label: "Piante", icon: "❦", end: false },
  { to: "/impostazioni", label: "Impostazioni", icon: "⚙︎", end: false },
];

export function Layout() {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Vai al contenuto
      </a>
      <nav className="app-nav" aria-label="Sezioni principali">
        <span className="app-brand" aria-hidden="true">
          <img src="/favicon.svg" alt="" width="28" height="28" /> Piante
        </span>
        <ul>
          {LINKS.map((link) => (
            <li key={link.to}>
              <NavLink to={link.to} end={link.end} className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
                <span className="nav-icon" aria-hidden="true">
                  {link.icon}
                </span>
                <span className="nav-label">{link.label}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <main id="main" className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
