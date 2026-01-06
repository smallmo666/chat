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
}

export type TaskItem = {
  id: string;
  title: string;
  status: 'pending' | 'process' | 'finish' | 'error';
  description?: React.ReactNode;
  duration?: number;
  logs?: string[];
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

// Dummy export to ensure this is treated as a module
export const _types = true;
