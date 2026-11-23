import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  ApiError,
  createCategory,
  createDirection,
  addDocumentVersion,
  createDocument,
  createService,
  getCurrentAccount,
  getDocument,
  listCategories,
  listDirections,
  listDocumentVersions,
  listDocuments,
  listServices,
  login,
  logout,
  renameCategory,
  renameDirection,
  renameService,
  purgeDocument,
  restoreDocument,
  softDeleteDocument,
  updateDocument,
  type Account,
  type Category,
  type Direction,
  type DocumentSummary,
  type DocumentVersion,
  type Service,
} from './api'

type Section = 'directions' | 'services' | 'categories' | 'documents'

const sectionLabels: Record<Section, string> = {
  directions: 'Directions',
  services: 'Services',
  categories: 'Catégories',
  documents: 'Documents',
}

function apiMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 409) return 'Ce nom existe déjà dans ce registre.'
    if (error.status === 422) return 'Vérifiez le nom saisi puis réessayez.'
    if (error.status === 403) return 'Votre session ne dispose pas du droit de gérer le registre.'
    if (error.status === 503) return 'Le service est momentanément indisponible. Réessayez plus tard.'
    return error.message
  }
  return 'La requête n’a pas abouti. Vérifiez la connexion puis réessayez.'
}

function LoginScreen({ onLogin, serviceError }: { onLogin: (email: string, password: string) => Promise<void>; serviceError?: string }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await onLogin(email, password)
    } catch (cause) {
      setError(cause instanceof ApiError && cause.status === 401
        ? 'Adresse professionnelle ou mot de passe incorrect.'
        : apiMessage(cause))
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="login-layout">
      <section className="login-card" aria-labelledby="login-title">
        <div className="brand-mark brand-mark-large" aria-hidden="true">T</div>
        <p className="eyebrow">Municipalité de Tataouine</p>
        <h1 id="login-title">Espace d’administration</h1>
        <p className="muted login-copy">Connectez-vous avec votre compte professionnel pour gérer les référentiels.</p>
        {serviceError && <p className="feedback error login-alert" role="alert">{serviceError}</p>}
        <form className="form-stack" onSubmit={submit}>
          <label className="field">
            <span>Adresse professionnelle</span>
            <input autoComplete="username" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required maxLength={320} />
          </label>
          <label className="field">
            <span>Mot de passe</span>
            <input autoComplete="current-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required maxLength={128} />
          </label>
          {error && <p className="feedback error" role="alert">{error}</p>}
          <button className="button button-primary button-full" type="submit" disabled={busy}>
            {busy ? 'Connexion…' : 'Se connecter'}
          </button>
        </form>
        <p className="login-footnote">Accès réservé aux administrateurs centraux.</p>
      </section>
    </main>
  )
}

function AccessDenied({ onLogout }: { onLogout: () => void }) {
  return (
    <main className="login-layout">
      <section className="login-card" aria-labelledby="denied-title">
        <div className="status-icon status-icon-warning" aria-hidden="true">!</div>
        <p className="eyebrow">Accès restreint</p>
        <h1 id="denied-title">Cette page est réservée à l’administration centrale</h1>
        <p className="muted login-copy">Votre compte est connecté, mais il ne peut pas gérer les référentiels.</p>
        <button className="button button-secondary button-full" type="button" onClick={onLogout}>Se déconnecter</button>
      </section>
    </main>
  )
}

function NameEditor({
  initialName,
  label,
  busy,
  onSave,
  onCancel,
}: {
  initialName: string
  label: string
  busy: boolean
  onSave: (name: string) => Promise<void>
  onCancel: () => void
}) {
  const [name, setName] = useState(initialName)
  const [error, setError] = useState('')

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const value = name.trim()
    if (!value || value.length > 200) {
      setError('Le nom doit contenir entre 1 et 200 caractères.')
      return
    }
    setError('')
    try {
      await onSave(value)
    } catch (cause) {
      setError(apiMessage(cause))
    }
  }

  return (
    <form className="inline-editor" onSubmit={submit}>
      <label className="sr-only" htmlFor={`edit-${label}`}>Nouveau nom pour {label}</label>
      <input id={`edit-${label}`} value={name} maxLength={200} onChange={(event) => setName(event.target.value)} autoFocus />
      <button className="button button-primary button-small" type="submit" disabled={busy}>Enregistrer</button>
      <button className="button button-quiet button-small" type="button" onClick={onCancel} disabled={busy}>Annuler</button>
      {error && <span className="inline-error" role="alert">{error}</span>}
    </form>
  )
}

