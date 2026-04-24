interface ConfirmDialogProps {
  body: string;
  confirmLabel?: string;
  onCancel: () => void;
  onConfirm: () => void;
  open: boolean;
  title: string;
}

export function ConfirmDialog({
  open,
  title,
  body,
  confirmLabel = "确认",
  onCancel,
  onConfirm,
}: ConfirmDialogProps) {
  if (!open) {
    return null;
  }

  return (
    <div className="dialog-backdrop" role="presentation" onClick={onCancel}>
      <div
        className="dialog-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="dialog-copy">
          <div className="eyebrow">确认操作</div>
          <h2 id="confirm-dialog-title">{title}</h2>
          <p>{body}</p>
        </div>
        <div className="dialog-actions">
          <button type="button" className="ghost-button" onClick={onCancel}>
            取消
          </button>
          <button type="button" className="danger-button" onClick={onConfirm}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
