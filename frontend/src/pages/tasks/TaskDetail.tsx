import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  CheckCircle,
  Clock,
  Loader2,
  MessageSquare,
  Send,
  ShieldCheck,
  TestTube,
  XCircle,
} from 'lucide-react';
import * as api from '../../lib/api';
import type { MaintenanceTask } from '../../lib/types';

interface TaskDetailProps {
  taskId: string;
}

export default function TaskDetail({ taskId }: TaskDetailProps) {
  const { t } = useTranslation();
  const [task, setTask] = useState<MaintenanceTask | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Message form
  const [messageText, setMessageText] = useState('');
  const [sendingMessage, setSendingMessage] = useState(false);

  // Approval form
  const [approvalNote, setApprovalNote] = useState('');
  const [approvingAction, setApprovingAction] = useState<'approve' | 'reject' | null>(null);

  // Test result form
  const [testType, setTestType] = useState('');
  const [testTitle, setTestTitle] = useState('');
  const [testSummary, setTestSummary] = useState('');
  const [addingTest, setAddingTest] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const data = await api.getTask(Number(taskId));
        setTask(data);
      } catch (err) {
        console.error('Failed to load task:', err);
        setError('Failed to load task data');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [taskId]);

  async function handleSendMessage() {
    if (!messageText.trim() || !task) return;
    setSendingMessage(true);
    try {
      const updated = await api.addMessage(task.id, {
        author_name: 'current_user',
        message_text: messageText.trim(),
      });
      setTask(updated);
      setMessageText('');
    } catch (err) {
      console.error('Failed to send message:', err);
    } finally {
      setSendingMessage(false);
    }
  }

  async function handleApproval(approved: boolean) {
    if (!task) return;
    setApprovingAction(approved ? 'approve' : 'reject');
    try {
      const updated = await api.approveTask(task.id, {
        approver_name: 'current_user',
        approved,
        decision_note: approvalNote.trim() || null,
      });
      setTask(updated);
      setApprovalNote('');
    } catch (err) {
      console.error('Failed to submit approval:', err);
    } finally {
      setApprovingAction(null);
    }
  }

  async function handleAddTestResult() {
    if (!testType.trim() || !testTitle.trim() || !task) return;
    setAddingTest(true);
    try {
      const updated = await api.addTestResult(task.id, {
        test_type: testType.trim(),
        title: testTitle.trim(),
        summary: testSummary.trim() || null,
      });
      setTask(updated);
      setTestType('');
      setTestTitle('');
      setTestSummary('');
    } catch (err) {
      console.error('Failed to add test result:', err);
    } finally {
      setAddingTest(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (error || !task) {
    return (
      <div className="p-6 text-center text-red-600">
        <p>{error || 'Task not found'}</p>
      </div>
    );
  }

  const priorityColor: Record<string, string> = {
    low: 'bg-gray-100 text-gray-600',
    medium: 'bg-blue-100 text-blue-700',
    high: 'bg-orange-100 text-orange-700',
    critical: 'bg-red-100 text-red-700',
  };

  const statusColor: Record<string, string> = {
    open: 'bg-yellow-100 text-yellow-700',
    in_progress: 'bg-blue-100 text-blue-700',
    closed: 'bg-green-100 text-green-700',
  };

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">{task.title}</h1>
        <div className="flex items-center gap-3">
          <span
            className={`px-3 py-1 rounded-full text-xs font-medium ${statusColor[task.status] || 'bg-gray-100 text-gray-700'}`}
          >
            {task.status}
          </span>
          <span
            className={`px-3 py-1 rounded-full text-xs font-medium ${priorityColor[task.priority || 'medium'] || 'bg-gray-100 text-gray-700'}`}
          >
            {task.priority || 'medium'}
          </span>
          <span className="text-sm text-gray-500 capitalize">{task.task_type || '-'}</span>
        </div>
      </div>

      {/* Info Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow-sm p-4">
          <p className="text-xs text-gray-500 mb-1">Project</p>
          <p className="text-sm font-medium">#{task.project_id}</p>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4">
          <p className="text-xs text-gray-500 mb-1">Site</p>
          <p className="text-sm font-medium">{task.site_name}</p>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4">
          <p className="text-xs text-gray-500 mb-1">Asset</p>
          <p className="text-sm font-medium">
            {task.asset_type} {task.asset_ref || ''}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4">
          <p className="text-xs text-gray-500 mb-1">Assigned To</p>
          <p className="text-sm font-medium">{task.assigned_to || 'Unassigned'}</p>
        </div>
      </div>

      {/* Description */}
      {task.description && (
        <div className="bg-white rounded-lg shadow-sm p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-2">Description</h3>
          <p className="text-sm text-gray-600">{task.description}</p>
        </div>
      )}

      {/* Messages Section */}
      <div className="bg-white rounded-lg shadow-sm p-4">
        <div className="flex items-center gap-2 mb-4">
          <MessageSquare className="h-5 w-5 text-blue-500" />
          <h3 className="text-sm font-medium text-gray-900">
            {t('tasks.messages', 'Messages')} ({task.messages.length})
          </h3>
        </div>

        {task.messages.length === 0 ? (
          <p className="text-sm text-gray-500 mb-4">No messages yet.</p>
        ) : (
          <div className="space-y-3 mb-4 max-h-64 overflow-y-auto">
            {task.messages.map((msg, i) => (
              <div key={i} className="flex gap-3 p-3 bg-gray-50 rounded-lg">
                <div className="flex-shrink-0 h-8 w-8 bg-blue-100 rounded-full flex items-center justify-center">
                  <span className="text-xs font-medium text-blue-700">
                    {String(msg.author_name || 'U')
                      .charAt(0)
                      .toUpperCase()}
                  </span>
                </div>
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium">
                      {String(msg.author_name || 'Unknown')}
                    </span>
                    <Clock className="h-3 w-3 text-gray-400" />
                    <span className="text-xs text-gray-400">
                      {String(msg.created_at || '')}
                    </span>
                  </div>
                  <p className="text-sm text-gray-700">{String(msg.message_text || '')}</p>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Add Message */}
        <div className="flex gap-2">
          <textarea
            value={messageText}
            onChange={(e) => setMessageText(e.target.value)}
            rows={2}
            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            placeholder="Type a message..."
          />
          <button
            onClick={handleSendMessage}
            disabled={sendingMessage || !messageText.trim()}
            className="self-end px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium disabled:opacity-50"
          >
            {sendingMessage ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </button>
        </div>
      </div>

      {/* Approval Section */}
      {task.requires_approval && (
        <div className="bg-white rounded-lg shadow-sm p-4">
          <div className="flex items-center gap-2 mb-4">
            <ShieldCheck className="h-5 w-5 text-amber-500" />
            <h3 className="text-sm font-medium text-gray-900">
              Approval ({task.approvals.length})
            </h3>
          </div>

          {task.approvals.length > 0 && (
            <div className="space-y-2 mb-4">
              {task.approvals.map((a, i) => (
                <div key={i} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                  {a.approved ? (
                    <CheckCircle className="h-5 w-5 text-green-500" />
                  ) : (
                    <XCircle className="h-5 w-5 text-red-500" />
                  )}
                  <div>
                    <span className="text-sm font-medium">
                      {String(a.approver_name || 'Unknown')}
                    </span>
                    {a.decision_note && (
                      <p className="text-xs text-gray-500">{String(a.decision_note)}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="space-y-3">
            <textarea
              value={approvalNote}
              onChange={(e) => setApprovalNote(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              placeholder="Approval note (optional)..."
            />
            <div className="flex gap-2">
              <button
                onClick={() => handleApproval(true)}
                disabled={approvingAction !== null}
                className="inline-flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm font-medium disabled:opacity-50"
              >
                {approvingAction === 'approve' && (
                  <Loader2 className="h-4 w-4 animate-spin" />
                )}
                <CheckCircle className="h-4 w-4" />
                Approve
              </button>
              <button
                onClick={() => handleApproval(false)}
                disabled={approvingAction !== null}
                className="inline-flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm font-medium disabled:opacity-50"
              >
                {approvingAction === 'reject' && (
                  <Loader2 className="h-4 w-4 animate-spin" />
                )}
                <XCircle className="h-4 w-4" />
                Reject
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Test Results Section */}
      {task.requires_test_result && (
        <div className="bg-white rounded-lg shadow-sm p-4">
          <div className="flex items-center gap-2 mb-4">
            <TestTube className="h-5 w-5 text-purple-500" />
            <h3 className="text-sm font-medium text-gray-900">
              Test Results ({task.test_results.length})
            </h3>
          </div>

          {task.test_results.length > 0 && (
            <div className="space-y-2 mb-4">
              {task.test_results.map((tr, i) => (
                <div key={i} className="p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium">
                      {String(tr.title || 'Untitled')}
                    </span>
                    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-700">
                      {String(tr.test_type || '')}
                    </span>
                    {tr.status && (
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          tr.status === 'pass'
                            ? 'bg-green-100 text-green-700'
                            : 'bg-red-100 text-red-700'
                        }`}
                      >
                        {String(tr.status)}
                      </span>
                    )}
                  </div>
                  {tr.summary && (
                    <p className="text-xs text-gray-500">{String(tr.summary)}</p>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Add Test Result */}
          <div className="space-y-3 border-t border-gray-200 pt-3">
            <h4 className="text-xs font-medium text-gray-500 uppercase">Add Test Result</h4>
            <div className="grid grid-cols-2 gap-3">
              <input
                type="text"
                value={testType}
                onChange={(e) => setTestType(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Test type (e.g. IV curve)"
              />
              <input
                type="text"
                value={testTitle}
                onChange={(e) => setTestTitle(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Test title"
              />
            </div>
            <textarea
              value={testSummary}
              onChange={(e) => setTestSummary(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              placeholder="Summary (optional)..."
            />
            <button
              onClick={handleAddTestResult}
              disabled={addingTest || !testType.trim() || !testTitle.trim()}
              className="inline-flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 text-sm font-medium disabled:opacity-50"
            >
              {addingTest && <Loader2 className="h-4 w-4 animate-spin" />}
              Add Result
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
