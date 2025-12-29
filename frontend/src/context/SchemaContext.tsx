import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import type { TableSchema } from '../types';

interface SchemaContextType {
    dbTables: TableSchema[];
    checkedKeys: React.Key[];
    setCheckedKeys: (keys: React.Key[]) => void;
    refreshTables: () => Promise<void>;
    loading: boolean;
}

const SchemaContext = createContext<SchemaContextType | undefined>(undefined);

export const SchemaProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [dbTables, setDbTables] = useState<TableSchema[]>([]);
    const [checkedKeys, setCheckedKeys] = useState<React.Key[]>([]);
    const [loading, setLoading] = useState(false);

    const fetchTables = async () => {
        setLoading(true);
        try {
            const res = await fetch('http://localhost:8000/tables');
            const data = await res.json();
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
        fetchTables();
    }, []);

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
