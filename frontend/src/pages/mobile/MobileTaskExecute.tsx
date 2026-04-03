import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ArrowLeft, Send, CheckCircle, XCircle, Paperclip,
  MessageSquare, FlaskConical, ThumbsUp, ThumbsDown, Loader2,
} from 'lucide-react';
import axios from 'axios';
import * as api from '../../lib/api';
import type { MaintenanceTask } from '../../lib/types';

interface Props {
  taskId: number;
  onBack: () => void;
}

type Panel = 'messages' | 'test' | 'attachments';

export default function MobileTaskExecute({ taskId, onBack }: Props) {
  const { t } = useTranslation();
  const [task, setTask] = useState<MaintenanceTask | null>(null);
  const [loading, setLoading] = useState(true);
  const [panel, setPanel] = useState<Panel>('messages');
  const [messageText, setMessageText] = useState('');
  const [sending, setSending] = useState(false);
  const [testTitle, setTestTitle] = useState('');
  const [testType, setTestType] = useState('visual');
  const [testStatus, setTestStatus] = useState('pass');
  const [testSummary, setTestSummary] = useState('');
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.getTask(taskId).then(setTask).catch(console.error).finally(() => setLoading(false));
  }, [taskId]);

  async function sendMessage() {
    if (!messageText.trim()) return;
    setSending(true);
    try {
      const updated = await api.addMessage(taskId, {
        author_name: 'tech',
        message_type: 'text',
        message_text: messageText.trim(),
      });
      setTask(updated);
      setMessageText('');
    } catch (e) { console.error(e); }
    finally { setSending(false); }
  }

  async function submitTestResult() {
    if (!testTitle.trim()) return;
    setSending(true);
    try {
      const updated = await api.addTestResult(taskId, {
        test_type: testType,
        title: testTitle,
        status: testStatus,
        summary: testSummary || undefined,
      });
      setTask(updated);
      setTestTitle('');
      setTestSummary('');
    } catch (e) { console.error(e); }
    finally { setSending(false); }
  }

  async function uploadAttachment(files: FileList | null) {
    if (!files || files.length === 0) return;
    setUploading(true);
    try {
      const form = new FormData();
      Array.from(files).forEach(f => form.append('files', f));
      await axios.post(`/api/tasks/${taskId}/attachments`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      // Refresh task
      const updated = await api.getTask(taskId);
      setTask(updated);
    } catch (e) { console.error(e); }
    finally { setUploading(false); if (fileRef.current) fileRef.current.value = ''; }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (!task) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-400">
        <p>{t('mobile.task_not_found', 'Task not found')}</p>
        <button onClick={onBack} className="mt-4 text-blue-600 text-sm">{t('mobile.go_back', 'Go back')}</button>
      </div>
    );
  }

  const statusColor: Record<string, string> = {
    open: 'bg-blue-100 text-blue-700',
    in_progress: 'bg-yellow-100 text-yellow-700',
    approved: 'bg-green-100 text-green-700',
    rejected: 'bg-red-100 text-red-700',
  };

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-4 py-3">
        <div className="flex items-center gap-3 mb-2">
          <button onClick={onBack} className="p-1.5 rounded-lg hover:bg-gray-100">
            <ArrowLeft className="h-5 w-5 text-gray-600" />
          </button>
          <div className="flex-1 min-w-0">
            <p className="font-bold text-gray-900 text-sm truncate">{task.title}</p>
            <p className="text-xs text-gray-500">{task.site_name} · {task.asset_ref || task.asset_type}</p>
          </div>
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColor[task.status] || 'bg-gray-100 text-gray-600'}`}>
            {task.status}
          </span>
        </div>

        {/* Panel tabs */}
        <div className="flex gap-1">
          {(['messages', 'test', 'attachments'] as Panel[]).map(p => (
            <button
              key={p}
              onClick={() => setPanel(p)}
              className={`flex-1 py-1.5 rounded text-xs font-medium transition-colors ${
                panel === p ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600'
              }`}
            >
              {p === 'messages' ? t('mobile.messages', 'Messages') :
               p === 'test' ? t('mobile.test', 'Test Result') :
               t('mobile.files', 'Files')}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {panel === 'messages' && (
          <div className="space-y-3">
            {task.messages?.length === 0 && (
              <p className="text-center text-gray-400 text-sm py-8">{t('mobile.no_messages', 'No messages yet')}</p>
            )}
            {task.messages?.map((msg, i) => (
              <div key={i} className="bg-white rounded-xl border border-gray-200 p-3">
                <div className="flex items-center gap-2 mb-1">
                  <MessageSquare className="h-3.5 w-3.5 text-blue-500" />
                  <span className="text-xs font-semibold text-gray-700">{msg.author_name}</span>
                  <span className="text-xs text-gray-400 ml-auto">
                    {msg.created_at ? new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                  </span>
                </div>
                <p className="text-sm text-gray-800">{msg.message_text}</p>
              </div>
            ))}
          </div>
        )}

        {panel === 'test' && (
          <div className="space-y-3">
            {task.test_results?.map((tr, i) => (
              <div key={i} className="bg-white rounded-xl border border-gray-200 p-3">
                <div className="flex items-center gap-2 mb-1">
                  <FlaskConical className="h-3.5 w-3.5 text-purple-500" />
                  <span className="text-xs font-semibold text-gray-700">{tr.title}</span>
                  <span className={`ml-auto px-2 py-0.5 rounded-full text-xs font-medium ${
                    tr.status === 'pass' ? 'bg-green-100 text-green-700' :
                    tr.status === 'fail' ? 'bg-red-100 text-red-700' :
                    'bg-gray-100 text-gray-600'
                  }`}>{tr.status}</span>
                </div>
                {tr.summary && <p className="text-xs text-gray-600">{tr.summary}</p>}
              </div>
            ))}
          </div>
        )}

        {panel === 'attachments' && (
          <div className="space-y-3">
            <input ref={fileRef} type="file" multiple accept=".pdf,.dxf,.png,.jpg,.jpeg" className="hidden"
              onChange={e => uploadAttachment(e.target.files)} />
            <button
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              className="w-full py-3 border-2 border-dashed border-gray-300 rounded-xl text-sm text-gray-500 hover:border-blue-400 hover:text-blue-500 transition-colors flex items-center justify-center gap-2"
            >
              {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Paperclip className="h-4 w-4" />}
              {uploading ? t('mobile.uploading', 'Uploading…') : t('mobile.attach_file', 'Attach File')}
            </button>
            {(!task.messages || task.messages.length === 0) && (
              <p className="text-center text-gray-400 text-xs py-4">{t('mobile.no_attachments', 'No attachments yet')}</p>
            )}
          </div>
        )}
      </div>

      {/* Bottom action bar */}
      <div className="bg-white border-t border-gray-200 p-3 safe-area-bottom">
        {panel === 'messages' && (
          <div className="flex gap-2">
            <input
              type="text"
              value={messageText}
              onChange={e => setMessageText(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage()}
              placeholder={t('mobile.write_message', 'Write a message…')}
              className="flex-1 border border-gray-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={sendMessage}
              disabled={sending || !messageText.trim()}
              className="p-2.5 bg-blue-600 text-white rounded-xl disabled:opacity-50 hover:bg-blue-700 transition-colors"
            >
              {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            </button>
          </div>
        )}

        {panel === 'test' && (
          <div className="space-y-2">
            <input
              type="text"
              value={testTitle}
              onChange={e => setTestTitle(e.target.value)}
              placeholder={t('mobile.test_title', 'Test title…')}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <div className="flex gap-2">
              <select
                value={testType}
                onChange={e => setTestType(e.target.value)}
                className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm"
              >
                <option value="visual">Visual</option>
                <option value="iv_curve">IV Curve</option>
                <option value="insulation">Insulation</option>
                <option value="continuity">Continuity</option>
                <option value="thermal">Thermal</option>
              </select>
              <div className="flex rounded-lg border border-gray-300 overflow-hidden">
                <button onClick={() => setTestStatus('pass')}
                  className={`px-3 py-2 text-xs font-medium flex items-center gap-1 transition-colors ${testStatus === 'pass' ? 'bg-green-600 text-white' : 'bg-white text-gray-600'}`}>
                  <ThumbsUp className="h-3 w-3" /> Pass
                </button>
                <button onClick={() => setTestStatus('fail')}
                  className={`px-3 py-2 text-xs font-medium flex items-center gap-1 transition-colors ${testStatus === 'fail' ? 'bg-red-600 text-white' : 'bg-white text-gray-600'}`}>
                  <ThumbsDown className="h-3 w-3" /> Fail
                </button>
              </div>
            </div>
            <textarea
              value={testSummary}
              onChange={e => setTestSummary(e.target.value)}
              placeholder={t('mobile.test_notes', 'Notes (optional)')}
              rows={2}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={submitTestResult}
              disabled={sending || !testTitle.trim()}
              className="w-full py-2.5 bg-purple-600 text-white rounded-xl text-sm font-medium disabled:opacity-50 hover:bg-purple-700 transition-colors flex items-center justify-center gap-2"
            >
              {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <FlaskConical className="h-4 w-4" />}
              {t('mobile.submit_test', 'Submit Test Result')}
            </button>
          </div>
        )}

        {panel === 'attachments' && (
          <div className="flex gap-2">
            {task.requires_approval && (
              <div className="flex gap-2 w-full">
                <button
                  onClick={async () => {
                    setSending(true);
                    try {
                      const u = await api.approveTask(taskId, { approver_name: 'tech', approved: true });
                      setTask(u);
                    } catch (e) { console.error(e); }
                    finally { setSending(false); }
                  }}
                  disabled={sending}
                  className="flex-1 py-2.5 bg-green-600 text-white rounded-xl text-sm font-medium flex items-center justify-center gap-1"
                >
                  <CheckCircle className="h-4 w-4" /> {t('mobile.approve', 'Approve')}
                </button>
                <button
                  onClick={async () => {
                    setSending(true);
                    try {
                      const u = await api.approveTask(taskId, { approver_name: 'tech', approved: false });
                      setTask(u);
                    } catch (e) { console.error(e); }
                    finally { setSending(false); }
                  }}
                  disabled={sending}
                  className="flex-1 py-2.5 bg-red-600 text-white rounded-xl text-sm font-medium flex items-center justify-center gap-1"
                >
                  <XCircle className="h-4 w-4" /> {t('mobile.reject', 'Reject')}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
