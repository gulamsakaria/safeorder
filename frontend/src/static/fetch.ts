import { getResponse } from 'msw'
import { allHandlers } from './handlers'

/** The fetch of the static site: every /api request is answered in the browser. */
export async function staticFetch(request: Request): Promise<Response> {
  const response = await getResponse(allHandlers, request)
  if (response) return response
  return Response.json({ error: { code: 'NOT_FOUND', message: 'not found' } }, { status: 404 })
}
