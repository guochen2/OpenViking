import DOMPurify from 'dompurify';
import { marked } from 'marked';

marked.setOptions({
  breaks: true,
  gfm: true,
});

export function renderMarkdown(content: string): string {
  if (!content) return '';
  const raw = marked.parse(content, { async: false });
  return DOMPurify.sanitize(raw, {
    USE_PROFILES: { html: true },
  });
}
