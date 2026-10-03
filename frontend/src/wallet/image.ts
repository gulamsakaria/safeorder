const MAX_SIDE = 800
const MAX_CHARS = 250_000
const QUALITY_STEPS = [0.75, 0.6, 0.45, 0.3]

/** Shrinks a photo in the browser to a small JPEG data URL, so the upload stays light. */
export async function photoToDataUrl(file: File): Promise<string> {
  const bitmap = await createImageBitmap(file)
  const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(bitmap.width * scale)
  canvas.height = Math.round(bitmap.height * scale)
  canvas.getContext('2d')!.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  let out = ''
  for (const quality of QUALITY_STEPS) {
    out = canvas.toDataURL('image/jpeg', quality)
    if (out.length <= MAX_CHARS) return out
  }
  throw new Error('photo too large')
}
