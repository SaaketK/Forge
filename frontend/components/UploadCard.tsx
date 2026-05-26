"use client";

import { useRef, useState } from "react";
import { motion } from "framer-motion";
import { Upload, FileCode } from "lucide-react";

interface Props {
  onRun: () => void;
  disabled: boolean;
}

export default function UploadCard({ onRun, disabled }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = (f: File) => {
    if (f.name.endsWith(".c") || f.name.endsWith(".h")) setFile(f);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="w-full max-w-xl mx-auto"
    >
      <h1 className="text-3xl font-semibold text-[#e2e2e8] text-center mb-3 tracking-tight">
        Autonomous C Code Repair
      </h1>
      <p className="text-[#6b6b7b] text-center text-sm mb-8 leading-relaxed">
        Forge analyzes, patches, and validates systems code using a multi-agent AI pipeline.
      </p>

      {/* Drop zone */}
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const f = e.dataTransfer.files[0];
          if (f) handleFile(f);
        }}
        className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all duration-200
          ${dragging
            ? "border-violet-500 bg-violet-500/5"
            : file
            ? "border-[#2a2a38] bg-[#13131a]"
            : "border-[#1f1f27] bg-[#0f0f16] hover:border-[#2a2a38] hover:bg-[#13131a]"
          }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".c,.h"
          className="hidden"
          onChange={(e) => { if (e.target.files?.[0]) handleFile(e.target.files[0]); }}
        />
        {file ? (
          <div className="flex flex-col items-center gap-2">
            <FileCode className="w-8 h-8 text-violet-400" />
            <span className="text-[#e2e2e8] font-medium text-sm">{file.name}</span>
            <span className="text-[#6b6b7b] text-xs">{(file.size / 1024).toFixed(1)} KB</span>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <Upload className="w-8 h-8 text-[#3a3a4a]" />
            <span className="text-[#6b6b7b] text-sm">Drop a <code className="text-violet-400">.c</code> file or click to browse</span>
          </div>
        )}
      </div>

      <button
        disabled={!file || disabled}
        onClick={() => file && onRun()}
        className="mt-4 w-full py-2.5 rounded-lg text-sm font-medium transition-all duration-200
          disabled:opacity-40 disabled:cursor-not-allowed
          bg-violet-600 hover:bg-violet-500 text-white"
      >
        Run Forge
      </button>
    </motion.div>
  );
}
