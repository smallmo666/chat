import React from 'react';

export type Message = {
  role: 'user' | 'agent';
  content?: string | React.ReactNode;
  thinking?: string;
  data?: any[]; // For export
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
