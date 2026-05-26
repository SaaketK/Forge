"use client";

import { Flame, GitBranch } from "lucide-react";

export default function Navbar() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 h-14 border-b border-[#1f1f27] bg-[#0d0d0f]/80 backdrop-blur-md flex items-center px-6">
      <div className="flex items-center gap-2">
        <Flame className="w-5 h-5 text-orange-400" />
        <span className="font-semibold text-[#e2e2e8] tracking-tight">Forge</span>
      </div>
      <div className="ml-auto">
        <a
          href="https://github.com"
          target="_blank"
          rel="noreferrer"
          className="text-[#6b6b7b] hover:text-[#e2e2e8] transition-colors"
        >
          <GitBranch className="w-5 h-5" />
        </a>
      </div>
    </nav>
  );
}
