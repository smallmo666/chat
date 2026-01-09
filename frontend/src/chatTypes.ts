export interface Message {
    role: 'user' | 'agent';
    content?: string | any; // Allow any for complex content
    thinking?: string;
    data?: any[];
    vizOption?: any; // ECharts option for dashboard pinning
    interrupt?: boolean; // HITL flag
    
    // V2.0 New Fields
    hypotheses?: string[];
    analysisDepth?: 'simple' | 'deep';
    insights?: string[];
    uiComponent?: string;
    images?: string[]; // List of base64 images from Python analysis
    plan?: TaskItem[]; // Execution plan steps
    clarification?: {
        question: string;
        options: string[];
        type?: 'select' | 'multiple';
        scope?: 'task' | 'schema' | 'param';
    };
    actionLogs?: { node: string; step: string; detail?: string; metrics?: any; ts?: number }[];
    detectiveInsight?: { hypotheses: string[]; depth: string }; // 补充 detectiveInsight 字段
    currentTask?: string; // 当前正在进行的任务描述
    
    // UI Helpers
    downloadToken?: string;
    isCode?: boolean;
    isAnalysis?: boolean;
    tableData?: { columns: string[]; data: any[] };
}

export type TaskItem = {
  id: string;
  title: string;
  status: 'pending' | 'process' | 'finish' | 'error';
  description?: React.ReactNode;
  duration?: number;
  logs?: string[];
  subtasks?: TaskItem[];
  startTime?: number;
  endTime?: number;
}

export type TableColumn = {
    name: string;
    type: string;
    comment?: string;
}

export type TableSchema = {
    name: string;
    comment?: string;
    columns: TableColumn[];
}

export type TreeDataNode = {
    title: React.ReactNode;
    key: string;
    isLeaf?: boolean;
    children?: TreeDataNode[];
    icon?: React.ReactNode;
}

export interface ChatSession {
    id: string;
    title: string;
    updated_at: string;
    project_id: number;
}
