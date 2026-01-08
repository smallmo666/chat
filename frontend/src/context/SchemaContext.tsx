import React, { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import type { TableSchema } from '../chatTypes';
import api from '../lib/api';

interface SchemaContextType {
    dbTables: TableSchema[];
    checkedKeys: React.Key[];
    setCheckedKeys: (keys: React.Key[]) => void;
    refreshTables: () => Promise<void>;
    loading: boolean;
}

const SchemaContext = createContext<SchemaContextType | undefined>(undefined);

export const SchemaProvider: React.FC<{ children: ReactNode; projectId?: string }> = ({ children, projectId }) => {
    const [dbTables, setDbTables] = useState<TableSchema[]>([]);
    const [checkedKeys, setCheckedKeys] = useState<React.Key[]>([]);
    const [loading, setLoading] = useState(false);

    const fetchTables = async () => {
        setLoading(true);
        try {
            const res = await api.post('/api/projects/tables', { project_id: projectId ? parseInt(projectId) : undefined });
            const data = res.data;
            if (data.tables) {
                setDbTables(data.tables);
            }
        } catch (err) {
            console.error("Failed to fetch tables", err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (projectId) {
            fetchTables();
        }
    }, [projectId]);

    const refreshTables = async () => {
        await fetchTables();
    };

    return (
        <SchemaContext.Provider value={{ dbTables, checkedKeys, setCheckedKeys, refreshTables, loading }}>
            {children}
        </SchemaContext.Provider>
    );
};

export const useSchema = () => {
    const context = useContext(SchemaContext);
    if (context === undefined) {
        throw new Error('useSchema must be used within a SchemaProvider');
    }
    return context;
};
