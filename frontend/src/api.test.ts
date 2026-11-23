import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  ApiError,
  createDirection,
  getCurrentAccount,
  listCategories,
  listServices,
  login,
} from './api'

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function stubFetch(response: Response) {
  const spy = vi.fn<typeof fetch>().mockResolvedValue(response)
  vi.stubGlobal('fetch', spy)
  return spy
}

function calledUrl(spy: ReturnType<typeof stubFetch>) {
  return String(spy.mock.calls[0]?.[0])
}

function calledInit(spy: ReturnType<typeof stubFetch>) {
  return spy.mock.calls[0]?.[1] as RequestInit
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('lecture du registre', () => {
  it('filtre les services par Direction côté API', async () => {
    const spy = stubFetch(jsonResponse([]))
    await listServices('direction-1')
    expect(calledUrl(spy)).toBe('/api/v1/admin/catalog/services?direction_id=direction-1')
  })

  it('demande uniquement les catégories racines', async () => {
    const spy = stubFetch(jsonResponse([]))
    await listCategories({ rootsOnly: true })
    expect(calledUrl(spy)).toBe('/api/v1/admin/catalog/categories?roots_only=true')
  })

  it('demande les sous-catégories d’une racine', async () => {
    const spy = stubFetch(jsonResponse([]))
    await listCategories({ parentId: 'racine-1' })
    expect(calledUrl(spy)).toBe('/api/v1/admin/catalog/categories?parent_id=racine-1')
  })

  it('liste tout le registre sans filtre explicite', async () => {
    const spy = stubFetch(jsonResponse([]))
    await listCategories()
    expect(calledUrl(spy)).toBe('/api/v1/admin/catalog/categories')
  })

  it('transmet les cookies de session sans mise en cache', async () => {
    const spy = stubFetch(jsonResponse({ id: 'a', email: 'admin@example.tn', is_central_admin: true }))
    await getCurrentAccount()
    const init = calledInit(spy)
    expect(init.credentials).toBe('same-origin')
    expect(init.cache).toBe('no-store')
  })
})

describe('protection CSRF', () => {
  it('refuse une écriture sans jeton CSRF sans appeler le backend', async () => {
    const spy = stubFetch(jsonResponse({}))
    await expect(createDirection('Urbanisme')).rejects.toMatchObject({
      name: 'ApiError',
      status: 403,
    })
    expect(spy).not.toHaveBeenCalled()
  })

  it('ajoute le jeton CSRF du cookie aux écritures', async () => {
    document.cookie = 'maa_csrf=jeton-test'
    const spy = stubFetch(jsonResponse({ id: 'd1', name: 'Urbanisme', created_at: '2026-11-23T00:00:00Z' }))
    await createDirection('Urbanisme')
    const headers = new Headers(calledInit(spy).headers)
    expect(headers.get('X-CSRF-Token')).toBe('jeton-test')
    expect(headers.get('Content-Type')).toBe('application/json')
  })

  it('n’exige pas de jeton pour une connexion sans session', async () => {
    const spy = stubFetch(jsonResponse({ id: 'a', email: 'admin@example.tn', is_central_admin: true }))
    await login('admin@example.tn', 'mot-de-passe')
    const headers = new Headers(calledInit(spy).headers)
    expect(headers.get('X-CSRF-Token')).toBeNull()
  })
})

describe('erreurs de l’API', () => {
  it('traduit une session expirée en message explicite', async () => {
    stubFetch(jsonResponse({ detail: 'Non authentifié' }, 401))
    await expect(getCurrentAccount()).rejects.toMatchObject({
      status: 401,
      message: 'Votre session a expiré. Reconnectez-vous.',
    })
  })

  it('propage le message métier d’un conflit', async () => {
    document.cookie = 'maa_csrf=jeton-test'
    stubFetch(jsonResponse({ detail: 'Ce nom existe déjà dans ce registre.' }, 409))
    const error = await createDirection('Urbanisme').catch((cause: unknown) => cause)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(409)
    expect((error as ApiError).message).toBe('Ce nom existe déjà dans ce registre.')
  })

  it('retombe sur un message neutre quand la réponse n’est pas JSON', async () => {
    stubFetch(new Response('<html>erreur</html>', { status: 500 }))
    await expect(getCurrentAccount()).rejects.toMatchObject({
      status: 500,
      message: 'La requête a échoué (500).',
    })
  })
})
