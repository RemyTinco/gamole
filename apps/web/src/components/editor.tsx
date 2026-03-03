'use client'

import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import { Markdown } from 'tiptap-markdown'
import type { MarkdownStorage } from 'tiptap-markdown'
import { useEffect } from 'react'

/** Safely get markdown from TipTap editor storage (typed as DOM Storage by default) */
function getMarkdownFromEditor(editor: ReturnType<typeof useEditor>): string {
  if (!editor) return ''
  const storage = editor.storage as unknown as Record<string, MarkdownStorage>
  return storage.markdown?.getMarkdown() ?? ''
}

interface EditorProps {
  /** Initial content — markdown string when markdown=true, HTML otherwise */
  content: string
  /** Called on every change with the current content (markdown or HTML) */
  onChange: (value: string) => void
  /** Enable markdown input/output mode (default: false = HTML mode) */
  markdown?: boolean
  /** Minimum height CSS value (default: '300px') */
  minHeight?: string
  /** Make the editor read-only */
  readOnly?: boolean
}

export function Editor({ content, onChange, markdown = false, minHeight = '300px', readOnly = false }: EditorProps) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      ...(markdown
        ? [
            Markdown.configure({
              html: false,
              transformPastedText: true,
              transformCopiedText: true,
            }),
          ]
        : []),
    ],
    content: markdown ? content : content,
    editable: !readOnly,
    onUpdate: ({ editor }) => {
      if (markdown) {
        const md = getMarkdownFromEditor(editor)
        onChange(md)
      } else {
        onChange(editor.getHTML())
      }
    },
  })

  // Sync content from parent when it changes externally (e.g. SSE stream update)
  useEffect(() => {
    if (!editor || editor.isDestroyed) return
    const currentContent = markdown
      ? getMarkdownFromEditor(editor)
      : editor.getHTML()
    if (content !== currentContent) {
      editor.commands.setContent(content)
    }
  // Only re-sync when content prop changes, not on every editor keystroke
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [content, editor])

  return (
    <div className="rounded-md border">
      {/* Toolbar */}
      {!readOnly && (
        <div className="flex flex-wrap items-center gap-1 border-b p-2">
          <button
            type="button"
            onClick={() => editor?.chain().focus().toggleBold().run()}
            className={`rounded px-2 py-1 text-sm font-bold hover:bg-accent ${
              editor?.isActive('bold') ? 'bg-accent' : ''
            }`}
          >
            B
          </button>
          <button
            type="button"
            onClick={() => editor?.chain().focus().toggleItalic().run()}
            className={`rounded px-2 py-1 text-sm italic hover:bg-accent ${
              editor?.isActive('italic') ? 'bg-accent' : ''
            }`}
          >
            I
          </button>
          <div className="mx-1 h-5 w-px bg-border" />
          <button
            type="button"
            onClick={() => editor?.chain().focus().toggleHeading({ level: 1 }).run()}
            className={`rounded px-2 py-1 text-sm font-semibold hover:bg-accent ${
              editor?.isActive('heading', { level: 1 }) ? 'bg-accent' : ''
            }`}
          >
            H1
          </button>
          <button
            type="button"
            onClick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()}
            className={`rounded px-2 py-1 text-sm font-semibold hover:bg-accent ${
              editor?.isActive('heading', { level: 2 }) ? 'bg-accent' : ''
            }`}
          >
            H2
          </button>
          <button
            type="button"
            onClick={() => editor?.chain().focus().toggleHeading({ level: 3 }).run()}
            className={`rounded px-2 py-1 text-sm font-semibold hover:bg-accent ${
              editor?.isActive('heading', { level: 3 }) ? 'bg-accent' : ''
            }`}
          >
            H3
          </button>
          <div className="mx-1 h-5 w-px bg-border" />
          <button
            type="button"
            onClick={() => editor?.chain().focus().toggleBulletList().run()}
            className={`rounded px-2 py-1 text-sm hover:bg-accent ${
              editor?.isActive('bulletList') ? 'bg-accent' : ''
            }`}
          >
            • List
          </button>
          <button
            type="button"
            onClick={() => editor?.chain().focus().toggleOrderedList().run()}
            className={`rounded px-2 py-1 text-sm hover:bg-accent ${
              editor?.isActive('orderedList') ? 'bg-accent' : ''
            }`}
          >
            1. List
          </button>
          <div className="mx-1 h-5 w-px bg-border" />
          <button
            type="button"
            onClick={() => editor?.chain().focus().toggleBlockquote().run()}
            className={`rounded px-2 py-1 text-sm hover:bg-accent ${
              editor?.isActive('blockquote') ? 'bg-accent' : ''
            }`}
          >
            &ldquo; Quote
          </button>
          <button
            type="button"
            onClick={() => editor?.chain().focus().toggleCodeBlock().run()}
            className={`rounded px-2 py-1 text-sm font-mono hover:bg-accent ${
              editor?.isActive('codeBlock') ? 'bg-accent' : ''
            }`}
          >
            {'</>'}
          </button>
        </div>
      )}
      {/* Editor */}
      <EditorContent
        editor={editor}
        className={`prose prose-sm dark:prose-invert max-w-none p-4 focus:outline-none [&_.ProseMirror]:outline-none`}
        style={{ minHeight }}
      />
    </div>
  )
}
