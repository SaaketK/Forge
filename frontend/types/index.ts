export type AgentStatus = "idle" | "active" | "done" | "failed" | "retrying";

export interface AgentStep {
  id: string;
  name: string;
  description: string;
  status: AgentStatus;
  detail?: string;
}

export interface PipelineState {
  steps: AgentStep[];
  retryCount: number;
  isComplete: boolean;
  phase: "idle" | "running" | "done";
}

export interface Finding {
  id: string;
  severity: "CRITICAL" | "WARNING" | "INFO";
  category: string;
  description: string;
}

export interface Results {
  findings: number;
  patches: number;
  retries: number;
}
