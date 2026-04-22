import { NavLink, Outlet } from "react-router-dom";

const navItems = [
  { to: "/", label: "首页" },
  { to: "/stories", label: "Story" },
  { to: "/runs", label: "Runs" },
];

export function AppShell() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">S2P</div>
          <div>
            <div className="brand-title">Story2Proposal</div>
            <div className="brand-subtitle">Scientific Writing Studio</div>
          </div>
        </div>
        <nav className="topnav" aria-label="Main">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="page-root">
        <Outlet />
      </main>
    </div>
  );
}
