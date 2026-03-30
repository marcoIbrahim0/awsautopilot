'use client';

import { useCallback, useEffect, useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { useAuth } from '@/contexts/AuthContext';
import {
  deleteUser,
  getErrorMessage,
  getUsers,
  inviteUser,
  type UserListItem,
} from '@/lib/api';
import { SettingsCard, SettingsNotice, SettingsSectionIntro } from './settings-ui';

export function TeamSettingsTab() {
  const { user, isAuthenticated } = useAuth();
  const isAdmin = user?.role === 'admin';

  const [users, setUsers] = useState<UserListItem[]>([]);
  const [isLoadingUsers, setIsLoadingUsers] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [isInviting, setIsInviting] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [inviteSuccess, setInviteSuccess] = useState<string | null>(null);

  const [userToDelete, setUserToDelete] = useState<UserListItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const fetchUsers = useCallback(async () => {
    if (!isAuthenticated) return;
    setIsLoadingUsers(true);
    setError(null);
    try {
      setUsers(await getUsers());
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoadingUsers(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    void fetchUsers();
  }, [fetchUsers]);

  async function handleInvite(event: React.FormEvent) {
    event.preventDefault();
    setIsInviting(true);
    setInviteError(null);
    setInviteSuccess(null);

    try {
      await inviteUser(inviteEmail.trim());
      setInviteSuccess(`Invitation sent to ${inviteEmail.trim()}`);
      setInviteEmail('');
      await fetchUsers();
    } catch (err) {
      setInviteError(getErrorMessage(err));
    } finally {
      setIsInviting(false);
    }
  }

  async function handleDelete() {
    if (!userToDelete) return;
    setIsDeleting(true);
    setError(null);

    try {
      await deleteUser(userToDelete.id);
      setUsers((current) => current.filter((member) => member.id !== userToDelete.id));
      setUserToDelete(null);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <div id="settings-panel-team" role="tabpanel" tabIndex={0} className="space-y-6">
      <SettingsSectionIntro
        title="Team"
        description="Manage who has access to this tenant and who can administer settings."
        action={
          isAdmin ? (
            <Button onClick={() => setShowInviteModal(true)}>Invite user</Button>
          ) : (
            <Badge variant="info">Members are read-only</Badge>
          )
        }
      />

      {error ? <SettingsNotice tone="danger">{error}</SettingsNotice> : null}

      <SettingsCard className="overflow-hidden p-0">
        {isLoadingUsers ? (
          <div className="p-8 text-center">
            <p className="animate-pulse text-muted">Loading team members...</p>
          </div>
        ) : users.length === 0 ? (
          <div className="p-8 text-center">
            <p className="text-muted">No team members yet.</p>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {users.map((member) => {
              const avatarText = (member.name || member.email || '?').charAt(0).toUpperCase();
              return (
                <div
                  key={member.id}
                  className="flex items-center justify-between gap-4 p-4 transition-colors hover:bg-bg/50"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-accent/20 font-medium text-accent">
                      {avatarText}
                    </div>
                    <div className="min-w-0">
                      <p className="truncate font-medium text-text">
                        {member.name}
                        {member.id === user?.id ? (
                          <span className="ml-2 text-sm text-muted">(you)</span>
                        ) : null}
                      </p>
                      <p className="truncate text-sm text-muted">{member.email}</p>
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <Badge variant={member.role === 'admin' ? 'default' : 'info'}>{member.role}</Badge>
                    {isAdmin && member.id !== user?.id ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setUserToDelete(member)}
                        className="text-danger hover:bg-danger/10 hover:text-danger"
                      >
                        Remove
                      </Button>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </SettingsCard>

      <Modal
        isOpen={showInviteModal}
        onClose={() => {
          setShowInviteModal(false);
          setInviteEmail('');
          setInviteError(null);
          setInviteSuccess(null);
        }}
        title="Invite Team Member"
      >
        <form onSubmit={handleInvite} className="space-y-4">
          <p className="text-sm text-muted">
            Send an invitation email to add a new team member to your organization.
          </p>

          {inviteError ? <SettingsNotice tone="danger">{inviteError}</SettingsNotice> : null}
          {inviteSuccess ? <SettingsNotice tone="success">{inviteSuccess}</SettingsNotice> : null}

          <Input
            id="inviteEmail"
            type="email"
            label="Email Address"
            value={inviteEmail}
            onChange={(event) => setInviteEmail(event.target.value)}
            placeholder="colleague@company.com"
            required
          />

          <div className="flex justify-end gap-3 pt-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setShowInviteModal(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isInviting || !inviteEmail.trim()} isLoading={isInviting}>
              Send invitation
            </Button>
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={!!userToDelete}
        onClose={() => setUserToDelete(null)}
        title="Remove Team Member"
      >
        <div className="space-y-4">
          <p className="text-muted">
            Remove <span className="font-medium text-text">{userToDelete?.name}</span> ({userToDelete?.email}) from
            this team?
          </p>
          <p className="text-sm text-muted">They will no longer have access to this tenant.</p>

          <div className="flex justify-end gap-3 pt-2">
            <Button variant="secondary" onClick={() => setUserToDelete(null)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={handleDelete} isLoading={isDeleting}>
              Remove user
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
