"use client";

import { motion } from "framer-motion";
import { Download, ShieldAlert, Wrench, RefreshCw } from "lucide-react";
import type { Results } from "@/types";

interface Props {
  results: Results;
}

const cards = (r: Results) => [
  { label: "Findings", value: r.findings, icon: <ShieldAlert className="w-4 h-4 text-red-400" />, color: "text-red-400" },
  { label: "Patches Applied", value: r.patches, icon: <Wrench className="w-4 h-4 text-emerald-400" />, color: "text-emerald-400" },
  { label: "Retries", value: r.retries, icon: <RefreshCw className="w-4 h-4 text-amber-400" />, color: "text-amber-400" },
];

export default function ResultsSection({ results }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.15 }}
      className="w-full max-w-xl mx-auto mt-10"
    >
      <h2 className="text-xs font-semibold text-[#4a4a5a] uppercase tracking-widest mb-6">Results</h2>

      <div className="grid grid-cols-3 gap-3 mb-6">
        {cards(results).map((c) => (
          <div key={c.label} className="bg-[#0f0f16] border border-[#1f1f27] rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">{c.icon}<span className="text-[#5a5a6a] text-xs">{c.label}</span></div>
            <span className={`text-2xl font-semibold ${c.color}`}>{c.value}</span>
          </div>
        ))}
      </div>

      <button
        onClick={() => alert("Download would trigger here when connected to the backend.")}
        className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg border border-[#1f1f27] text-sm text-[#9b9baf] hover:text-[#e2e2e8] hover:border-[#2a2a38] transition-all duration-200"
      >
        <Download className="w-4 h-4" />
        Download Fixed File
      </button>
    </motion.div>
  );
}
