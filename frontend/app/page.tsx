"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import Navbar from "@/components/Navbar";
import UploadCard from "@/components/UploadCard";
import AgentPipeline from "@/components/AgentPipeline";
import ResultsSection from "@/components/ResultsSection";
import { buildSimulationFrames, mockResults } from "@/lib/mockData";
import type { PipelineState } from "@/types";

const FRAME_DELAY = 1400;

export default function Home() {
  const [pipeline, setPipeline] = useState<PipelineState | null>(null);
  const [running, setRunning] = useState(false);

  const runForge = () => {
    setRunning(true);
    const frames = buildSimulationFrames();
    let i = 0;

    const tick = () => {
      if (i >= frames.length) {
        setRunning(false);
        return;
      }
      setPipeline(frames[i]);
      i++;
      setTimeout(tick, FRAME_DELAY);
    };

    tick();
  };

  const isComplete = pipeline?.isComplete ?? false;

  return (
    <div className="min-h-screen bg-[#0d0d0f] text-[#e2e2e8]">
      <Navbar />

      <main className="pt-24 pb-20 px-6">
        <AnimatePresence>
          {!pipeline && (
            <motion.div exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.25 }}>
              <UploadCard onRun={runForge} disabled={running} />
            </motion.div>
          )}
        </AnimatePresence>

        {pipeline && (
          <AgentPipeline steps={pipeline.steps} retryCount={pipeline.retryCount} />
        )}

        {isComplete && (
          <ResultsSection results={mockResults} />
        )}
      </main>
    </div>
  );
}