function CatalogWorkspace({ account, onLogout }: { account: Account; onLogout: () => Promise<void> }) {
  const [section, setSection] = useState<Section>('directions')
  const [directions, setDirections] = useState<Direction[]>([])
  const [services, setServices] = useState<Service[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [selectedDirection, setSelectedDirection] = useState('')
  const [editing, setEditing] = useState<string | null>(null)
  const [directionName, setDirectionName] = useState('')
  const [serviceName, setServiceName] = useState('')
  const [serviceDirection, setServiceDirection] = useState('')
  const [categoryName, setCategoryName] = useState('')
  const [categoryParent, setCategoryParent] = useState('')
  const [categoryRetention, setCategoryRetention] = useState('')
  const [documents, setDocuments] = useState<DocumentSummary[]>([])
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null)
  const [selectedDocument, setSelectedDocument] = useState<DocumentSummary | null>(null)
  const [documentVersions, setDocumentVersions] = useState<DocumentVersion[]>([])
  const [docFilterService, setDocFilterService] = useState('')
  const [docFilterCategory, setDocFilterCategory] = useState('')
  const [docLoading, setDocLoading] = useState(false)
  const [docBusy, setDocBusy] = useState(false)
  const [docError, setDocError] = useState('')
  const [docNotice, setDocNotice] = useState('')
  const [showUpload, setShowUpload] = useState(false)
  const [uploadTitle, setUploadTitle] = useState('')
  const [uploadService, setUploadService] = useState('')
  const [uploadCategory, setUploadCategory] = useState('')
  const [uploadDate, setUploadDate] = useState('')
  const [uploadReference, setUploadReference] = useState('')
  const [uploadDescription, setUploadDescription] = useState('')
  const [uploadIssuer, setUploadIssuer] = useState('')
  const [uploadKeywords, setUploadKeywords] = useState('')
  const [uploadConfidentiality, setUploadConfidentiality] = useState('')
  const [uploadRetentionCode, setUploadRetentionCode] = useState('')
  const [uploadFile, setUploadFile] = useState<File | null>(null)

  const loadDocuments = useCallback(async () => {
    setDocLoading(true)
    setDocError('')
    try {
      const page = await listDocuments({ serviceId: docFilterService || undefined, categoryId: docFilterCategory || undefined, limit: 50 })
      setDocuments(page.items)
    } catch (cause) {
      setDocError(apiMessage(cause))
    } finally {
      setDocLoading(false)
    }
  }, [docFilterService, docFilterCategory])

  useEffect(() => {
    if (section !== 'documents') return
    void loadDocuments()
  }, [section, loadDocuments])

  const loadDocumentDetail = useCallback(async (id: string) => {
    setDocError('')
    try {
      const [doc, versions] = await Promise.all([getDocument(id), listDocumentVersions(id)])
      setSelectedDocument(doc)
      setDocumentVersions(versions)
    } catch (cause) {
      setDocError(apiMessage(cause))
    }
  }, [])

  useEffect(() => {
    if (selectedDocumentId) void loadDocumentDetail(selectedDocumentId)
    else { setSelectedDocument(null); setDocumentVersions([]) }
  }, [selectedDocumentId, loadDocumentDetail])
  const loadCategories = useCallback(async () => {
    const roots = await listCategories({ rootsOnly: true })
    const children = await Promise.all(roots.map((root) => listCategories({ parentId: root.id })))
    return [...roots, ...children.flat()]
  }, [])

  const loadCatalog = useCallback(async (directionId: string) => {
    const nextDirections = await listDirections()
    const nextDirection = directionId || nextDirections[0]?.id || ''
    const [nextServices, nextCategories] = await Promise.all([
      nextDirection ? listServices(nextDirection) : Promise.resolve<Service[]>([]),
      loadCategories(),
    ])
    return { nextDirections, nextDirection, nextServices, nextCategories }
  }, [loadCategories])

  const applyCatalog = useCallback((catalog: Awaited<ReturnType<typeof loadCatalog>>) => {
    setDirections(catalog.nextDirections)
    setSelectedDirection(catalog.nextDirection)
    setServiceDirection((current) => current || catalog.nextDirection)
    setServices(catalog.nextServices)
    setCategories(catalog.nextCategories)
  }, [])

  const refresh = useCallback(async () => {
    applyCatalog(await loadCatalog(selectedDirection))
  }, [applyCatalog, loadCatalog, selectedDirection])

  useEffect(() => {
    let mounted = true
    void loadCatalog('')
      .then((catalog) => { if (mounted) applyCatalog(catalog) })
      .catch((cause: unknown) => { if (mounted) setError(apiMessage(cause)) })
      .finally(() => { if (mounted) setLoading(false) })
    return () => { mounted = false }
  }, [applyCatalog, loadCatalog])

  const roots = useMemo(() => categories.filter((category) => category.parent_id === null), [categories])
  const orderedCategories = useMemo(() => {
    const children = new Map<string, Category[]>()
    for (const category of categories) {
      if (category.parent_id) children.set(category.parent_id, [...(children.get(category.parent_id) ?? []), category])
    }
    return roots.flatMap((root) => [root, ...(children.get(root.id) ?? [])])
  }, [categories, roots])

  async function run(action: () => Promise<unknown>, success: string): Promise<boolean> {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await action()
      await refresh()
      setNotice(success)
      setEditing(null)
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) {
        await onLogout()
        return false
      }
      setError(apiMessage(cause))
      return false
    } finally {
      setBusy(false)
    }
    return true
  }

  async function createNamed(name: string, submit: (value: string) => Promise<unknown>, success: string, clear: () => void) {
    const value = name.trim()
    if (!value || value.length > 200) {
      setError('Le nom doit contenir entre 1 et 200 caractères.')
      return
    }
    if (!await run(() => submit(value), success)) return
    clear()
  }

  async function submitDirection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await createNamed(directionName, createDirection, 'Direction ajoutée au registre.', () => setDirectionName(''))
  }

  async function submitService(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!serviceDirection) {
      setError('Créez d’abord une Direction pour y rattacher ce Service.')
      return
    }
    await createNamed(serviceName, (name) => createService(serviceDirection, name), 'Service ajouté au registre.', () => setServiceName(''))
  }

  async function submitCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await createNamed(categoryName, (name) => createCategory(categoryParent || null, name, categoryRetention ? Number(categoryRetention) : null),
      categoryParent ? 'Sous-catégorie ajoutée au registre.' : 'Catégorie ajoutée au registre.', () => { setCategoryName(''); setCategoryRetention('') })
  }

  async function changeDirection(directionId: string) {
    setSelectedDirection(directionId)
    setError('')
    try {
      setServices(await listServices(directionId || undefined))
    } catch (cause) {
      setError(apiMessage(cause))
    }
  }

  const sectionDescription: Record<Section, string> = {
    directions: 'Structurez les directions de la municipalité.',
    services: 'Rattachez chaque service à sa direction.',
    categories: 'Organisez les catégories et leurs sous-catégories.',
    documents: 'Déposez, consultez et gérez les documents municipaux.',
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true">T</div>
          <div><strong>Tataouine</strong><span>Assistant municipal</span></div>
        </div>
        <p className="sidebar-label">Administration</p>
        <nav aria-label="Navigation du registre" className="side-nav">
          {(Object.keys(sectionLabels) as Section[]).map((item, index) => (
            <button key={item} className={`nav-item ${section === item ? 'active' : ''}`} type="button" onClick={() => { setSection(item); setError(''); setNotice('') }} aria-current={section === item ? 'page' : undefined}>
              <span className="nav-number">0{index + 1}</span><span>{sectionLabels[item]}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note"><span className="live-dot" />Registre applicatif</div>
          <div className="user-card">
            <div className="avatar" aria-hidden="true">{account.email.slice(0, 1).toUpperCase()}</div>
            <div className="user-copy"><strong>{account.email}</strong><span>Administrateur central</span></div>
            <button className="icon-button" type="button" onClick={() => void onLogout()} aria-label="Se déconnecter" title="Se déconnecter">↗</button>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar"><span>Référentiels</span><span className="topbar-separator">/</span><strong>{sectionLabels[section]}</strong><span className="topbar-spacer" /><span className="secure-label"><span aria-hidden="true">●</span> Session sécurisée</span></header>
        <div className="content-wrap">
          <section className="page-heading">
            <div>
              <p className="eyebrow">Administration · Registre</p>
              <h1>{sectionLabels[section]}<span className="heading-period">.</span></h1>
              <p className="muted">{sectionDescription[section]}</p>
            </div>
            <div className="heading-count"><strong>{section === 'directions' ? directions.length : section === 'services' ? services.length : categories.length}</strong><span>entrée{(section === 'directions' ? directions.length : section === 'services' ? services.length : categories.length) === 1 ? '' : 's'}</span></div>
          </section>

          <div className="info-banner"><span className="info-symbol" aria-hidden="true">i</span><p>Les référentiels sont la source de vérité de l’application. Leur gestion est réservée à l’administrateur central.</p></div>
          {error && <div className="feedback error page-feedback" role="alert"><span aria-hidden="true">!</span>{error}<button className="feedback-close" type="button" onClick={() => setError('')} aria-label="Fermer le message">×</button></div>}
          {notice && <div className="feedback success page-feedback" role="status"><span aria-hidden="true">✓</span>{notice}<button className="feedback-close" type="button" onClick={() => setNotice('')} aria-label="Fermer le message">×</button></div>}

          {loading ? <div className="loading-panel" role="status"><span className="spinner" />Chargement du registre…</div> : (
            <>
              {section === 'directions' && <section className="panel" aria-labelledby="directions-panel-title">
                <div className="panel-header"><div><p className="eyebrow">Axe organisationnel</p><h2 id="directions-panel-title">Directions enregistrées</h2></div><span className="count-pill">{directions.length}</span></div>
                <form className="create-row" onSubmit={(event) => void submitDirection(event)}>
                  <label className="field grow"><span>Nom de la Direction</span><input value={directionName} maxLength={200} onChange={(event) => setDirectionName(event.target.value)} placeholder="Ex. Direction des services techniques" /></label>
                  <button className="button button-primary" type="submit" disabled={busy}><span aria-hidden="true">＋</span> Ajouter</button>
                </form>
                {directions.length === 0 ? <EmptyState title="Aucune Direction pour le moment" text="Ajoutez une première Direction pour commencer à structurer les services." /> : (
                  <ul className="entry-list">
                    {directions.map((direction) => <li className="entry-row" key={direction.id}>
                      <div className="entry-icon direction-icon" aria-hidden="true">D</div>
                      <div className="entry-main">{editing === direction.id ? <NameEditor label={`direction-${direction.id}`} initialName={direction.name} busy={busy} onCancel={() => setEditing(null)} onSave={async (name) => { await run(() => renameDirection(direction.id, name), 'Direction renommée.') }} /> : <><strong>{direction.name}</strong><span>Direction municipale</span></>}</div>
                      {editing !== direction.id && <button className="button button-quiet button-small" type="button" onClick={() => setEditing(direction.id)} aria-label={`Renommer ${direction.name}`}>Renommer</button>}
                    </li>)}
                  </ul>
                )}
              </section>}

              {section === 'services' && <section className="panel" aria-labelledby="services-panel-title">
                <div className="panel-header"><div><p className="eyebrow">Axe organisationnel</p><h2 id="services-panel-title">Services enregistrés</h2></div><span className="count-pill">{services.length}</span></div>
                <div className="filter-row"><label className="field grow"><span>Filtrer par Direction</span><select value={selectedDirection} onChange={(event) => void changeDirection(event.target.value)} disabled={directions.length === 0}><option value="">Choisir une Direction</option>{directions.map((direction) => <option key={direction.id} value={direction.id}>{direction.name}</option>)}</select></label></div>
                <form className="create-row" onSubmit={(event) => void submitService(event)}>
                  <label className="field grow"><span>Nom du Service</span><input value={serviceName} maxLength={200} onChange={(event) => setServiceName(event.target.value)} placeholder="Ex. Service de l’état civil" /></label>
                  <label className="field parent-field"><span>Direction parente</span><select value={serviceDirection} onChange={(event) => setServiceDirection(event.target.value)} disabled={directions.length === 0}><option value="">Choisir</option>{directions.map((direction) => <option key={direction.id} value={direction.id}>{direction.name}</option>)}</select></label>
                  <button className="button button-primary" type="submit" disabled={busy || directions.length === 0}><span aria-hidden="true">＋</span> Ajouter</button>
                </form>
                {directions.length === 0 ? <EmptyState title="Ajoutez d’abord une Direction" text="Chaque Service doit être rattaché à une Direction existante." /> : services.length === 0 ? <EmptyState title="Aucun Service dans cette Direction" text="Ajoutez un Service pour compléter le registre." /> : (
                  <ul className="entry-list">{services.map((service) => <li className="entry-row" key={service.id}>
                    <div className="entry-icon service-icon" aria-hidden="true">S</div>
                    <div className="entry-main">{editing === service.id ? <NameEditor label={`service-${service.id}`} initialName={service.name} busy={busy} onCancel={() => setEditing(null)} onSave={async (name) => { await run(() => renameService(service.id, name), 'Service renommé.') }} /> : <><strong>{service.name}</strong><span>{service.direction_name}</span></>}</div>
                    {editing !== service.id && <button className="button button-quiet button-small" type="button" onClick={() => setEditing(service.id)} aria-label={`Renommer ${service.name}`}>Renommer</button>}
                  </li>)}</ul>
                )}
              </section>}

              {section === 'categories' && <section className="panel" aria-labelledby="categories-panel-title">
                <div className="panel-header"><div><p className="eyebrow">Axe de classification</p><h2 id="categories-panel-title">Catégories enregistrées</h2></div><span className="count-pill">{categories.length}</span></div>
                <form className="create-row" onSubmit={(event) => void submitCategory(event)}>
                  <label className="field grow"><span>Nom de la catégorie</span><input value={categoryName} maxLength={200} onChange={(event) => setCategoryName(event.target.value)} placeholder="Ex. Ressources humaines" /></label>
                  <label className="field parent-field"><span>Catégorie parente <span className="optional">(facultatif)</span></span><select value={categoryParent} onChange={(event) => setCategoryParent(event.target.value)}><option value="">Créer une catégorie principale</option>{roots.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
                  <label className="field retention-field"><span>Rétention (années, facultatif)</span><input type="number" min={1} value={categoryRetention} onChange={(event) => setCategoryRetention(event.target.value)} placeholder="Indéfinie" /></label>
                  <button className="button button-primary" type="submit" disabled={busy}><span aria-hidden="true">＋</span> Ajouter</button>
                </form>
                {categories.length === 0 ? <EmptyState title="Aucune catégorie pour le moment" text="Ajoutez une catégorie principale, puis complétez-la avec des sous-catégories." /> : (
                  <ul className="entry-list category-list">{orderedCategories.map((category) => <li className={`entry-row ${category.parent_id ? 'child-row' : ''}`} key={category.id}>
                    <div className={`entry-icon ${category.parent_id ? 'child-icon' : 'category-icon'}`} aria-hidden="true">{category.parent_id ? '↳' : 'C'}</div>
                    <div className="entry-main">{editing === category.id ? <NameEditor label={`category-${category.id}`} initialName={category.name} busy={busy} onCancel={() => setEditing(null)} onSave={async (name) => { await run(() => renameCategory(category.id, name), 'Catégorie renommée.') }} /> : <><strong>{category.name}</strong><span>{category.parent_id ? `Sous-catégorie de ${category.parent_name}` : 'Catégorie principale'}{category.retention_years ? ` · Rétention ${category.retention_years} an(s)` : ' · Conservation indéfinie'}</span></>}</div>
                    {editing !== category.id && <button className="button button-quiet button-small" type="button" onClick={() => setEditing(category.id)} aria-label={`Renommer ${category.name}`}>Renommer</button>}
                  </li>)}</ul>
                )}
              </section>}
            {section === 'documents' && <section className="panel" aria-labelledby="documents-panel-title">
                 <div className="panel-header"><div><p className="eyebrow">Gestion documentaire</p><h2 id="documents-panel-title">Documents enregistrés</h2></div><span className="count-pill">{documents.length}</span></div>
                 <div className="filter-row">
                   <label className="field grow"><span>Service</span><select value={docFilterService} onChange={(event) => setDocFilterService(event.target.value)}><option value="">Tous les services</option>{services.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
                   <label className="field grow"><span>Catégorie</span><select value={docFilterCategory} onChange={(event) => setDocFilterCategory(event.target.value)}><option value="">Toutes les catégories</option>{categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
                   <button className="button button-primary" type="button" onClick={() => setShowUpload((v) => !v)} disabled={docBusy}>{showUpload ? 'Annuler' : 'Déposer un document'}</button>
                 </div>
                 {docError && <div className="feedback error page-feedback" role="alert">{docError}</div>}
                 {docNotice && <div className="feedback success page-feedback" role="status">{docNotice}</div>}
                 {showUpload && (
                   <form className="create-row document-upload" onSubmit={async (event) => {
                     event.preventDefault()
                     if (!uploadFile) { setDocError('Sélectionnez un fichier.'); return }
                     setDocBusy(true); setDocError(''); setDocNotice('')
                     try {
                       const created = await createDocument({
                         title: uploadTitle, serviceId: uploadService, categoryId: uploadCategory,
                         documentDate: uploadDate, referenceNumber: uploadReference,
                         description: uploadDescription || null, issuer: uploadIssuer || null,
                         keywords: uploadKeywords.split(',').map((k) => k.trim()).filter(Boolean),
                         confidentialityLevel: uploadConfidentiality || null,
                         retentionCode: uploadRetentionCode || null, file: uploadFile,
                       })
                       setShowUpload(false)
                       setUploadTitle(''); setUploadService(''); setUploadCategory(''); setUploadDate(''); setUploadReference('')
                       setUploadDescription(''); setUploadIssuer(''); setUploadKeywords(''); setUploadConfidentiality(''); setUploadRetentionCode(''); setUploadFile(null)
                       setDocNotice('Document déposé.')
                       await loadDocuments()
                       setSelectedDocumentId(created.id)
                     } catch (cause) { setDocError(apiMessage(cause)) }
                     finally { setDocBusy(false) }
                   }}>
                     <label className="field grow"><span>Titre</span><input value={uploadTitle} onChange={(e) => setUploadTitle(e.target.value)} required maxLength={300} /></label>
                     <label className="field"><span>Service</span><select value={uploadService} onChange={(e) => setUploadService(e.target.value)} required><option value="">Choisir</option>{services.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
                     <label className="field"><span>Catégorie</span><select value={uploadCategory} onChange={(e) => setUploadCategory(e.target.value)} required><option value="">Choisir</option>{categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
                     <label className="field"><span>Date du document</span><input type="date" value={uploadDate} onChange={(e) => setUploadDate(e.target.value)} required /></label>
                     <label className="field"><span>Référence</span><input value={uploadReference} onChange={(e) => setUploadReference(e.target.value)} required maxLength={200} /></label>
                     <label className="field grow"><span>Description</span><input value={uploadDescription} onChange={(e) => setUploadDescription(e.target.value)} maxLength={5000} /></label>
                     <label className="field"><span>Émetteur</span><input value={uploadIssuer} onChange={(e) => setUploadIssuer(e.target.value)} maxLength={200} /></label>
                     <label className="field grow"><span>Mots-clés (virgules)</span><input value={uploadKeywords} onChange={(e) => setUploadKeywords(e.target.value)} /></label>
                     <label className="field"><span>Confidentialité</span><select value={uploadConfidentiality} onChange={(e) => setUploadConfidentiality(e.target.value)}><option value="">—</option><option value="public">Public</option><option value="interne">Interne</option><option value="confidentiel">Confidentiel</option><option value="secret">Secret</option></select></label>
                     <label className="field"><span>Code de conservation</span><input value={uploadRetentionCode} onChange={(e) => setUploadRetentionCode(e.target.value)} maxLength={100} /></label>
                     <label className="field"><span>Fichier</span><input type="file" onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)} required /></label>
                     <button className="button button-primary" type="submit" disabled={docBusy}>{docBusy ? 'Dépôt…' : 'Déposer'}</button>
                   </form>
                 )}
                 {docLoading ? <div className="loading-panel" role="status"><span className="spinner" />Chargement…</div> : (
                   documents.length === 0 ? <EmptyState title="Aucun document" text="Déposez un premier document pour commencer." /> : (
                     <ul className="entry-list">
                       {documents.map((doc) => <li className={`entry-row ${doc.status === 'deleted' ? 'deleted-row' : ''}`} key={doc.id}>
                         <div className="entry-icon document-icon" aria-hidden="true">📄</div>
                         <div className="entry-main">
                           <button className="link-button" type="button" onClick={() => setSelectedDocumentId(doc.id)}><strong>{doc.title}</strong></button>
                           <span>{doc.reference_number ?? '—'} · {doc.document_date} · {doc.status}</span>
                         </div>
                         <button className="button button-quiet button-small" type="button" onClick={() => setSelectedDocumentId(doc.id)}>Détails</button>
                       </li>)}
                     </ul>
                   )
                 )}
                 {selectedDocument && (
                   <div className="document-detail">
                     <h3>{selectedDocument.title}</h3>
                     <p className="muted">Référence {selectedDocument.reference_number} · Date {selectedDocument.document_date}</p>
                     <p className="muted">Service {selectedDocument.service_id} · Catégorie {selectedDocument.category_id} · Statut {selectedDocument.status}</p>
                     {selectedDocument.description && <p>{selectedDocument.description}</p>}
                     {selectedDocument.issuer && <p className="muted">Émetteur : {selectedDocument.issuer}</p>}
                     {selectedDocument.keywords.length > 0 && <p className="muted">Mots-clés : {selectedDocument.keywords.join(', ')}</p>}
                     {selectedDocument.confidentiality_level && <p className="muted">Confidentialité : {selectedDocument.confidentiality_level}</p>}
                     {selectedDocument.retention_code && <p className="muted">Conservation : {selectedDocument.retention_code}</p>}
                     <div className="detail-actions">
                       <a className="button button-secondary button-small" href={`/api/v1/documents/${selectedDocument.id}/content`} target="_blank" rel="noreferrer">Télécharger</a>
                       <button className="button button-quiet button-small" type="button" disabled={docBusy} onClick={() => {
                         const nextTitle = window.prompt('Nouveau titre', selectedDocument.title)
                         if (!nextTitle) return
                         void (async () => {
                           setDocBusy(true); setDocError('')
                           try {
                             const updated = await updateDocument(selectedDocument.id, {
                               title: nextTitle, serviceId: selectedDocument.service_id, categoryId: selectedDocument.category_id,
                               documentDate: selectedDocument.document_date, referenceNumber: selectedDocument.reference_number ?? '',
                               description: selectedDocument.description, issuer: selectedDocument.issuer,
                               keywords: selectedDocument.keywords, confidentialityLevel: selectedDocument.confidentiality_level,
                               retentionCode: selectedDocument.retention_code,
                             }, String(selectedDocument.aggregate_version))
                             setSelectedDocument(updated); setDocNotice('Métadonnées mises à jour.')
                             await loadDocuments()
                           } catch (cause) { setDocError(apiMessage(cause)) }
                           finally { setDocBusy(false) }
                         })()
                       }}>Renommer</button>
                       <label className="button button-quiet button-small">Nouvelle version<input type="file" hidden onChange={(e) => {
                         const f = e.target.files?.[0]; if (!f) return
                         void (async () => {
                           setDocBusy(true); setDocError('')
                           try {
                             const updated = await addDocumentVersion(selectedDocument.id, f, String(selectedDocument.aggregate_version))
                             setSelectedDocument(updated); setDocNotice('Version ajoutée.')
                             await loadDocuments(); await loadDocumentDetail(selectedDocument.id)
                           } catch (cause) { setDocError(apiMessage(cause)) }
                           finally { setDocBusy(false); e.target.value = '' }
                         })()
                       }} /></label>
                       {selectedDocument.status !== 'deleted' && <button className="button button-quiet button-small" type="button" disabled={docBusy} onClick={() => {
                         if (!window.confirm('Supprimer ce document ?')) return
                         void (async () => {
                           setDocBusy(true); setDocError('')
                           try {
                             await softDeleteDocument(selectedDocument.id, String(selectedDocument.aggregate_version))
                             setDocNotice('Document supprimé.')
                             await loadDocuments(); await loadDocumentDetail(selectedDocument.id)
                           } catch (cause) { setDocError(apiMessage(cause)) }
                           finally { setDocBusy(false) }
                         })()
                       }}>Supprimer</button>}
                       {selectedDocument.status === 'deleted' && <>
                         <button className="button button-secondary button-small" type="button" disabled={docBusy} onClick={() => {
                           void (async () => {
                             setDocBusy(true); setDocError('')
                             try {
                               const updated = await restoreDocument(selectedDocument.id, String(selectedDocument.aggregate_version))
                               setSelectedDocument(updated); setDocNotice('Document restauré.')
                               await loadDocuments()
                             } catch (cause) { setDocError(apiMessage(cause)) }
                             finally { setDocBusy(false) }
                           })()
                         }}>Restaurer</button>
                         <button className="button button-quiet button-small" type="button" disabled={docBusy} onClick={() => {
                           if (!window.confirm('Purger définitivement ce document ?')) return
                           void (async () => {
                             setDocBusy(true); setDocError('')
                             try {
                               await purgeDocument(selectedDocument.id, String(selectedDocument.aggregate_version))
                               setSelectedDocumentId(null); setDocNotice('Document purgé.')
                               await loadDocuments()
                             } catch (cause) { setDocError(apiMessage(cause)) }
                             finally { setDocBusy(false) }
                           })()
                         }}>Purger</button>
                       </>}
                     </div>
                     {documentVersions.length > 0 && (
                       <div className="versions-list">
                         <h4>Versions</h4>
                         <ul>{documentVersions.map((v) => <li key={v.id}>{v.sequence}. {v.original_filename} ({v.detected_mime_type}, {v.size_bytes} o) — {v.created_at}</li>)}</ul>
                       </div>
                     )}
                   </div>
                 )}
               </section>}
            </>
          )}
          <footer className="page-footer"><span>Les modifications sont conservées dans le registre de l’application.</span><span>Municipalité de Tataouine <b>·</b> Administration</span></footer>
        </div>
      </main>
    </div>
  )
}

function EmptyState({ title, text }: { title: string; text: string }) {
  return <div className="empty-state"><div className="empty-mark" aria-hidden="true">＋</div><div><strong>{title}</strong><p>{text}</p></div></div>
}

export default function App() {
  const [account, setAccount] = useState<Account | null>(null)
  const [checkingSession, setCheckingSession] = useState(true)
  const [accessDenied, setAccessDenied] = useState(false)
  const [startupError, setStartupError] = useState('')

  useEffect(() => {
    let mounted = true
    void getCurrentAccount().then((current) => {
      if (!mounted) return
      setAccount(current)
      setAccessDenied(!current.is_central_admin)
    }).catch((cause: unknown) => {
      if (!mounted) return
      if (cause instanceof ApiError && cause.status === 401) return
      setStartupError(apiMessage(cause))
    }).finally(() => { if (mounted) setCheckingSession(false) })
    return () => { mounted = false }
  }, [])

  async function authenticate(email: string, password: string) {
    const current = await login(email, password)
    setStartupError('')
    setAccount(current)
    setAccessDenied(!current.is_central_admin)
  }

  async function signOut() {
    try { await logout() } catch {
      // Always clear local account state when the session has already expired.
    } finally {
      setAccount(null)
      setAccessDenied(false)
    }
  }

  if (checkingSession) return <main className="boot-screen"><div className="brand-mark" aria-hidden="true">T</div><span className="spinner" /><p>Vérification de la session…</p></main>
  if (accessDenied && account) return <AccessDenied onLogout={() => void signOut()} />
  if (!account) return <LoginScreen onLogin={authenticate} serviceError={startupError} />
  return <CatalogWorkspace account={account} onLogout={signOut} />
}
