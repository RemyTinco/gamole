'use client'

import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'

interface EditorProps {
  content: string
  onChange: (html: string) => void
}

export function Editor({ content, onChange }: EditorProps) {
  const editor = useEditor({
    extensions: [StarterKit],
    content,
    onUpdate: ({ editor }) => {
      onChange(editor.getHTML())
    },
  })

  return (
    <div className="rounded-md border">
      {/* Toolbar */}
      <div className="flex items-center gap-1 border-b p-2">
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
      </div>
      {/* Editor */}
      <EditorContent
        editor={editor}
        className="prose prose-sm max-w-none p-4 focus:outline-none min-h-[300px] [&_.ProseMirror]:outline-none [&_.ProseMirror]:min-h-[300px]"
      />
    </div>
  )
}
