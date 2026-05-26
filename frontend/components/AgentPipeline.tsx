"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Check, X, Loader2, RefreshCw, Clock } from "lucide-react";
import type { AgentStep, AgentStatus } from "@/types";

interface Props {
  steps: AgentStep[];
  retryCount: number;
}

const statusConfig: Record<AgentStatus, { icon: React.ReactNode; color: string; dot: string }> = {
  idle: {
    icon: <Clock className="w-3.5 h-3.5" />,
    color: "text-[#3a3a4a] border-[#1f1f27]",
    dot: "bg-[#2a2a38]",
  },
  active: {
    icon: <Loader2 className="w-3.5 h-3.5 animate-spin" />,
    color: "text-violet-300 border-violet-500/50",
    dot: "bg-violet-500 shadow-[0_0_8px_rgba(139,92,246,0.6)]",
  },
  done: {
    icon: <Check className="w-3.5 h-3.5" />,
    color: "text-emerald-400 border-emerald-500/30",
    dot: "bg-emerald-500",
  },
  failed: {
    icon: <X className="w-3.5 h-3.5" />,
    color: "text-red-400 border-red-500/40",
    dot: "bg-red-500",
  },
  retrying: {
    icon: <RefreshCw className="w-3.5 h-3.5 animate-spin" />,
    color: "text-amber-400 border-amber-500/40",
    dot: "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.5)]",
  },
};

function StepCard({ step, isLast }: { step: AgentStep; isLast: boolean }) {
  const cfg = statusConfig[step.status];

  return (
    <div className="flex gap-4">
      {/* Timeline spine */}
      <div className="flex flex-col items-center">
        <motion.div
          layout
          className={`w-2.5 h-2.5 rounded-full mt-1.5 flex-shrink-0 transition-all duration-500 ${cfg.dot}`}
        />
        {!isLast && <div className="w-px flex-1 bg-[#1f1f27] mt-1 min-h-[40px]" />}
      </div>

      {/* Card */}
      <motion.div
        layout
        className={`flex-1 mb-4 rounded-lg border px-4 py-3 transition-all duration-300 ${
          step.status === "active"
            ? "bg-[#13101f] border-violet-500/40 shadow-[0_0_16px_rgba(139,92,246,0.12)]"
            : step.status === "retrying"
            ? "bg-[#1a1000] border-amber-500/30"
            : step.status === "failed"
            ? "bg-[#1a0a0a] border-red-500/30"
            : step.status === "done"
            ? "bg-[#0d0d0f] border-emerald-500/20"
            : "bg-[#0d0d0f] border-[#1a1a22]"
        }`}
      >
        <div className="flex items-center justify-between mb-1">
          <span className="text-[#e2e2e8] text-sm font-medium">{step.name}</span>
          <span className={`flex items-center gap-1.5 text-xs ${cfg.color}`}>
            {cfg.icon}
            <span className="capitalize">{step.status}</span>
          </span>
        </div>
        <p className="text-[#5a5a6a] text-xs leading-relaxed">{step.detail ?? step.description}</p>
      </motion.div>
    </div>
  );
}

export default function AgentPipeline({ steps, retryCount }: Props) {
  const showRetryLoop = steps.some((s) => s.status === "failed" || s.status === "retrying");

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.1 }}
      className="w-full max-w-xl mx-auto mt-10"
    >
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xs font-semibold text-[#4a4a5a] uppercase tracking-widest">Agent Pipeline</h2>
        {retryCount > 0 && (
          <span className="text-xs text-amber-400 bg-amber-400/10 border border-amber-400/20 rounded-full px-2.5 py-0.5">
            {retryCount} retry
          </span>
        )}
      </div>

      {steps.map((step, i) => (
        <StepCard key={step.id} step={step} isLast={i === steps.length - 1} />
      ))}

      {/* Retry loop annotation */}
      <AnimatePresence>
        {showRetryLoop && (
          <motion.div
            key="retry-loop"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="ml-6 mt-1 flex items-center gap-2 text-xs text-amber-400/70"
          >
            <RefreshCw className="w-3 h-3" />
            <span>Validation failed — feeding error context back to Patch Agent</span>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
