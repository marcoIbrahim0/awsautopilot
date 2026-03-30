'use client';

import { useState } from 'react';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';

interface TenantIdFormProps {
  onSave: (tenantId: string) => void;
}

/**
 * Shown when no tenant ID is configured. Lets the user enter one and save (persisted to localStorage).
 */
export function TenantIdForm({ onSave }: TenantIdFormProps) {
  const [value, setValue] = useState('');
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    const trimmed = value.trim();
    if (!trimmed) return;
    setSaving(true);
    try {
      onSave(trimmed);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mb-6 p-6 bg-surface border border-border rounded-xl max-w-md">
      <h3 className="text-base font-medium text-text mb-1">Tenant ID</h3>
      <p className="text-sm text-muted mb-4">
        Enter your tenant ID to load data. It will be saved in this browser.
      </p>
      <div className="flex gap-3 items-end">
        <div className="flex-1">
          <Input
            label="Tenant ID"
            placeholder="e.g. tenant-uuid"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSave()}
          />
        </div>
        <Button onClick={handleSave} disabled={!value.trim() || saving}>
          {saving ? 'Saving…' : 'Save'}
        </Button>
      </div>
    </div>
  );
}
