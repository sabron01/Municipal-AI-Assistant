import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import * as api from './api'

vi.mock('./api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./api')>()
  return {
    ...actual,
    getCurrentAccount: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
    listDirections: vi.fn(),
    listServices: vi.fn(),
    listCategories: vi.fn(),
    createDirection: vi.fn(),
    renameDirection: vi.fn(),
    createService: vi.fn(),
    renameService: vi.fn(),
    createCategory: vi.fn(),
    renameCategory: vi.fn(),
  }
})

const mocked = vi.mocked(api)

const admin = { id: 'u-1', email: 'admin@example.tn', is_central_admin: true }
const agent = { id: 'u-2', email: 'agent@example.tn', is_central_admin: false }
const techniques = { id: 'dir-1', name: 'Services techniques', created_at: '2026-11-23T08:00:00Z' }
const finances = { id: 'dir-2', name: 'Finances', created_at: '2026-11-23T08:00:00Z' }
const voirie = {
  id: 'svc-1', direction_id: 'dir-1', direction_name: 'Services techniques',
  name: 'Voirie', created_at: '2026-11-23T08:00:00Z',
}
const budget = {
  id: 'svc-2', direction_id: 'dir-2', direction_name: 'Finances',
  name: 'Budget', created_at: '2026-11-23T08:00:00Z',
}
const rootCategory = {
  id: 'cat-1', parent_id: null, parent_name: null,
  name: 'Ressources humaines', created_at: '2026-11-23T08:00:00Z', retention_years: null,
}
const childCategory = {
  id: 'cat-2', parent_id: 'cat-1', parent_name: 'Ressources humaines',
  name: 'Recrutement', created_at: '2026-11-23T08:00:00Z', retention_years: 5,
}

function authenticatedCatalog() {
  mocked.getCurrentAccount.mockResolvedValue(admin)
  mocked.listDirections.mockResolvedValue([techniques, finances])
  mocked.listServices.mockImplementation(async (directionId?: string) =>
    directionId === 'dir-2' ? [budget] : [voirie])
  mocked.listCategories.mockImplementation(async (options: api.CategoryQuery = {}) => {
    if (options.rootsOnly) return [rootCategory]
    if (options.parentId === rootCategory.id) return [childCategory]
    return [rootCategory, childCategory]
  })
  mocked.logout.mockResolvedValue(undefined)
}

function navButton(label: string) {
  const navigation = screen.getByRole('navigation', { name: 'Navigation du registre' })
  return within(navigation).getByRole('button', { name: new RegExp(label) })
}

beforeEach(() => {
  vi.resetAllMocks()
})

