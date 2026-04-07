import React, { useState, useRef, useEffect, useCallback } from "react";
import { useMsal, useIsAuthenticated } from "@azure/msal-react";
import { loginRequest } from "../authConfig";

const TopBar: React.FC = () => {
  const { instance, accounts } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const account = accounts[0];
  const displayName = account?.name || account?.username || "";
  const initials = displayName
    .split(/[\s@]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0].toUpperCase())
    .join("");

  const handleLogin = useCallback(async () => {
    try {
      await instance.loginRedirect(loginRequest);
    } catch (e) {
      console.error("Login failed:", e);
    }
  }, [instance]);

  const handleLogout = useCallback(async () => {
    setMenuOpen(false);
    try {
      await instance.logoutRedirect();
    } catch (e) {
      console.error("Logout failed:", e);
    }
  }, [instance]);

  // Close menu on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    if (menuOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [menuOpen]);

  return (
    <header className="topbar">
      <div className="topbar-title">Foundry Hosted Agent + Entra Agent ID Demo</div>

      <div className="topbar-account" ref={menuRef}>
        {isAuthenticated ? (
          <>
            <button
              className="topbar-avatar"
              onClick={() => setMenuOpen((v) => !v)}
              title={displayName}
            >
              {initials}
            </button>
            {menuOpen && (
              <div className="topbar-menu">
                <div className="topbar-menu-header">
                  <div className="topbar-menu-name">{account?.name || "—"}</div>
                  <div className="topbar-menu-email">{account?.username || "—"}</div>
                </div>
                <div className="topbar-menu-divider" />
                <button className="topbar-menu-item" onClick={handleLogout}>
                  サインアウト
                </button>
              </div>
            )}
          </>
        ) : (
          <button className="btn btn-primary topbar-login-btn" onClick={handleLogin}>
            サインイン
          </button>
        )}
      </div>
    </header>
  );
};

export default TopBar;
