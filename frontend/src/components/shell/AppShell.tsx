"use client";

import React from "react";
import { Rail } from "./Rail";
import { TopBar } from "./TopBar";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex bg-bg-base text-ink antialiased selection:bg-uv-wash selection:text-uv">
      {/* Left Navigation Rail */}
      <Rail />

      {/* Main Container */}
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar />
        <main className="flex-1 p-6 max-w-7xl w-full mx-auto">{children}</main>
      </div>
    </div>
  );
}
export default AppShell;
