'use client';

import { useState, useRef, useCallback } from 'react';
import { motion, AnimatePresence, Reorder } from 'motion/react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type GroupingDimension = 'rule' | 'severity' | 'region' | 'resource' | 'status' | 'remediation';

const DIMENSION_LABELS: Record<GroupingDimension, string> = {
    rule: 'Rule',
    severity: 'Severity',
    region: 'Region',
    resource: 'Resource',
    status: 'Status',
    remediation: 'Remediation path',
};

const ALL_DIMENSIONS: GroupingDimension[] = ['rule', 'severity', 'region', 'resource', 'status', 'remediation'];
const MAX_DIMENSIONS = 3;

export interface GroupingControlBarProps {
    /** Currently active grouping stack, ordered parent → child */
    value: GroupingDimension[];
    onChange: (next: GroupingDimension[]) => void;
}

// ---------------------------------------------------------------------------
// Dimension picker popover
// ---------------------------------------------------------------------------

interface DimensionPickerProps {
    available: GroupingDimension[];
    onSelect: (dim: GroupingDimension) => void;
    onClose: () => void;
}

function DimensionPicker({ available, onSelect, onClose }: DimensionPickerProps) {
    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -4 }}
            transition={{ duration: 0.12 }}
            className="absolute left-0 top-full mt-1 z-50 min-w-40 rounded-xl border border-border bg-dropdown-bg shadow-premium p-1"
        >
            {available.length === 0 ? (
                <p className="px-3 py-2 text-xs text-muted">Max {MAX_DIMENSIONS} dimensions reached</p>
            ) : (
                available.map((dim) => (
                    <button
                        key={dim}
                        onClick={() => { onSelect(dim); onClose(); }}
                        className="w-full flex items-center gap-2 px-3 py-1.5 text-sm text-text rounded-lg hover:bg-accent/10 hover:text-accent transition-colors text-left"
                    >
                        {DIMENSION_LABELS[dim]}
                    </button>
                ))
            )}
        </motion.div>
    );
}

// ---------------------------------------------------------------------------
// Dimension token
// ---------------------------------------------------------------------------

interface TokenProps {
    dim: GroupingDimension;
    index: number;
    total: number;
    onRemove: () => void;
}

function GroupingToken({ dim, index, total, onRemove }: TokenProps) {
    return (
        <div className="flex items-center gap-1">
            {/* Token pill */}
            <div className="flex items-center gap-1.5 pl-2.5 pr-1.5 py-1 rounded-lg nm-neu-sm bg-transparent text-accent text-sm font-semibold select-none cursor-grab active:cursor-grabbing group">
                {/* Drag handle */}
                <svg className="w-3 h-3 opacity-40 shrink-0 group-hover:opacity-70 transition-opacity" fill="currentColor" viewBox="0 0 16 16">
                    <circle cx="5" cy="4" r="1.2" />
                    <circle cx="11" cy="4" r="1.2" />
                    <circle cx="5" cy="8" r="1.2" />
                    <circle cx="11" cy="8" r="1.2" />
                    <circle cx="5" cy="12" r="1.2" />
                    <circle cx="11" cy="12" r="1.2" />
                </svg>
                <span className="tracking-tight">{DIMENSION_LABELS[dim]}</span>
                <button
                    onClick={(e) => { e.stopPropagation(); onRemove(); }}
                    className="w-4 h-4 flex items-center justify-center rounded-md hover:nm-inset-sm transition-all duration-200"
                    aria-label={`Remove ${DIMENSION_LABELS[dim]} grouping`}
                >
                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                </button>
            </div>

            {/* Arrow connector between tokens */}
            {index < total - 1 && (
                <svg className="w-4 h-4 text-muted shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                </svg>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// GroupingControlBar
// ---------------------------------------------------------------------------

export function GroupingControlBar({ value, onChange }: GroupingControlBarProps) {
    const [pickerOpen, setPickerOpen] = useState(false);
    const pickerRef = useRef<HTMLDivElement>(null);

    const available = ALL_DIMENSIONS.filter((d) => !value.includes(d));
    const canAdd = value.length < MAX_DIMENSIONS;

    const handleAdd = useCallback((dim: GroupingDimension) => {
        onChange([...value, dim]);
    }, [value, onChange]);

    const handleRemove = useCallback((dim: GroupingDimension) => {
        onChange(value.filter((d) => d !== dim));
    }, [value, onChange]);

    const handleReorder = useCallback((next: GroupingDimension[]) => {
        onChange(next);
    }, [onChange]);

    // Close picker on outside click
    const handlePickerToggle = () => {
        setPickerOpen((v) => !v);
    };

    return (
        <div className="flex flex-wrap items-center gap-2 py-2">
            {/* Label */}
            <span className="text-xs text-muted font-medium shrink-0 uppercase tracking-wide">Group by</span>

            {/* Reorderable token list */}
            <Reorder.Group
                axis="x"
                values={value}
                onReorder={handleReorder}
                className="flex items-center gap-1 flex-wrap"
                as="div"
            >
                <AnimatePresence initial={false}>
                    {value.map((dim, index) => (
                        <Reorder.Item
                            key={dim}
                            value={dim}
                            as="div"
                            className="flex items-center gap-1"
                            initial={{ opacity: 0, scale: 0.85 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.85 }}
                            transition={{ duration: 0.15 }}
                        >
                            <GroupingToken
                                dim={dim}
                                index={index}
                                total={value.length}
                                onRemove={() => handleRemove(dim)}
                            />
                        </Reorder.Item>
                    ))}
                </AnimatePresence>
            </Reorder.Group>

            {/* Add grouping button + picker */}
            {canAdd && (
                <div className="relative" ref={pickerRef}>
                    <button
                        onClick={handlePickerToggle}
                        className="flex items-center gap-1.5 px-3 py-1 rounded-lg border border-dashed border-accent/40 bg-transparent text-accent/80 text-sm hover:nm-neu-sm hover:border-transparent hover:text-accent transition-all duration-300 font-medium"
                        aria-expanded={pickerOpen}
                        aria-haspopup="listbox"
                    >
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                        </svg>
                        Add Grouping
                    </button>

                    <AnimatePresence>
                        {pickerOpen && (
                            <>
                                {/* Backdrop to close on click outside */}
                                <div
                                    className="fixed inset-0 z-40"
                                    onClick={() => setPickerOpen(false)}
                                    aria-hidden="true"
                                />
                                <DimensionPicker
                                    available={available}
                                    onSelect={handleAdd}
                                    onClose={() => setPickerOpen(false)}
                                />
                            </>
                        )}
                    </AnimatePresence>
                </div>
            )}

            {/* Clear all */}
            {value.length > 0 && (
                <button
                    onClick={() => onChange([])}
                    className="text-xs text-muted hover:text-text transition-colors ml-1"
                >
                    Clear
                </button>
            )}
        </div>
    );
}