describe('accès au registre', () => {
  it('affiche la connexion lorsqu’aucune session n’est active', async () => {
    mocked.getCurrentAccount.mockRejectedValue(new api.ApiError(401, 'Non authentifié'))
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Espace d’administration' })).toBeTruthy()
    expect(mocked.listDirections).not.toHaveBeenCalled()
  })

  it('refuse le registre à un compte non administrateur', async () => {
    mocked.getCurrentAccount.mockResolvedValue(agent)
    render(<App />)
    expect(await screen.findByRole('heading', { name: /réservée à l’administration centrale/i })).toBeTruthy()
    expect(mocked.listDirections).not.toHaveBeenCalled()
  })

  it('ouvre le registre après une connexion administrateur', async () => {    const user = userEvent.setup()
    authenticatedCatalog()
    mocked.getCurrentAccount.mockRejectedValue(new api.ApiError(401, 'Non authentifié'))
    mocked.login.mockResolvedValue(admin)

    render(<App />)
    await user.type(await screen.findByLabelText('Adresse professionnelle'), 'admin@example.tn')
    await user.type(screen.getByLabelText('Mot de passe'), 'mot-de-passe-solide')
    await user.click(screen.getByRole('button', { name: 'Se connecter' }))

    expect(await screen.findByText('Services techniques')).toBeTruthy()
    expect(mocked.login).toHaveBeenCalledWith('admin@example.tn', 'mot-de-passe-solide')
  })

  it('explique une indisponibilité du service au démarrage', async () => {
    mocked.getCurrentAccount.mockRejectedValue(new api.ApiError(503, 'Service indisponible'))
    render(<App />)

    expect(await screen.findByText('Le service est momentanément indisponible. Réessayez plus tard.')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Se connecter' })).toBeTruthy()
  })

  it('n’affiche aucune alerte lorsqu’aucune session n’est ouverte', async () => {
    mocked.getCurrentAccount.mockRejectedValue(new api.ApiError(401, 'Non authentifié'))
    render(<App />)

    await screen.findByRole('heading', { name: 'Espace d’administration' })
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('permet de se déconnecter depuis le registre', async () => {
    authenticatedCatalog()
    const user = userEvent.setup()
    render(<App />)

    await screen.findByText('Services techniques')
    await user.click(screen.getByRole('button', { name: 'Se déconnecter' }))

    await waitFor(() => expect(mocked.logout).toHaveBeenCalled())
    expect(await screen.findByRole('heading', { name: 'Espace d’administration' })).toBeTruthy()
  })
})

describe('chargement du registre', () => {
  it('charge les services de la première Direction via l’API', async () => {
    authenticatedCatalog()
    render(<App />)

    expect(await screen.findByText('Services techniques')).toBeTruthy()
    await waitFor(() => expect(mocked.listServices).toHaveBeenCalledWith('dir-1'))
    expect(mocked.listServices).not.toHaveBeenCalledWith()
  })

  it('charge les catégories racines puis les sous-catégories via l’API', async () => {
    authenticatedCatalog()
    const user = userEvent.setup()
    render(<App />)

    await screen.findByText('Services techniques')
    expect(mocked.listCategories).toHaveBeenCalledWith({ rootsOnly: true })
    expect(mocked.listCategories).toHaveBeenCalledWith({ parentId: 'cat-1' })

    await user.click(navButton('Catégories'))
    expect(await screen.findByText('Recrutement')).toBeTruthy()
  })

  it('filtre les services par Direction à la sélection', async () => {
    authenticatedCatalog()
    const user = userEvent.setup()
    render(<App />)

    await screen.findByText('Services techniques')
    await user.click(navButton('Services'))
    expect(await screen.findByText('Voirie')).toBeTruthy()

    await user.selectOptions(screen.getByLabelText('Filtrer par Direction'), 'dir-2')
    expect(await screen.findByText('Budget')).toBeTruthy()
    expect(mocked.listServices).toHaveBeenCalledWith('dir-2')
    expect(screen.queryByText('Voirie')).toBeNull()
  })
})

describe('formulaires et retours', () => {
  it('refuse un nom vide sans appeler l’API', async () => {
    authenticatedCatalog()
    const user = userEvent.setup()
    render(<App />)

    await screen.findByText('Services techniques')
    await user.click(screen.getByRole('button', { name: 'Ajouter' }))

    expect(await screen.findByText('Le nom doit contenir entre 1 et 200 caractères.')).toBeTruthy()
    expect(mocked.createDirection).not.toHaveBeenCalled()
  })

  it('renomme une Direction puis recharge le registre', async () => {
    authenticatedCatalog()
    mocked.renameDirection.mockResolvedValue({ ...techniques, name: 'Urbanisme et patrimoine' })
    const user = userEvent.setup()
    render(<App />)

    await screen.findByText('Services techniques')
    await user.click(screen.getByRole('button', { name: 'Renommer Services techniques' }))
    const input = screen.getByLabelText('Nouveau nom pour direction-dir-1')
    await user.clear(input)
    await user.type(input, 'Urbanisme et patrimoine')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(mocked.renameDirection).toHaveBeenCalledWith('dir-1', 'Urbanisme et patrimoine'))
    expect(await screen.findByText('Direction renommée.')).toBeTruthy()
  })

  it('traduit une erreur de validation en message compréhensible', async () => {
    authenticatedCatalog()
    mocked.createDirection.mockRejectedValue(new api.ApiError(422, 'Requête invalide'))
    const user = userEvent.setup()
    render(<App />)

    await screen.findByText('Services techniques')
    await user.type(screen.getByLabelText('Nom de la Direction'), 'Urbanisme')
    await user.click(screen.getByRole('button', { name: 'Ajouter' }))

    expect(await screen.findByText('Vérifiez le nom saisi puis réessayez.')).toBeTruthy()
  })

  it('affiche un état vide lorsque le registre ne contient aucune Direction', async () => {
    authenticatedCatalog()
    mocked.listDirections.mockResolvedValue([])
    render(<App />)

    expect(await screen.findByText('Aucune Direction pour le moment')).toBeTruthy()
    expect(mocked.listServices).not.toHaveBeenCalled()
  })
})

describe('gestion de session expirée', () => {
  it('déconnecte l’utilisateur lorsqu’une action reçoit un 401', async () => {
    authenticatedCatalog()
    mocked.createDirection.mockRejectedValue(new api.ApiError(401, 'Non authentifié'))
    const user = userEvent.setup()
    render(<App />)

    await screen.findByText('Services techniques')
    await user.type(screen.getByLabelText('Nom de la Direction'), 'Urbanisme')
    await user.click(screen.getByRole('button', { name: 'Ajouter' }))

    await waitFor(() => expect(mocked.logout).toHaveBeenCalled())
    expect(await screen.findByRole('heading', { name: 'Espace d’administration' })).toBeTruthy()
  })

  it('affiche un message explicite en cas de conflit de nom', async () => {
    authenticatedCatalog()
    mocked.createDirection.mockRejectedValue(new api.ApiError(409, 'Ce nom existe déjà dans ce registre.'))
    const user = userEvent.setup()
    render(<App />)

    await screen.findByText('Services techniques')
    await user.type(screen.getByLabelText('Nom de la Direction'), 'Finances')
    await user.click(screen.getByRole('button', { name: 'Ajouter' }))

    expect(await screen.findByText('Ce nom existe déjà dans ce registre.')).toBeTruthy()
  })
})
