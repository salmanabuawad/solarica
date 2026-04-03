import { useEffect, useRef } from 'react';
import { X, HelpCircle, BookOpen, Lightbulb, ExternalLink } from 'lucide-react';
import { useHelp } from '../../contexts/HelpContext';
import { useTranslation } from 'react-i18next';

// ── Topic content map ────────────────────────────────────────────

interface HelpSection {
  icon: React.ElementType;
  titleKey: string;
  bodyKey: string;
}

const TOPIC_CONTENT: Record<string, HelpSection[]> = {
  dashboard: [
    { icon: Lightbulb, titleKey: 'help.dashboard.tip1.title', bodyKey: 'help.dashboard.tip1.body' },
    { icon: BookOpen,  titleKey: 'help.dashboard.tip2.title', bodyKey: 'help.dashboard.tip2.body' },
  ],
  projects: [
    { icon: Lightbulb, titleKey: 'help.projects.tip1.title', bodyKey: 'help.projects.tip1.body' },
  ],
  tasks: [
    { icon: Lightbulb, titleKey: 'help.tasks.tip1.title', bodyKey: 'help.tasks.tip1.body' },
  ],
  inventory: [
    { icon: Lightbulb, titleKey: 'help.inventory.tip1.title', bodyKey: 'help.inventory.tip1.body' },
  ],
  measurements: [
    { icon: BookOpen, titleKey: 'help.measurements.tip1.title', bodyKey: 'help.measurements.tip1.body' },
  ],
  security: [
    { icon: BookOpen, titleKey: 'help.security.tip1.title', bodyKey: 'help.security.tip1.body' },
  ],
};

const DEFAULT_SECTIONS: HelpSection[] = [
  { icon: Lightbulb, titleKey: 'help.general.tip1.title', bodyKey: 'help.general.tip1.body' },
  { icon: BookOpen,  titleKey: 'help.general.tip2.title', bodyKey: 'help.general.tip2.body' },
];

// ── Component ────────────────────────────────────────────────────

export default function HelpModal() {
  const { isOpen, topic, closeHelp } = useHelp();
  const { t } = useTranslation();
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') closeHelp(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [isOpen, closeHelp]);

  useEffect(() => {
    document.body.style.overflow = isOpen ? 'hidden' : '';
    return () => { document.body.style.overflow = ''; };
  }, [isOpen]);

  if (!isOpen) return null;

  const sections: HelpSection[] = (topic ? TOPIC_CONTENT[topic] : undefined) ?? DEFAULT_SECTIONS;
  const topicLabel = topic
    ? t(`help.topic.${topic}`, topic.charAt(0).toUpperCase() + topic.slice(1))
    : t('help.general.title', 'General Help');

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-[9100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={e => { if (e.target === overlayRef.current) closeHelp(); }}
      role="dialog"
      aria-modal="true"
      aria-label={t('help.modal.label', 'Help')}
    >
      <div className="bg-surface rounded-2xl shadow-2xl border border-border w-full max-w-lg flex flex-col max-h-[80vh] overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-primary-light flex items-center justify-center shrink-0">
              <HelpCircle size={16} className="text-primary" />
            </div>
            <h2 className="text-base font-semibold text-text-primary">
              {topicLabel}
            </h2>
          </div>
          <button
            onClick={closeHelp}
            className="p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-alt transition-colors"
            aria-label={t('common.close', 'Close')}
          >
            <X size={17} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-5 space-y-4">
          {sections.map((section, idx) => {
            const Icon = section.icon;
            return (
              <div key={idx} className="flex gap-3.5 p-3.5 rounded-xl bg-surface-alt border border-border">
                <div className="mt-0.5 shrink-0 w-8 h-8 rounded-lg bg-primary-light flex items-center justify-center">
                  <Icon size={15} className="text-primary" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-text-primary mb-1">
                    {t(section.titleKey)}
                  </p>
                  <p className="text-sm text-text-secondary leading-relaxed">
                    {t(section.bodyKey)}
                  </p>
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-border flex items-center justify-between bg-surface-alt shrink-0">
          <span className="text-xs text-text-muted">
            {t('help.footer.hint', 'Press Esc to close')}
          </span>
          <a
            href="https://solarica.io/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-xs text-primary hover:text-primary-hover transition-colors font-medium"
          >
            {t('help.footer.docs', 'Full documentation')}
            <ExternalLink size={11} />
          </a>
        </div>
      </div>
    </div>
  );
}
