/** User-written text is rendered as plain text; React escapes it, and line breaks are kept. */
export function UserText({ children }: { children: string }) {
  return <p className="whitespace-pre-wrap break-words">{children}</p>
}
