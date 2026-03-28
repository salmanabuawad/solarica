import { createPortal } from "react-dom";

interface ProgressModalProps {
  open: boolean;
  title: string;
  message?: string;
}

export function ProgressModal({ open, title, message }: ProgressModalProps) {
  if (!open) return null;

  return createPortal(
    <div className="progress-modal-backdrop">
      <div className="progress-modal" role="dialog" aria-modal="true" aria-label={title}>
        <div className="progress-modal-spinner">
          <div className="progress-modal-ring" />
        </div>
        <p className="progress-modal-title">{title}</p>
        {message && <p className="progress-modal-message">{message}</p>}
      </div>
    </div>,
    document.body,
  );
}
